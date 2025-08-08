from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import *

from .models import CustomUser, OTP
import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError










from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import TempUserRegistration, OTP
from django.utils import timezone
from django.forms import ModelForm, FloatField
import json

class TempRegistrationForm(forms.Form):
    email = forms.EmailField()
    username = forms.CharField(max_length=150)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    profile_picture = forms.ImageField(required=False)

    def clean_email(self):
        email = self.cleaned_data['email']
        if TempUserRegistration.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email is being registered.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        validate_password(password2)
        return password2

class OTPVerificationFormTemp(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput())
    otp = forms.CharField(max_length=6)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        otp = cleaned_data.get('otp')

        if not OTP.objects.filter(email=email, code=otp, expires_at__gte=timezone.now()).exists():
            raise forms.ValidationError("Invalid or expired OTP.")
        return cleaned_data







class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    profile_picture = forms.ImageField(required=False)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 'profile_picture']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already in use. Please use a different email.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username is required.")
        return username
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        
        # Custom password validation that skips common password and numeric checks
        try:
            # Create a custom password validator that excludes the validators we don't want
            from django.contrib.auth.password_validation import (
                MinimumLengthValidator,
                UserAttributeSimilarityValidator
            )
            
            # Use only these validators
            custom_validators = [
                MinimumLengthValidator(),
                UserAttributeSimilarityValidator()
            ]
            
            # Apply our custom validators
            for validator in custom_validators:
                validator.validate(password2, self.instance)
                
        except ValidationError as error:
            self.add_error('password2', error)
        
        return password2
    
    def _post_clean(self):
        super()._post_clean()
        # Remove any password1 errors since we're handling all validation in password2
        if 'password1' in self.errors:
            del self.errors['password1']

class EmailLoginForm(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(max_length=6, required=True)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp')
        if self.user:
            valid_otp = OTP.objects.filter(
                user=self.user,
                code=otp,
                expires_at__gte=timezone.now()
            ).exists()
            if not valid_otp:
                raise forms.ValidationError("Invalid or expired OTP.")
        return otp

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['name', 'assessment_type', 'file']
        widgets = {
            'assessment_type': forms.Select(attrs={'class': 'form-select'}),
        }

# class HackathonCreateForm(forms.ModelForm):
#     evaluation_criteria = forms.CharField(
#         widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter criteria as JSON, e.g., {"Innovation": 25, "Technical Implementation": 25, "Presentation": 25, "Impact": 25}'}),
#         help_text="JSON format with criterion names and maximum scores"
#     )
    
#     class Meta:
#         model = Hackathon
#         fields = [
#             'name', 'description', 'start_date', 'end_date',
#             'registration_start', 'registration_end',
#             'thumbnail', 'prize', 'rules',
#             'max_participants', 'team_size_min', 'team_size_max',
#             'allow_individual', 'evaluation_criteria'
#         ]
#         widgets = {
#             'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
#             'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
#             'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
#             'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
#             'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
#             'rules': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
#             'prize': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
#         }
    
#     def clean_evaluation_criteria(self):
#         criteria = self.cleaned_data['evaluation_criteria']
#         try:
#             import json
#             parsed = json.loads(criteria)
#             if not isinstance(parsed, dict):
#                 raise forms.ValidationError("Criteria must be a JSON object")
#             for key, value in parsed.items():
#                 if not isinstance(value, (int, float)) or value <= 0:
#                     raise forms.ValidationError(f"Score for '{key}' must be a positive number")
#             return parsed
#         except json.JSONDecodeError:
#             raise forms.ValidationError("Invalid JSON format")

# class HackathonTeamForm(forms.ModelForm):
#     class Meta:
#         model = HackathonTeam
#         fields = ['name', 'description']
#         widgets = {
#             'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Team name'}),
#             'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Team description (optional)'}),
#         }

# class HackathonSubmissionForm(forms.ModelForm):
#     class Meta:
#         model = HackathonSubmission
#         fields = [
#             'project_title', 'project_description',
#             'submission_file', 'submission_url',
#             'github_url', 'demo_url'
#         ]
#         widgets = {
#             'project_title': forms.TextInput(attrs={'class': 'form-control'}),
#             'project_description': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
#             'submission_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
#             'github_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/'}),
#             'demo_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
#         }

# class HackathonEvaluationForm(forms.Form):
#     def __init__(self, *args, **kwargs):
#         criteria = kwargs.pop('criteria', {})
#         super().__init__(*args, **kwargs)
        
#         for criterion, max_score in criteria.items():
#             self.fields[f'score_{criterion}'] = forms.FloatField(
#                 label=f"{criterion} (Max: {max_score})",
#                 min_value=0,
#                 max_value=max_score,
#                 widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'})
#             )
        
#         self.fields['comments'] = forms.CharField(
#             widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
#             required=False
#         )

# class TeamJoinForm(forms.Form):
#     invite_code = forms.CharField(
#         max_length=20,
#         widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter team invite code'})
#     )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['skills', 'experience_level']

class LearningPathForm(forms.ModelForm):
    class Meta:
        model = LearningPath
        fields = ['status', 'progress']



from django import forms
from django.core.validators import FileExtensionValidator
from .models import Resume, UserProfile, CustomUser
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'profile_picture', 'bio')

class UserUpdateForm(forms.ModelForm):
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
    )
    
    class Meta:
        model = CustomUser
        fields = ['email', 'username', 'first_name', 'last_name', 'profile_picture', 'bio']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'disabled': 'disabled'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True
    
from django import forms
from .models import CustomUser, UserProfile, Resume

class ProfileUpdateForm(forms.ModelForm):
    skills = forms.CharField(required=False)
    experience_level = forms.CharField(required=False)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'profile_picture', 'bio']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self.instance, 'profile'):
            self.fields['skills'].initial = self.instance.profile.skills
            self.fields['experience_level'].initial = self.instance.profile.experience_level
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.skills = self.cleaned_data['skills']
            profile.experience_level = self.cleaned_data['experience_level']
            profile.save()
        return user

class ResumeUploadForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['resume_file']
        widgets = {
            'resume_file': forms.FileInput(attrs={'accept': '.pdf,.txt'})
        }
    
    def clean_resume_file(self):
        file = self.cleaned_data.get('resume_file')
        if file:
            # Validate file size (5MB max)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File too large (max 5MB)")
            return file



# ============================================
# HACKATHON FORMS (Enhanced and Fixed)
# ============================================

class ManualScoreForm(ModelForm):
    """Form used on /hackathon/<id>/evaluate/."""
    overall_score = FloatField(
        required=False, min_value=0, max_value=100, label="Overall (0-100)"
    )

    class Meta:
        model  = HackathonSubmission
        fields = ["innovation_score", "feasibility_score", "impact_score"]
        labels = {
            "innovation_score":  "Innovation (0-100)",
            "feasibility_score": "Feasibility (0-100)",
            "impact_score":      "Impact (0-100)",
        }

    # validate & compute total
    def clean(self):
        cleaned = super().clean()

        overall = cleaned.get("overall_score")
        inv = cleaned.get("innovation_score")  or 0
        fea = cleaned.get("feasibility_score") or 0
        imp = cleaned.get("impact_score")      or 0
        any_rubric = any([inv, fea, imp])

        if overall is None and not any_rubric:
            raise ValidationError("Enter an overall score OR at least one rubric score.")

        if overall is None:
            overall = round((inv + fea + imp) / 3, 1)

        cleaned["calculated_overall"] = overall
        return cleaned
    
    
class SubmissionFileForm(forms.Form):
    project_files = forms.FileField(label="Upload your project files (.zip)")

# BASIC HACKATHON CREATE FORM (For compatibility)
class HackathonCreateForm(forms.ModelForm):
    """Basic hackathon creation form - maintains backward compatibility"""
    evaluation_criteria = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4, 
            'placeholder': 'Enter criteria as JSON, e.g., {"Innovation": 25, "Technical Implementation": 25, "Presentation": 25, "Impact": 25}',
            'class': 'form-control'
        }),
        help_text="JSON format with criterion names and maximum scores"
    )
    
    class Meta:
        model = Hackathon
        fields = [
            'name', 'description', 'start_date', 'end_date',
            'registration_start', 'registration_end',
            'thumbnail', 'prize', 'rules',
            'max_participants', 'team_size_min', 'team_size_max',
            'allow_individual', 'evaluation_criteria'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'rules': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'prize': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'team_size_min': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'team_size_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
    
    def clean_evaluation_criteria(self):
        criteria = self.cleaned_data['evaluation_criteria']
        try:
            parsed = json.loads(criteria)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Criteria must be a JSON object")
            for key, value in parsed.items():
                if not isinstance(value, (int, float)) or value <= 0:
                    raise forms.ValidationError(f"Score for '{key}' must be a positive number")
            return parsed
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format")


# 🚀 ENHANCED HACKATHON CREATE FORM (Fixed and Complete)
class EnhancedHackathonCreateForm(forms.ModelForm):
    """Enhanced hackathon creation form with API integration and advanced features"""
    
    # Basic evaluation criteria (inheriting validation from parent)
    evaluation_criteria = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4, 
            'placeholder': '{"Innovation": 25, "Technical Implementation": 25, "Presentation": 25, "Impact": 25}',
            'class': 'form-control'
        }),
        help_text="JSON format with criterion names and maximum scores"
    )
    
    # 🚀 API Integration Fields
    slack_webhook = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control', 
            'placeholder': 'https://hooks.slack.com/services/...'
        }),
        help_text="Optional: Slack webhook for real-time notifications"
    )
    
    discord_webhook = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control', 
            'placeholder': 'https://discord.com/api/webhooks/...'
        }),
        help_text="Optional: Discord webhook for notifications"
    )
    
    github_org = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'organization-name'
        }),
        help_text="Optional: GitHub organization for repository verification"
    )
    
    # 🚀 Submission Guidelines
    submission_guidelines = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Specific requirements for submissions (file formats, naming conventions, etc.)'
        }),
        help_text="Additional guidelines for project submissions"
    )
    
    # 🚀 File Management Fields
    max_file_size_mb = forms.IntegerField(
        initial=50,
        min_value=1,
        max_value=500,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '500'
        }),
        help_text="Maximum file size allowed for submissions (in MB)"
    )
    
    allowed_file_types = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'pdf,zip,tar.gz,docx,pptx'
        }),
        help_text="Comma-separated list of allowed file extensions"
    )
    
    # 🚀 Advanced Settings
    allow_late_submission = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Allow submissions up to 24 hours after deadline"
    )
    
    auto_evaluation = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Enable automatic code quality evaluation (requires GitHub integration)"
    )
    
    class Meta:
        model = Hackathon
        fields = [
            # Basic fields
            'name', 'description', 'start_date', 'end_date',
            'registration_start', 'registration_end',
            'thumbnail', 'prize', 'rules',
            'max_participants', 'team_size_min', 'team_size_max',
            'allow_individual', 'evaluation_criteria',
            # Enhanced fields
            'submission_guidelines',
            'slack_webhook', 'discord_webhook', 'github_org',
            'max_file_size_mb', 'allowed_file_types',
            'allow_late_submission', 'auto_evaluation'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'rules': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'prize': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'team_size_min': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'team_size_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
    
    def clean_evaluation_criteria(self):
        """Enhanced validation with total score check"""
        criteria = self.cleaned_data['evaluation_criteria']
        try:
            parsed = json.loads(criteria)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Criteria must be a JSON object")
            
            total_score = 0
            for key, value in parsed.items():
                if not isinstance(value, (int, float)) or value <= 0:
                    raise forms.ValidationError(f"Score for '{key}' must be a positive number")
                total_score += value
            
            return parsed
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format")
    
    def clean_allowed_file_types(self):
        file_types = self.cleaned_data.get('allowed_file_types', '')
        if file_types:
            types_list = [ext.strip().lower() for ext in file_types.split(',') if ext.strip()]
            
            valid_extensions = [
                'pdf', 'doc', 'docx', 'txt', 'zip', 'tar.gz', 'rar',
                'jpg', 'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov',
                'ppt', 'pptx', 'xlsx', 'xls', 'csv'
            ]
            
            for ext in types_list:
                if ext not in valid_extensions:
                    raise forms.ValidationError(f"'{ext}' is not a supported file type")
            
            return types_list
        return ['pdf', 'zip', 'tar.gz', 'docx', 'pptx']
    
    def clean_slack_webhook(self):
        webhook = self.cleaned_data.get('slack_webhook')
        if webhook and not webhook.startswith('https://hooks.slack.com/'):
            raise forms.ValidationError("Please provide a valid Slack webhook URL")
        return webhook
    
    def clean_discord_webhook(self):
        webhook = self.cleaned_data.get('discord_webhook')
        if webhook and not webhook.startswith('https://discord.com/api/webhooks/'):
            raise forms.ValidationError("Please provide a valid Discord webhook URL")
        return webhook
    
    def clean_github_org(self):
        org = self.cleaned_data.get('github_org')
        if org and not org.replace('-', '').replace('_', '').isalnum():
            raise forms.ValidationError("Invalid GitHub organization name")
        return org
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Enhanced date validation
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        reg_start = cleaned_data.get('registration_start')
        reg_end = cleaned_data.get('registration_end')
        
        if all([start_date, end_date, reg_start, reg_end]):
            if reg_start >= reg_end:
                raise forms.ValidationError("Registration end must be after registration start")
            if reg_end > start_date:
                raise forms.ValidationError("Hackathon must start after registration ends")
            if start_date >= end_date:
                raise forms.ValidationError("End date must be after start date")
        
        return cleaned_data


# BASIC SUBMISSION FORM (For compatibility)
# forms.py - Updated version
from django import forms
from django.core.exceptions import ValidationError
from .models import HackathonSubmission
import logging

logger = logging.getLogger(__name__)

from django import forms
from .models import HackathonSubmission

class HackathonSubmissionForm(forms.ModelForm):
    class Meta:
        model = HackathonSubmission
        fields = ['project_title', 'project_description', 'submission_file', 'github_url', 'demo_url']
        widgets = {
            'project_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your project title'
            }),
            'project_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your project'
            }),
            'submission_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.zip'
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/username/repository'
            }),
            'demo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-demo-link.com'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.hackathon = kwargs.pop('hackathon', None)
        self.user_registration = kwargs.pop('user_registration', None)
        self.is_update = kwargs.pop('is_update', False)
        super().__init__(*args, **kwargs)
        
        # Make title and description readonly if they're pre-filled from AI
        if self.initial and self.initial.get('project_title'):
            self.fields['project_title'].widget.attrs['readonly'] = True
            self.fields['project_description'].widget.attrs['readonly'] = True



# 🚀 ENHANCED SUBMISSION FORM (Complete version)
class EnhancedHackathonSubmissionForm(forms.ModelForm):
    """Enhanced submission form with all fields and validation"""
    
    # ✅ SIMPLE VERSION - No multiple files for now
    additional_files = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Describe additional files you have (optional)'
        }),
        help_text="Describe any additional files you have (you can upload them via GitHub or other means)"
    )
    
    class Meta:
        model = HackathonSubmission
        fields = [
            'project_title', 'project_description',
            'submission_file', 'submission_url',
            'github_url', 'demo_url',
            # Comment out fields that might not exist in your model
            # 'video_demo_url', 'live_demo_url', 'presentation_file'
        ]
        widgets = {
            'project_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your project title'
            }),
            'project_description': forms.Textarea(attrs={
                'rows': 6, 
                'class': 'form-control',
                'placeholder': 'Describe your project, technologies used, challenges faced, etc.'
            }),
            'submission_file': forms.FileInput(attrs={'class': 'form-control'}),
            'submission_url': forms.URLInput(attrs={
                'class': 'form-control', 
                'placeholder': 'https://example.com (optional)'
            }),
            'github_url': forms.URLInput(attrs={
                'class': 'form-control', 
                'placeholder': 'https://github.com/username/repository'
            }),
            'demo_url': forms.URLInput(attrs={
                'class': 'form-control', 
                'placeholder': 'https://demo-link.com (optional)'
            }),
        }
    
    def clean_github_url(self):
        github_url = self.cleaned_data.get('github_url')
        if github_url and 'github.com' not in github_url:
            raise forms.ValidationError("Please provide a valid GitHub repository URL")
        return github_url
    
    def clean_submission_file(self):
        file = self.cleaned_data.get('submission_file')
        if file:
            max_size = 50 * 1024 * 1024  # 50MB
            if file.size > max_size:
                raise forms.ValidationError(f"File size exceeds 50MB limit. Current size: {file.size // (1024*1024)}MB")
        return file



# TEAM FORMS (Enhanced but backward compatible)
class HackathonTeamForm(forms.ModelForm):
    class Meta:
        model = HackathonTeam
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter team name',
                'maxlength': '100'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control', 
                'placeholder': 'Describe your team and what you\'re looking for in members (optional)'
            }),
        }
    
    def clean_name(self):
        name = self.cleaned_data['name']
        if len(name.strip()) < 3:
            raise forms.ValidationError("Team name must be at least 3 characters long")
        return name.strip()


class TeamJoinForm(forms.Form):
    invite_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Enter 8-character team invite code',
            'pattern': '[A-Z0-9]{8}',
            'title': 'Invite code should be 8 characters (letters and numbers)'
        }),
        help_text="Ask your team leader for the invite code"
    )
    
    def clean_invite_code(self):
        code = self.cleaned_data['invite_code'].upper().strip()
        if len(code) != 8:
            raise forms.ValidationError("Invite code must be exactly 8 characters")
        if not code.isalnum():
            raise forms.ValidationError("Invite code can only contain letters and numbers")
        return code


# EVALUATION FORMS (Enhanced but backward compatible)
class HackathonEvaluationForm(forms.ModelForm):
    """Model form for saving evaluations"""
    class Meta:
        model = HackathonEvaluation
        fields = ['comments', 'scores']  # scores will be stored as JSON

    def clean_scores(self):
        scores = self.cleaned_data.get('scores', {})
        try:
            # Validate scores structure
            if not isinstance(scores, dict):
                raise forms.ValidationError("Scores must be a dictionary")
            return json.dumps(scores)
        except (TypeError, ValueError):
            raise forms.ValidationError("Invalid scores format")



# 🚀 NEW ADDITIONAL FORMS

class HackathonRegistrationForm(forms.Form):
    """Enhanced registration confirmation form"""
    agree_to_rules = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree to follow all hackathon rules and guidelines"
    )
    
    emergency_contact = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Emergency contact name and phone (optional)'
        })
    )
    
    dietary_restrictions = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Any dietary restrictions or allergies (optional)'
        })
    )
    
    skills = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Your skills and technologies you\'re familiar with (optional)'
        })
    )


class BulkEvaluationForm(forms.Form):
    """Form for bulk operations on submissions"""
    action = forms.ChoiceField(
        choices=[
            ('', 'Select action'),
            ('mark_evaluated', 'Mark as Evaluated'),
            ('export_csv', 'Export to CSV'),
            ('send_feedback', 'Send Feedback Emails')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    submissions = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )



class HackathonFilterForm(forms.Form):
    """Form for filtering hackathons"""
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('upcoming', 'Upcoming'),
        ('registration_open', 'Registration Open'),
        ('in_progress', 'In Progress'),
        ('evaluation', 'Under Evaluation'),
        ('completed', 'Completed'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('', 'All Difficulties'),
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search hackathons...'
        })
    )
    
    min_prize = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum prize amount'
        })
    )


from django import forms
from .models import HackathonSubmission

class WinnerSelectionForm(forms.Form):
    PRIZE_CATEGORIES = [
        ('first_place', '🥇 1st Place'),
        ('second_place', '🥈 2nd Place'),
        ('third_place', '🥉 3rd Place'),
        ('best_innovation', '💡 Best Innovation'),
        ('best_design', '🎨 Best Design'),
        ('peoples_choice', '👥 People\'s Choice'),
        ('special_recognition', '🏆 Special Recognition'),
    ]
    
    submission_id = forms.IntegerField(widget=forms.HiddenInput())
    prize_category = forms.ChoiceField(
        choices=PRIZE_CATEGORIES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    announcement_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional announcement message for this winner...'
        })
    )



# ============================================
# CODING PROBLEM FORMS
# ============================================

class CodeSubmissionForm(forms.ModelForm):
    """Form for submitting code solutions"""
    class Meta:
        model = CodeSubmission
        fields = ['code', 'language']
        widgets = {
            'code': forms.Textarea(attrs={
                'rows': 20,
                'class': 'form-control',
                'style': 'font-family: monospace;',
                'placeholder': 'Write your solution here...'
            }),
            'language': forms.Select(attrs={'class': 'form-control'})
        }


class CodingProblemFilterForm(forms.Form):
    """Form for filtering coding problems"""
    DIFFICULTY_CHOICES = [
        ('', 'All Difficulties'),
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    difficulty = forms.ChoiceField(
        choices=DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by tags (e.g., array, string, dynamic-programming)'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search problems...'
        })
    )


# ============================================
# QUIZ FORMS
# ============================================

class QuizStartForm(forms.Form):
    """Form to start a quiz"""
    competency_id = forms.IntegerField(widget=forms.HiddenInput())
    agree_to_rules = forms.BooleanField(
        required=True,
        label="I understand the quiz rules and time limits"
    )


class QuizAnswerForm(forms.Form):
    """Form for submitting quiz answers"""
    def __init__(self, *args, **kwargs):
        question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        
        if question:
            choices = [(answer.id, answer.text) for answer in question.answers.all()]
            self.fields['answer'] = forms.ChoiceField(
                choices=choices,
                widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                required=True
            )
