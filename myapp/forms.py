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

class HackathonCreateForm(forms.ModelForm):
    evaluation_criteria = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Enter criteria as JSON, e.g., {"Innovation": 25, "Technical Implementation": 25, "Presentation": 25, "Impact": 25}'}),
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
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_start': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'registration_end': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'rules': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'prize': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def clean_evaluation_criteria(self):
        criteria = self.cleaned_data['evaluation_criteria']
        try:
            import json
            parsed = json.loads(criteria)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Criteria must be a JSON object")
            for key, value in parsed.items():
                if not isinstance(value, (int, float)) or value <= 0:
                    raise forms.ValidationError(f"Score for '{key}' must be a positive number")
            return parsed
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format")

class HackathonTeamForm(forms.ModelForm):
    class Meta:
        model = HackathonTeam
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Team name'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Team description (optional)'}),
        }

class HackathonSubmissionForm(forms.ModelForm):
    class Meta:
        model = HackathonSubmission
        fields = [
            'project_title', 'project_description',
            'submission_file', 'submission_url',
            'github_url', 'demo_url'
        ]
        widgets = {
            'project_title': forms.TextInput(attrs={'class': 'form-control'}),
            'project_description': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'submission_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://github.com/'}),
            'demo_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
        }

class HackathonEvaluationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        criteria = kwargs.pop('criteria', {})
        super().__init__(*args, **kwargs)
        
        for criterion, max_score in criteria.items():
            self.fields[f'score_{criterion}'] = forms.FloatField(
                label=f"{criterion} (Max: {max_score})",
                min_value=0,
                max_value=max_score,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'})
            )
        
        self.fields['comments'] = forms.CharField(
            widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            required=False
        )

class TeamJoinForm(forms.Form):
    invite_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter team invite code'})
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['skills', 'experience_level']

class LearningPathForm(forms.ModelForm):
    class Meta:
        model = LearningPath
        fields = ['status', 'progress']