from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# ============================
# USER AND PROFILE MODELS
# ============================

import uuid

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_admin = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(blank=True)
    total_xp = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    token_created_at = models.DateTimeField(auto_now_add=True, null=True)
    
    # Remove username field requirement and make it non-unique
    username = models.CharField(max_length=150, unique=False)
    
    # Set email as the USERNAME_FIELD for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username is still required for creation
    
    def __str__(self):
        return self.email

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    skills = models.TextField(blank=True)
    experience_level = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email}'s Profile"

from django.db import models
from django.utils import timezone
import uuid

# models.py

from django.db import models
from django.utils import timezone

class TempUserRegistration(models.Model):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150)
    password = models.CharField(max_length=128)
    profile_picture = models.ImageField(upload_to='temp_profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class OTP(models.Model):
    email = models.EmailField(default='temp@example.com')  # Temporary default
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return timezone.now() > self.expires_at




# ============================
# LEARNING MODULE MODELS
# ============================

class Module(models.Model):
    DIFFICULTY_LEVELS = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    estimated_time = models.CharField(max_length=50)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS)
    thumbnail = models.ImageField(upload_to='module_thumbnails/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    xp_reward = models.PositiveIntegerField(default=100)  # Experience points for completing
    
    def __str__(self):
        return self.name


import re
from django.db import models

import os
import re
from django.db import models
from django.conf import settings

import csv
import io
import re
from django.conf import settings
from django.db import models

class ModuleContent(models.Model):
    CONTENT_TYPES = (
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
    )
    
    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    video_url = models.URLField(blank=True, null=True)
    pdf_file = models.FileField(upload_to='module_pdfs/', blank=True, null=True)
    quiz_file = models.FileField(upload_to='quiz_csvs/', blank=True, null=True, help_text='Upload CSV file for quiz questions.')
    content_text = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField(default=0)
    is_required = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['module', 'order']),
        ]
    
    def __str__(self):
        return f"{self.module.name} - {self.title}"

    # --- Video helper methods: (unchanged) ---
    def is_youtube_video(self):
        if not self.video_url:
            return False
        return any(domain in self.video_url for domain in ['youtube.com', 'youtu.be'])
    
    def is_vimeo_video(self):
        if not self.video_url:
            return False
        return 'vimeo.com' in self.video_url
    
    def get_video_embed_url(self):
        if not self.video_url:
            return None
        try:
            url = self.video_url

            if self.is_youtube_video():
                if 'youtu.be' in url:
                    video_id = url.split('/')[-1].split('?')[0]
                elif 'embed' in url:
                    return url.split('?')[0]
                else:
                    match = re.search(r'(?:v=|/v/)([a-zA-Z0-9_-]{11})', url)
                    if match:
                        video_id = match.group(1)
                    else:
                        return None
                
                if len(video_id) == 11 and all(c.isalnum() or c in ['-', '_'] for c in video_id):
                    return f'https://www.youtube.com/embed/{video_id}'
                return None

            elif self.is_vimeo_video():
                if 'player.vimeo.com' in url:
                    return url.split('?')[0]
                match = re.search(r'vimeo.com/(?:channels/[\w]+/|groups/[\w]+/videos/|album/\d+/video/|video/|)(\d+)', url)
                if match:
                    video_id = match.group(1)
                    return f'https://player.vimeo.com/video/{video_id}'
                return None

            else:
                return url  # fallback for other direct URLs (e.g., mp4)

        except Exception as e:
            print(f"Error processing video URL: {e}")
            return None

    # --- PDF helper methods ---

    def pdf_file_exists(self):
        if self.pdf_file:
            try:
                return self.pdf_file.storage.exists(self.pdf_file.name)
            except Exception:
                return False
        return False

    def get_pdf_file_size(self):
        if self.pdf_file:
            try:
                return self.pdf_file.size
            except Exception:
                return None
        return None

    # --- Quiz CSV parsing method ---

    def get_quiz_questions(self):
        """
        Parses the uploaded CSV quiz_file into a list of dicts:
        Each row corresponds to:
        Category, Question, Difficulty, Option1, Option2, Option3, Option4, Correct Answer (optional)
        """
        if not self.quiz_file:
            return []

        try:
            # Read the file in-memory and decode
            file_data = self.quiz_file.read().decode('utf-8')
            csv_reader = csv.reader(io.StringIO(file_data))

            questions = []
            for row in csv_reader:
                # Skip empty or malformed rows
                if not row or len(row) < 7:
                    continue

                category = row[0].strip()
                question_text = row[1].strip()
                difficulty = row[2].strip()
                options = [row[3].strip(), row[4].strip(), row[5].strip(), row[6].strip()]
                correct_answer = row[7].strip() if len(row) > 7 else None

                questions.append({
                    "category": category,
                    "question_text": question_text,
                    "difficulty": difficulty,
                    "options": options,
                    "correct_answer": correct_answer,
                })

            return questions
        except Exception as e:
            print(f"Error reading quiz CSV: {e}")
            return []

class QuizAttemptLearningPath(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.ForeignKey(ModuleContent, on_delete=models.CASCADE)
    score = models.IntegerField()
    total = models.IntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content')

    def __str__(self):
        return f"Attempt by {self.user} on {self.content.title}"
    
class QuizUserAnswer(models.Model):
    quiz_attempt = models.ForeignKey(QuizAttemptLearningPath, on_delete=models.CASCADE, related_name='user_answers')
    question_index = models.PositiveIntegerField()
    selected_answer = models.CharField(max_length=255)  # store answer text or ID, here text for simplicity
    
    class Meta:
        unique_together = ('quiz_attempt', 'question_index')
        indexes = [
            models.Index(fields=['quiz_attempt', 'question_index']),
        ]
    
    def __str__(self):
        return f"Answer for question {self.question_index} in {self.quiz_attempt}"


from django.conf import settings
from django.db import models

class AssignmentSubmission(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey(ModuleContent, limit_choices_to={'content_type': 'assignment'}, on_delete=models.CASCADE)
    uploaded_file = models.FileField(upload_to='assignment_submissions/%Y/%m/%d/')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'assignment')  # One submission per user per assignment; remove if multiple allowed.

    def __str__(self):
        return f"{self.user} submission for {self.assignment.title}"


class ModuleCompletion(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='completed_contents')
    content = models.ForeignKey(ModuleContent, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('user', 'content')
        indexes = [
            models.Index(fields=['user', 'content']),
        ]
    
    def __str__(self):
        return f"{self.user.username} completed {self.content.title}"


class LearningPath(models.Model):
    STATUS_CHOICES = (
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='learning_paths')
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    progress = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Made nullable
    
    def save(self, *args, **kwargs):
        # Calculate progress if not set
        if self.progress == 0:  # Changed condition to avoid recalculating unnecessarily
            self.progress = self.calculate_progress()
        
        # Update status based on progress
        if self.progress == 100 and self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            # Award badge and XP after saving to ensure ID exists
            super().save(*args, **kwargs)
            self.award_badge_and_xp()
            return
        elif self.progress > 0 and self.status == 'not_started':
            self.status = 'in_progress'
            if not self.started_at:
                self.started_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def calculate_progress(self):
        total_contents = self.module.contents.filter(is_required=True).count()
        if total_contents == 0:
            return 0
        completed_contents = ModuleCompletion.objects.filter(
            user=self.user,
            content__module=self.module,
            is_completed=True
        ).count()
        return int((completed_contents / total_contents) * 100)
    
    def __str__(self):
        return f"{self.user.username} - {self.module.name} ({self.status})"


class ProgressNode(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='progress_nodes')
    step = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
    detail = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.step}"


# ============================
# HACKATHON MODELS
# ============================

# ============================
# ENHANCED HACKATHON MODELS
# ============================

class Hackathon(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('registration_open', 'Registration Open'),
        ('in_progress', 'In Progress'),
        ('evaluation', 'Under Evaluation'),
        ('completed', 'Completed'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_hackathons')
    
    # Date fields
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_start = models.DateTimeField()
    registration_end = models.DateTimeField()
    
    # Media and content
    thumbnail = models.ImageField(upload_to='hackathon_thumbnails/', null=True, blank=True)
    prize = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    
    # Team configuration
    team_size_min = models.PositiveIntegerField(default=1)
    team_size_max = models.PositiveIntegerField(default=5)
    allow_individual = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(default=100)
    
    # Evaluation
    evaluation_criteria = models.JSONField(default=dict, help_text="JSON object with criterion names and max scores")
    
    # Status and permissions
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    is_active = models.BooleanField(default=True)
    allow_student_creation = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['is_active', 'registration_start']),
        ]
        ordering = ['-start_date']
    
    def __str__(self):
        return self.name
    
    @property
    def is_registration_open(self):
        now = timezone.now()
        return (self.registration_start <= now <= self.registration_end and 
                self.status == 'registration_open')
    
    @property
    def current_participants(self):
        return HackathonRegistration.objects.filter(hackathon=self, is_active=True).count()
    
    @property
    def spots_remaining(self):
        return max(0, self.max_participants - self.current_participants)
    
    @property
    def can_submit(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.status == 'in_progress'
    
    # Add this method to your Hackathon model
    def can_creator_participate(self):
        """Allow creator to participate in their own hackathon"""
        return True

    def is_user_creator(self, user):
        """Check if user is the creator"""
        return self.created_by == user


class HackathonTeam(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='led_teams')
    members = models.ManyToManyField(CustomUser, related_name='hackathon_teams', blank=True)
    
    description = models.TextField(blank=True)
    invite_code = models.CharField(max_length=20, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('hackathon', 'name')
        indexes = [
            models.Index(fields=['hackathon', 'is_active']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.invite_code:
            import string
            import random
            self.invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)
        # Add leader as member
        if self.pk:
            self.members.add(self.leader)
    
    @property
    def member_count(self):
        return self.members.count()
    
    @property
    def can_add_members(self):
        return self.member_count < self.hackathon.team_size_max
    
    def __str__(self):
        return f"{self.hackathon.name} - {self.name}"

class HackathonRegistration(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hackathon_registrations')
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, null=True, blank=True, related_name='registrations')
    
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('hackathon', 'user')
        indexes = [
            models.Index(fields=['hackathon', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.hackathon.name}"

class HackathonSubmission(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name='submissions')
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, null=True, blank=True, related_name='submissions')
    individual_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name='individual_submissions')
    
    # Project details
    project_title = models.CharField(max_length=200)
    project_description = models.TextField()
    
    # Submission files and URLs
    submission_file = models.FileField(upload_to='hackathon_submissions/', null=True, blank=True)
    submission_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    demo_url = models.URLField(blank=True)
    
    # Evaluation results
    scores = models.JSONField(default=dict)  # Individual criterion scores
    final_score = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_winner = models.BooleanField(default=False)
    prize_category = models.CharField(max_length=100, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['hackathon', 'final_score']),
            models.Index(fields=['hackathon', 'submitted_at']),
        ]
        ordering = ['-final_score', '-submitted_at']
    
    @property
    def submitter_name(self):
        if self.team:
            return self.team.name
        return self.individual_user.username if self.individual_user else "Unknown"
    
    @property
    def is_team_submission(self):
        return self.team is not None
    
    def __str__(self):
        return f"{self.project_title} - {self.hackathon.name}"

class HackathonEvaluation(models.Model):
    submission = models.ForeignKey(HackathonSubmission, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hackathon_evaluations')
    
    scores = models.JSONField(default=dict)  # Individual criterion scores
    comments = models.TextField(blank=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('submission', 'evaluator')
        indexes = [
            models.Index(fields=['submission', 'evaluator']),
        ]
    
    def __str__(self):
        return f"Evaluation by {self.evaluator.username} for {self.submission.project_title}"



# ============================
# BADGE AND LEADERBOARD MODELS
# ============================
from django.utils import timezone

from django.db import models
from django.utils import timezone

from django.db import models
from django.utils import timezone

# class Badge(models.Model):
#     AWARD_TYPES = (
#         ('badge', 'Badge'),
#         ('certificate', 'Certificate'),
#     )

#     module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='badges', null=True, blank=True)
#     name = models.CharField(max_length=100)
#     description = models.TextField()
#     award_type = models.CharField(max_length=20, choices=AWARD_TYPES, default='badge')

#     icon = models.ImageField(upload_to='badge_icons/', null=True, blank=True)
#     certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)
#     certificate_url = models.URLField(null=True, blank=True, help_text='External certificate link')

#     date_created = models.DateTimeField(default=timezone.now)

#     def __str__(self):
#         return self.name






class Leaderboard(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='leaderboard')
    score = models.IntegerField(default=0)
    rank = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-score']
        indexes = [
            models.Index(fields=['score']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - Rank {self.rank}"


# ============================
# LEGACY ASSESSMENT MODEL
# ============================

class Assessment(models.Model):
    """Legacy assessment model - kept for backward compatibility"""
    ASSESSMENT_TYPES = (
        ('coding', 'Coding Challenge'),
        ('quiz', 'Technical Quiz'),
        ('system_design', 'System Design'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assessments')
    name = models.CharField(max_length=100)
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPES)
    file = models.FileField(upload_to='assessments/')
    score = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    feedback = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.score}%)"


# =========================================
# QUIZ AND ASSESSMENT SYSTEM MODELS
# =========================================

class Competency(models.Model):
    """Represents a skill area or topic for quizzes"""
    name = models.CharField(max_length=50, unique=True)  # Added unique constraint
    description = models.TextField()
    icon = models.CharField(max_length=50, default='fas fa-cog')  # FontAwesome icon
    is_active = models.BooleanField(default=True)  # Added to enable/disable competencies
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Made nullable
    
    class Meta:
        verbose_name_plural = "Competencies"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Question(models.Model):
    """Quiz questions linked to competencies"""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    text = models.TextField()
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='questions')
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    points = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)  # Added to enable/disable questions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['competency', 'difficulty', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.competency.name} - {self.difficulty} - {self.text[:50]}..."
    
    @property
    def correct_answer(self):
        """Get the correct answer for this question"""
        return self.answers.filter(is_correct=True).first()


class Answer(models.Model):
    """Answer choices for quiz questions"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)  # Added for answer ordering
    
    class Meta:
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['question', 'is_correct']),
        ]
    
    def __str__(self):
        return f"{self.question.text[:30]} - {self.text[:20]}"


class UserCompetency(models.Model):
    """Tracks user's competency levels and scores"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='competencies')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='user_competencies')
    score = models.FloatField(
        default=0, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    attempts_count = models.PositiveIntegerField(default=0)  # Track number of attempts
    best_score = models.FloatField(default=0)  # Track best score achieved
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Made nullable
    
    class Meta:
        unique_together = ('user', 'competency')
        verbose_name_plural = "User Competencies"
        indexes = [
            models.Index(fields=['user', 'score']),
        ]
    
    def save(self, *args, **kwargs):
        # Update best score if current score is higher
        if self.score > self.best_score:
            self.best_score = self.score
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.competency.name} ({self.score}%)"


class QuizSettings(models.Model):
    """Configuration settings for quizzes per competency"""
    competency = models.OneToOneField(Competency, on_delete=models.CASCADE, related_name='settings')
    time_limit = models.PositiveIntegerField(default=10, help_text="Time limit in minutes")
    passing_score = models.PositiveIntegerField(
        default=70, 
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Minimum score to pass"
    )
    max_attempts = models.PositiveIntegerField(
        default=3, 
        help_text="Maximum attempts per day"
    )
    question_count = models.PositiveIntegerField(
        default=10, 
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Number of questions per quiz"
    )
    shuffle_questions = models.BooleanField(default=True)
    shuffle_answers = models.BooleanField(default=True)  # Added for answer shuffling
    show_correct_answers = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Made nullable
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Quiz Settings"
    
    def __str__(self):
        return f"Settings for {self.competency.name}"


class QuizAttempt(models.Model):
    """Individual quiz attempts by users"""
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'), 
        ('abandoned', 'Abandoned'),
        ('timed_out', 'Timed Out'),  # Added for timeout scenarios
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='quiz_attempts')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='attempts')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    score = models.FloatField(null=True, blank=True)
    time_taken = models.FloatField(null=True, blank=True, help_text="Time taken in seconds")
    current_question = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, help_text="Stores quiz settings snapshot")
    ip_address = models.GenericIPAddressField(null=True, blank=True)  # Added for security
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['user', 'competency', 'start_time']),
            models.Index(fields=['status', 'start_time']),
        ]
    
    def save(self, *args, **kwargs):
        if self.status in ['completed', 'abandoned', 'timed_out'] and not self.end_time:
            self.end_time = timezone.now()
            if self.start_time and self.end_time:
                self.time_taken = (self.end_time - self.start_time).total_seconds()
        super().save(*args, **kwargs)
    
    @property
    def duration(self):
        """Get duration of the attempt"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return timezone.now() - self.start_time
        return None
    
    @property
    def is_expired(self):
        """Check if quiz attempt has expired based on time limit"""
        if not self.metadata.get('time_limit'):
            return False
        time_limit_seconds = self.metadata['time_limit'] * 60
        duration = self.duration
        return duration and duration.total_seconds() > time_limit_seconds
    
    def __str__(self):
        return f"{self.user.username} - {self.competency.name} Attempt ({self.status})"


class QuizResponse(models.Model):
    """Individual responses to quiz questions"""
    quiz_attempt = models.ForeignKey(
        QuizAttempt, 
        on_delete=models.CASCADE, 
        related_name='responses',
        null=True,      # KEEP THIS - Don't remove
        blank=True      # KEEP THIS - Don't remove
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE, related_name='responses')
    is_correct = models.BooleanField()
    response_time = models.FloatField(help_text="Response time in seconds")
    points_earned = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # TEMPORARILY REMOVE unique_together constraint
        # unique_together = ('quiz_attempt', 'question')  
        indexes = [
            models.Index(fields=['quiz_attempt', 'is_correct']),
        ]
    
    def save(self, *args, **kwargs):
        if self.is_correct:
            self.points_earned = self.question.points
        else:
            self.points_earned = 0
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Response to {self.question.text[:30]} - {'Correct' if self.is_correct else 'Incorrect'}"





# ============================
# LEGACY QUIZ MODEL
# ============================

class QuizAssessment(models.Model):
    """Legacy quiz assessment model - kept for backward compatibility"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='quiz_assessments')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE)
    current_difficulty = models.CharField(max_length=10, choices=Question.DIFFICULTY_CHOICES, default='medium')
    completed = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.competency.name} Quiz (Legacy)"




# ============================
# CODING PROBLEMS
# ============================

# Add these models to your existing models.py

# Add these models to your existing models.py file

class CodingProblem(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    tags = models.CharField(max_length=200)  # Store as comma-separated values
    acceptance_rate = models.FloatField(default=0.0)
    
    # Problem constraints and examples
    constraints = models.TextField(blank=True)
    example_input = models.TextField()
    example_output = models.TextField()
    explanation = models.TextField(blank=True)
    
    # Test cases (we'll store as JSON)
    test_cases = models.JSONField(default=list)  # [{"input": "...", "output": "...", "hidden": false}]
    
    # Problem statistics
    total_submissions = models.PositiveIntegerField(default=0)
    accepted_submissions = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.id}. {self.title}"
    
    @property
    def acceptance_percentage(self):
        if self.total_submissions == 0:
            return 0
        return round((self.accepted_submissions / self.total_submissions) * 100, 1)


class CodeSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('accepted', 'Accepted'),
        ('wrong_answer', 'Wrong Answer'),
        ('runtime_error', 'Runtime Error'),
        ('time_limit_exceeded', 'Time Limit Exceeded'),
        ('compilation_error', 'Compilation Error'),
    ]
    
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('javascript', 'JavaScript'),
        ('java', 'Java'),
        ('cpp', 'C++'),
        ('c', 'C'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='code_submissions')
    problem = models.ForeignKey(CodingProblem, on_delete=models.CASCADE, related_name='submissions')
    code = models.TextField()
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Results
    execution_time = models.FloatField(null=True, blank=True)  # in milliseconds
    memory_used = models.FloatField(null=True, blank=True)    # in MB
    test_results = models.JSONField(default=list)  # Results for each test case
    error_message = models.TextField(blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.problem.title} ({self.status})"

import uuid
from django.db import models
from django.conf import settings

def generate_certificate_id():
    return uuid.uuid4().hex[:8].upper()

class Certificate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    module = models.ForeignKey('Module', on_delete=models.CASCADE, related_name='certificates')
    date_issued = models.DateTimeField(auto_now_add=True)
    certificate_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_certificate_id,
        editable=False
    )
    is_verified = models.BooleanField(default=True)
    pdf_file = models.FileField(upload_to='certificates/pdfs/', null=True, blank=True)

    class Meta:
        unique_together = ('user', 'module')  # One certificate per user per module
        ordering = ['-date_issued']
    
    def __str__(self):
        return f"{self.user.username}'s Certificate for {self.module.name} ({self.certificate_id})"





class Quiz(models.Model):
    title = models.CharField(max_length=200)

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    text = models.TextField()
    correct_answer = models.CharField(max_length=200)

class QuizOption(models.Model):
    question = models.ForeignKey(QuizQuestion, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=200)

class QuizResult(models.Model):
    username = models.CharField(max_length=100)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.IntegerField()
    total = models.IntegerField()
    submitted_at = models.DateTimeField()
