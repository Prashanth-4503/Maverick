from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import logging    

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

    @property
    def total_xp(self):
        """
        Sum XP from coding problem completions only, not from assessments.
        """
        return self.xp_records.aggregate(total=models.Sum('xp'))['total'] or 0
    
    def __str__(self):
        return f"{self.user.email}'s Profile"

class XPRecord(models.Model):
    """
    Keeps track of coding problems the user has earned XP for.
    Prevents awarding XP multiple times for the same problem.
    """
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='xp_records')
    problem_id = models.CharField(max_length=100)  # Store CodingProblem ID
    xp = models.PositiveIntegerField(default=0)  # XP earned for this problem
    earned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user_profile', 'problem_id')  # Prevents duplicate XP

    def __str__(self):
        return f"{self.user_profile.user.email} - {self.problem_id} ({self.xp} XP)"



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
    
    @property
    def enrollment_count(self):
        return self.learningpath_set.count()

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





# ============================
# HACKATHON MODELS
# ============================

# ============================
# ENHANCED HACKATHON MODELS
# ============================

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


# models.py
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

CustomUser = get_user_model()

class Submission(models.Model):
    """
    Represents a user's project submission for a hackathon, including
    both AI-generated and manually evaluated scores.
    """

    class EvaluationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        ERROR = 'error', 'Error'

    # Basic info
    hackathon = models.ForeignKey(
        'Hackathon',
        on_delete=models.CASCADE,
        related_name='ai_project_submissions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    project_title = models.CharField(max_length=200)
    project_description = models.TextField()
    submission_date = models.DateTimeField(auto_now_add=True)
    github_link = models.URLField(blank=True, null=True)
    demo_link = models.URLField(blank=True, null=True)
    submission_file = models.FileField(upload_to='hackathon_submissions/', null=True, blank=True)
    presentation_file = models.FileField(upload_to='hackathon_presentations/', null=True, blank=True)


    # AI evaluation
    evaluation_status = models.CharField(
        max_length=20,
        choices=EvaluationStatus.choices,
        default=EvaluationStatus.PENDING
    )
    ai_evaluation_notes = models.TextField(blank=True, null=True)
    ai_evaluation_score = models.IntegerField(blank=True, null=True)

    # ✅ Manual evaluation fields (added for judges)
    innovation_score = models.FloatField(blank=True, null=True)
    feasibility_score = models.FloatField(blank=True, null=True)
    impact_score = models.FloatField(blank=True, null=True)
    final_score = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"{self.project_title} for {self.hackathon.name} by {self.user.username}"

    class Meta:
        permissions = [
            ('manage_submission', 'Can manage submission as creator'),
        ]




class Hackathon(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('registration_open', 'Registration Open'),
        ('waiting', 'Waiting to Start'),
        ('in_progress', 'In Progress'),
        ('evaluation', 'Under Evaluation'),
        ('completed', 'Completed'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_hackathons')
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_start = models.DateTimeField()
    registration_end = models.DateTimeField()
    
    thumbnail = models.ImageField(upload_to='hackathon_thumbnails/', null=True, blank=True)
    prize = models.TextField(blank=True)
    rules = models.TextField(blank=True)
    
    team_size_min = models.PositiveIntegerField(default=1)
    team_size_max = models.PositiveIntegerField(default=5)
    allow_individual = models.BooleanField(default=True)
    max_participants = models.PositiveIntegerField(default=100)
    
    evaluation_criteria = models.JSONField(default=dict)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    is_active = models.BooleanField(default=True)
    allow_student_creation = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    
    allow_late_submission = models.BooleanField(default=False)
    submission_guidelines = models.TextField(blank=True)
    judging_criteria_weights = models.JSONField(default=dict)
    auto_evaluation = models.BooleanField(default=False)
    
    github_org = models.CharField(max_length=100, blank=True)
    slack_webhook = models.URLField(blank=True)
    discord_webhook = models.URLField(blank=True)
    
    max_file_size_mb = models.PositiveIntegerField(default=50)
    allowed_file_types = models.JSONField(default=list)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['is_active', 'registration_start']),
        ]
        ordering = ['-start_date']
        permissions = [
            ('manage_hackathon', 'Can manage hackathon as creator'),
            ('view_all_hackathons', 'Can view all hackathons'),
        ]

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.allowed_file_types:
            self.allowed_file_types = ['pdf', 'zip', 'tar.gz', 'docx', 'pptx']
        super().save(*args, **kwargs)
    
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
        return (self.start_date <= now <= self.end_date and self.status == 'in_progress') or \
               (self.allow_late_submission and now <= self.end_date + timezone.timedelta(hours=24))
    
    @property
    def registration_status(self):
        now = timezone.now()
        if now < self.registration_start:
            return 'Not Started'
        elif now > self.registration_end:
            return 'Closed'
        elif self.current_participants >= self.max_participants:
            return 'Full'
        else:
            return 'Open'
    
    def is_user_creator(self, user):
        return self.created_by == user
    
    def update_status(self):
        if self.status == 'completed':
            return self.status

        now = timezone.now()
        old_status = self.status
        
        if now < self.registration_start:
            self.status = 'upcoming'
        elif self.registration_start <= now <= self.registration_end:
            self.status = 'registration_open'
        elif self.registration_end < now < self.start_date:
            self.status = 'waiting'
        elif self.start_date <= now <= self.end_date:
            self.status = 'in_progress'
        elif now > self.end_date:
            self.status = 'evaluation'
        
        if self.status != old_status:
            self.save(update_fields=['status', 'updated_at'])
        
        return self.status

    def get_registration_stats(self):
        total_registrations = self.registrations.filter(is_active=True).count()
        team_registrations = self.registrations.filter(is_active=True, team__isnull=False).count()
        individual_registrations = total_registrations - team_registrations
        
        return {
            'total': total_registrations,
            'teams': team_registrations,
            'individuals': individual_registrations,
            'spots_remaining': self.spots_remaining,
            'registration_percentage': round((total_registrations / self.max_participants) * 100, 1) if self.max_participants > 0 else 0
        }

    def get_submission_stats(self):
        submission_queryset = self.user_uploaded_submissions.all()
        
        total_submissions = submission_queryset.count()
        team_submissions = submission_queryset.filter(team__isnull=False).count()
        individual_submissions = total_submissions - team_submissions
        
        return {
            'total': total_submissions,
            'teams': team_submissions,
            'individuals': individual_submissions,
            'evaluated': submission_queryset.filter(final_score__isnull=False).count(),
            'pending_evaluation': submission_queryset.filter(final_score__isnull=True).count(),
            'with_github': submission_queryset.filter(github_url__isnull=False).exclude(github_url='').count()
        }
    
    def get_team_stats(self):
        active_teams = self.teams.filter(is_active=True)
        return {
            'total_teams': active_teams.count(),
            'avg_team_size': active_teams.aggregate(
                avg_size=models.Avg('members__count')
            )['avg_size'] or 0,
        }
    
    def get_timeline_status(self):
        now = timezone.now()
        
        if now < self.registration_start:
            time_until = self.registration_start - now
            return {
                'phase': 'before_registration',
                'status': 'Upcoming',
                'time_remaining': time_until,
                'next_phase': 'Registration Opens',
                'progress_percentage': 0
            }
        elif self.registration_start <= now <= self.registration_end:
            total_reg_time = self.registration_end - self.registration_start
            elapsed_time = now - self.registration_start
            progress = (elapsed_time.total_seconds() / max(total_reg_time.total_seconds(), 1)) * 100
            return {
                'phase': 'registration',
                'status': 'Registration Open',
                'time_remaining': self.registration_end - now,
                'next_phase': 'Hackathon Starts',
                'progress_percentage': min(progress, 100)
            }
        elif self.start_date <= now <= self.end_date:
            total_hack_time = self.end_date - self.start_date
            elapsed_time = now - self.start_date
            progress = (elapsed_time.total_seconds() / max(total_hack_time.total_seconds(), 1)) * 100
            return {
                'phase': 'in_progress',
                'status': 'In Progress',
                'time_remaining': self.end_date - now,
                'next_phase': 'Submission Deadline',
                'progress_percentage': min(progress, 100)
            }
        elif now > self.end_date:
            return {
                'phase': 'completed',
                'status': 'Completed',
                'time_remaining': timezone.timedelta(0),
                'next_phase': 'Results',
                'progress_percentage': 100
            }
        else:
            return {
                'phase': 'waiting',
                'status': 'Waiting to Start',
                'time_remaining': self.start_date - now,
                'next_phase': 'Hackathon Starts',
                'progress_percentage': 0
            }


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
            models.Index(fields=['invite_code']),
        ]
        permissions = [
            ('manage_team', 'Can manage team as creator'),
        ]

    def save(self, *args, **kwargs):
        if not self.invite_code:
            import string
            import random
            self.invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)
        if self.pk:
            self.members.add(self.leader)
    
    @property
    def member_count(self):
        return self.members.count()
    
    @property
    def can_add_members(self):
        return self.member_count < self.hackathon.team_size_max
    
    def can_user_join(self, user):
        return (self.can_add_members and 
                not self.members.filter(id=user.id).exists() and
                not HackathonRegistration.objects.filter(hackathon=self.hackathon, user=user, is_active=True).exists())
    
    def __str__(self):
        return f"{self.hackathon.name} - {self.name}"


class HackathonRegistration(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hackathon_registrations')
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, null=True, blank=True, related_name='registrations')
    
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    skills = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    
    class Meta:
        unique_together = ('hackathon', 'user')
        indexes = [
            models.Index(fields=['hackathon', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
        permissions = [
            ('manage_registration', 'Can manage registration as creator'),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.hackathon.name}"
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class HackathonSubmission(models.Model):
    class EvaluationStatus(models.TextChoices):
        PENDING     = "pending",     "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED   = "completed",   "Completed"
        ERROR       = "error",       "Error"

    # ─────────── relationships ───────────
    hackathon = models.ForeignKey(
        "Hackathon", on_delete=models.CASCADE,
        related_name="user_uploaded_submissions"
    )
    team = models.ForeignKey(
        "HackathonTeam", on_delete=models.CASCADE,
        null=True, blank=True, related_name="submissions"
    )
    individual_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name="individual_submissions"
    )

    # ─────────── main info ───────────
    project_title       = models.CharField(max_length=200)
    project_description = models.TextField()

    # uploads & links
    submission_file   = models.FileField(upload_to="hackathon_submissions/", null=True, blank=True)
    submission_url    = models.URLField(blank=True)
    github_url        = models.URLField(blank=True)
    demo_url          = models.URLField(blank=True)
    video_demo_url    = models.URLField(blank=True)
    live_demo_url     = models.URLField(blank=True)
    presentation_file = models.FileField(upload_to="presentations/", null=True, blank=True)

    # automatic metrics
    plagiarism_score  = models.FloatField(null=True, blank=True)
    code_quality_score = models.FloatField(null=True, blank=True)

    # manual rubric (three criteria, 0-100 each)
    innovation_score  = models.FloatField(null=True, blank=True)
    feasibility_score = models.FloatField(null=True, blank=True)
    impact_score      = models.FloatField(null=True, blank=True)

    # JSON extras
    submission_metadata = models.JSONField(default=dict)
    scores              = models.JSONField(default=dict)

    # derived totals
    final_score         = models.FloatField(null=True, blank=True)   # shown to admins
    ai_evaluation_score = models.FloatField(null=True, blank=True)   # shown on public results

    feedback = models.TextField(blank=True)

    evaluation_status = models.CharField(
        max_length=20, choices=EvaluationStatus.choices,
        default=EvaluationStatus.PENDING
    )
    ai_evaluation_notes = models.TextField(blank=True, null=True)
    
    # ✅ NEW FIELD: Track if AI evaluation was triggered
    ai_evaluation_triggered = models.BooleanField(default=False)

    # ranking / winners
    rank          = models.PositiveIntegerField(null=True, blank=True)
    is_winner     = models.BooleanField(default=False)
    prize_category = models.CharField(max_length=100, blank=True)

    # bookkeeping
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    # ─────────── Meta & validation ───────────
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(team__isnull=False, individual_user__isnull=True) |
                    models.Q(team__isnull=True,  individual_user__isnull=False)
                ),
                name="either_team_or_individual",
            )
        ]
        unique_together = [
            ("hackathon", "team"),
            ("hackathon", "individual_user"),
        ]
        indexes = [
            models.Index(fields=["hackathon", "final_score"]),
            models.Index(fields=["hackathon", "submitted_at"]),
            models.Index(fields=["team"]),
            models.Index(fields=["individual_user"]),
        ]
        ordering = ["-final_score", "-submitted_at"]
        permissions = [
            ("manage_submission",   "Can manage submission as creator"),
            ("evaluate_submission", "Can evaluate submission"),
        ]

    def clean(self):
        super().clean()
        if not self.team and not self.individual_user:
            raise ValidationError("Either team or individual_user must be specified.")
        if self.team and self.individual_user:
            raise ValidationError("Cannot specify both team and individual_user.")

    # ✅ UPDATED save method with auto-trigger
    def save(self, *args, **kwargs):
        """Auto-trigger AI evaluation on first save"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Trigger AI evaluation for new submissions with files
        if is_new and self.submission_file and not self.ai_evaluation_triggered:
            self.trigger_ai_evaluation()

    def trigger_ai_evaluation(self):
        """Trigger AI evaluation for this submission"""
        if not self.ai_evaluation_triggered and self.submission_file:
            self.ai_evaluation_triggered = True
            self.evaluation_status = self.EvaluationStatus.PENDING
            self.save(update_fields=['ai_evaluation_triggered', 'evaluation_status'])
            
            # Import here to avoid circular imports
            try:
                from .views import evaluate_submission_task
                evaluate_submission_task(self.id)
            except Exception as e:
                logger.error(f"Failed to trigger AI evaluation for submission {self.id}: {e}")

    # convenience helpers
    @property
    def submitter_name(self):
        return self.team.name if self.team else (self.individual_user.username if self.individual_user else "Unknown")

    @property
    def total_file_size(self):
        size = (self.submission_file.size if self.submission_file else 0) + \
               (self.presentation_file.size if self.presentation_file else 0)
        if hasattr(self, "files"):
            size += sum(f.file_size or 0 for f in self.files.all())
        return size

    def __str__(self):
        return f"{self.project_title} – {self.hackathon.name}"
    


class HackathonSubmissionFile(models.Model):
    submission = models.ForeignKey(HackathonSubmission, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='hackathon_files/%Y/%m/%d/')
    file_type = models.CharField(max_length=20, choices=[
        ('source', 'Source Code'),
        ('documentation', 'Documentation'),
        ('presentation', 'Presentation'),
        ('demo', 'Demo Video'),
        ('other', 'Other')
    ])
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        permissions = [
            ('manage_submission_file', 'Can manage submission file as creator'),
        ]

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.submission.project_title} - {self.get_file_type_display()}"


class HackathonEvaluation(models.Model):
    submission = models.ForeignKey(HackathonSubmission, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hackathon_evaluations')
    
    scores = models.JSONField(default=dict)
    comments = models.TextField(blank=True)
    recommendation = models.CharField(max_length=50, choices=[
        ('highly_recommended', 'Highly Recommended'),
        ('recommended', 'Recommended'),
        ('average', 'Average'),
        ('needs_improvement', 'Needs Improvement'),
        ('not_recommended', 'Not Recommended')
    ], blank=True)
    
    evaluated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('submission', 'evaluator')
        indexes = [
            models.Index(fields=['submission', 'evaluator']),
        ]
        permissions = [
            ('manage_evaluation', 'Can manage evaluation as creator'),
        ]

    @property
    def total_score(self):
        return sum(self.scores.values()) if self.scores else 0
    
    def __str__(self):
        return f"Evaluation by {self.evaluator.username} for {self.submission.project_title}"


class GitHubRepository(models.Model):
    submission = models.OneToOneField(HackathonSubmission, on_delete=models.CASCADE, related_name='github_repository')
    repo_url = models.URLField()
    repo_owner = models.CharField(max_length=100)
    repo_name = models.CharField(max_length=100)
    last_commit_hash = models.CharField(max_length=40, blank=True)
    commit_count = models.IntegerField(default=0)
    contributors = models.JSONField(default=list)
    languages = models.JSONField(default=dict)
    verified_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        permissions = [
            ('manage_github_repo', 'Can manage GitHub repository as creator'),
        ]

    def __str__(self):
        return f"{self.repo_owner}/{self.repo_name}"
    
    def verify_repository(self):
        self.is_verified = True
        self.save(update_fields=['is_verified', 'verified_at'])


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
# CODING PROBLEMS - PROFESSIONAL VERSION
# ============================

class CodingProblem(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    # Basic Problem Information
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    tags = models.CharField(max_length=200)  # Store as comma-separated values
    
    # Problem Examples (for display only)
    example_input = models.TextField()
    example_output = models.TextField()
    explanation = models.TextField(blank=True)
    constraints = models.TextField(blank=True)
    
    # Professional Function Signature Info
    function_name = models.CharField(max_length=100, default="solution")
    function_params = models.JSONField(default=list)
    return_type = models.CharField(max_length=100, default="List[int]")
    
    # Professional Test Cases Format
    test_cases = models.JSONField(default=list)
    
    # Problem Statistics
    total_submissions = models.PositiveIntegerField(default=0)
    accepted_submissions = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['difficulty', 'is_active']),
        ]
    
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
    
    # Execution Results
    execution_time = models.FloatField(null=True, blank=True)  # in milliseconds
    memory_used = models.FloatField(null=True, blank=True)    # in MB
    test_results = models.JSONField(default=list)  # Results for each test case
    error_message = models.TextField(blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['user', 'submitted_at']),
            models.Index(fields=['problem', 'status']),
        ]
    
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

from django.db import models
from django.conf import settings

class ModuleVisit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    module = models.ForeignKey('Module', on_delete=models.CASCADE)
    last_visited = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'module')

    def __str__(self):
        return f"{self.user.username} visited {self.module.name} on {self.last_visited}"


from django.core.validators import FileExtensionValidator
class Resume(models.Model):
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='resumes'
    )
    resume_file = models.FileField(
        upload_to='resumes/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'txt'])]
    )
    extracted_skills = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Resume"
        verbose_name_plural = "Resumes"

    def __str__(self):
        return f"Resume of {self.user.email} uploaded at {self.uploaded_at}"
    
    def delete(self, *args, **kwargs):
        """Delete the file when the model instance is deleted"""
        storage, path = self.resume_file.storage, self.resume_file.path
        super().delete(*args, **kwargs)
        storage.delete(path)


# ============================
# CHATBOT
# ============================
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
import json

# Use settings.AUTH_USER_MODEL instead of direct User import
User = get_user_model()

# Your existing CodingProblem, CodeSubmission models...

class ChatConversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # ✅ FIXED
    problem = models.ForeignKey('CodingProblem', on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
        unique_together = ['user', 'problem']
    
    def __str__(self):
        return f"{self.user.username} - {self.problem.title}"

class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System')
    ]
    
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

class UserProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # ✅ FIXED
    problem = models.ForeignKey('CodingProblem', on_delete=models.CASCADE)
    hints_used = models.IntegerField(default=0)
    stuck_count = models.IntegerField(default=0)
    last_hint_time = models.DateTimeField(null=True, blank=True)
    approaches_discussed = models.JSONField(default=list, blank=True)
    
    class Meta:
        unique_together = ['user', 'problem']
    
    def __str__(self):
        return f"{self.user.username} - {self.problem.title} (Hints: {self.hints_used})"