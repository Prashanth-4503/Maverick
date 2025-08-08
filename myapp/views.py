import zipfile
import tempfile
from django.views.decorators.cache import never_cache
from datetime import datetime, timedelta  # ✅ correct import


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from myapp.forms import HackathonSubmissionForm
import zipfile
from django.db import models
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.conf import settings
from .forms import EnhancedHackathonCreateForm, EnhancedHackathonSubmissionForm, HackathonEvaluationForm
from .evaluator import evaluate_submission_task
# import datetime
import json
import random
from .models import *
import requests
from .forms import *
from django.core.mail import send_mail
from django import forms
import json
# ==========================
# General Views and Utilities
# ==========================

def index_view(request):
    return render(request, 'index.html')

def home_view(request):
    return render(request, 'base.html')

def is_admin(user):
    return user.is_authenticated and user.is_admin

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if not seconds:
        return "0 seconds"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes > 0:
        return f"{minutes}m {remaining_seconds}s"
    else:
        return f"{remaining_seconds}s"

# -------------------
# Authentication Views
# -------------------
from django.utils import timezone
from datetime import timedelta
from .models import TempUserRegistration

def delete_expired_temp_users():
    expiry_time = timezone.now() - timedelta(seconds=10)
    expired_users = TempUserRegistration.objects.filter(created_at__lt=expiry_time)
    print(f"Found {expired_users.count()} expired users")
    expired_users.delete()



from django.core.files.uploadedfile import InMemoryUploadedFile
import base64
import io
from PIL import Image
from .forms import TempRegistrationForm, OTPVerificationFormTemp
from .models import TempUserRegistration, OTP, CustomUser

def register_view(request):
    delete_expired_temp_users()
    if request.method == 'POST':
        form = TempRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data['email']
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            profile_picture = form.cleaned_data['profile_picture']

            # Save temp user to DB
            TempUserRegistration.objects.update_or_create(
                email=email,
                defaults={
                    'username': username,
                    'password': password,
                    'profile_picture': profile_picture
                }
            )

            # Generate OTP
            otp_code = str(random.randint(100000, 999999))
            expires_at = timezone.now() + timedelta(minutes=10)

            # Save OTP to session
            request.session['temp_user_data'] = {
                'email': email,
                'username': username,
                'password': password
            }
            if profile_picture:
                image_data = base64.b64encode(profile_picture.read()).decode('utf-8')
                request.session['profile_picture'] = image_data

            request.session['otp_code'] = otp_code
            request.session['otp_expires_at'] = expires_at.isoformat()

            # Send OTP email
            send_mail(
                subject='Your OTP Code',
                message=f'Your OTP is {otp_code}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False
            )

            return redirect('verify_email')
    else:
        form = TempRegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


from django.contrib.auth import get_user_model
from myapp.models import TempUserRegistration  # adjust to your actual app name
import base64

User = get_user_model()

def verify_otp_view(request):
    if request.method == "POST":
        otp_entered = request.POST.get('otp')
        session_data = request.session.get('temp_user_data', {})
        session_otp = request.session.get('otp_code')
        email = session_data.get('email')

        try:
            temp_user = TempUserRegistration.objects.get(email=email)
        except TempUserRegistration.DoesNotExist:
            messages.error(request, "Session expired. Please register again.")
            return redirect('register')

        if session_otp != otp_entered:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'verify_otp.html', {'email': email})

        # ✅ Create the actual user (replace with your model if not using default User)
        user = User.objects.create_user(
            username=session_data['username'],
            email=email,
            password=session_data['password']
        )

        # ✅ Handle the profile picture from session (optional)
        image_data = request.session.get('profile_picture')
        if image_data:
            image_bytes = base64.b64decode(image_data)
            file_name = f"{user.username}_profile.jpg"
            user.profile_picture.save(file_name, ContentFile(image_bytes), save=True)

        user.save()

        # ✅ Delete the temp user record
        temp_user.delete()

        # ✅ Clean up session
        request.session.flush()

        messages.success(request, "Registration successful. You can now log in.")
        return redirect('login')

    return redirect('register')






def verify_email(request):
    if 'temp_user_data' not in request.session:
        return redirect('register')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored_otp = request.session.get('otp_code')
        expires_at = datetime.fromisoformat(request.session.get('otp_expires_at'))

        if timezone.now() > expires_at:
            messages.error(request, 'OTP has expired. Please register again.')
            return redirect('register')

        if entered_otp == stored_otp:
            data = request.session['temp_user_data']

            # Create user
            user = CustomUser.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                is_verified=True,
            )

            # Restore profile picture if uploaded
            profile_pic_data = request.session.get('profile_picture')
            if profile_pic_data:
                image_data = base64.b64decode(profile_pic_data)
                image_file = InMemoryUploadedFile(
                    io.BytesIO(image_data), None, 'profile.jpg', 'image/jpeg', len(image_data), None
                )
                user.profile_picture = image_file
                user.save()

            # Create UserProfile if needed
            UserProfile.objects.create(user=user)

            # Clean session
            for key in ['temp_user_data', 'otp_code', 'otp_expires_at', 'profile_picture']:
                if key in request.session:
                    del request.session[key]

            login(request, user)
            messages.success(request, 'Email verified successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid OTP.')
    
    return render(request, 'registration/verify_email.html')



def resend_otp(request):
    if 'temp_user_data' not in request.session:
        return redirect('register')

    data = request.session['temp_user_data']

    # Generate new OTP
    otp_code = str(random.randint(100000, 999999))
    expires_at = timezone.now() + timedelta(minutes=15)

    # Store in session
    request.session['otp_code'] = otp_code
    request.session['otp_expires_at'] = expires_at.isoformat()

    # Send OTP email
    subject = 'New OTP for Verification'
    message = f'''
    Hi {data["username"]},

    Here is your new OTP: {otp_code}

    It will expire in 15 minutes.

    Best regards,
    Mavericks Team
    '''
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [data["email"]],
        fail_silently=False,
    )

    messages.info(request, 'A new OTP has been sent to your email.')
    return redirect('verify_email')


def login_view(request):
    if request.method == 'POST':
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                if user.is_verified:
                    login(request, user)
                    return redirect('dashboard')
                else:
                    # User exists but isn't verified
                    request.session['verify_user_id'] = user.id
                    messages.warning(request, 'Please verify your email first.')
                    return redirect('verify_email')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = EmailLoginForm()
    
    return render(request, 'registration/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

# @login_required
# def home(request):
#     return render(request, 'home.html')

# -------------------
# User Dashboard & Views
# -------------------

from myapp.models import ModuleCompletion

from django.db.models import Count, Q

from django.contrib.auth.decorators import login_required
from django.db.models import Avg
# import datetime
from django.utils.timezone import now
from myapp.models import ModuleCompletion

from django.db.models import Count, Q

from django.contrib.auth.decorators import login_required
from django.db.models import Avg
import datetime
from django.utils.timezone import now


@login_required
def dashboard(request):
    user = request.user

    coding_problems = CodingProblem.objects.filter(is_active=True)[:4]
    recent_submissions = CodeSubmission.objects.filter(user=user).order_by('-submitted_at')[:10]

    user_competency_qs = UserCompetency.objects.filter(user=user)
    competencies = Competency.objects.filter(is_active=True).order_by('name')
    user_comp_map = {uc.competency_id: uc for uc in user_competency_qs}

    user_competencies = []
    for comp in competencies:
        uc = user_comp_map.get(comp.id)
        has_in_progress_attempt = QuizAttempt.objects.filter(user=user, competency=comp, status='in_progress').exists()
        latest_attempt = QuizAttempt.objects.filter(user=user, competency=comp).order_by('-start_time').first()
        user_competencies.append({
            'competency': comp,
            'score': uc.score if uc else 0,
            'attempted': uc is not None,
            'has_in_progress_attempt': has_in_progress_attempt,
            'reached_max': False,
            'attempts_count': uc.attempts_count if uc else 0,
            'best_score': uc.best_score if uc else 0,
            'latest_attempt': latest_attempt,
        })

    profile = getattr(user, 'profile', None)

    accepted_problem_ids = set(CodeSubmission.objects.filter(user=user, status='accepted').values_list('problem_id', flat=True).distinct())
    accepted_problems_count = len(accepted_problem_ids)

    user_module_ids = ModuleCompletion.objects.filter(user=user).values_list('content__module_id', flat=True).distinct()
    user_modules = Module.objects.filter(id__in=user_module_ids)

    user_certificates = Certificate.objects.filter(user=user)
    certificates_count = user_certificates.count()

    hackathons = Hackathon.objects.filter(is_active=True).order_by('start_date')

    leaderboard_entry = getattr(user, 'leaderboard', None)
    current_rank = leaderboard_entry.rank if leaderboard_entry else 'N/A'

    hackathon_wins = Hackathon.objects.filter(
        user_uploaded_submissions__individual_user=user,
        user_uploaded_submissions__is_winner=True
    ).distinct().count()

    # ADDED: Updated assessment metrics
    completed_file_assessments = Assessment.objects.filter(user=user, completed=True).count()
    completed_quiz_assessments = QuizAttempt.objects.filter(user=user, status='completed').values('competency_id').distinct().count()
    completed_assessments = completed_file_assessments + completed_quiz_assessments

    total_file_assessments = Assessment.objects.filter(user=user).count()
    total_quiz_competencies = Competency.objects.filter(is_active=True).count()
    total_assessments = total_file_assessments + total_quiz_competencies

    completion_percentage = (completed_assessments / total_assessments * 100) if total_assessments > 0 else 0

    scores = [uc['score'] for uc in user_competencies if uc['score'] > 0]
    avg_score = sum(scores) / len(scores) if scores else 0

    last_month = now() - timedelta(days=30)
    avg_score_last_month = Assessment.objects.filter(
        user=user,
        completed=True,
        timestamp__lt=last_month
    ).aggregate(avg=Avg('score'))['avg'] or 0

    score_change = round(avg_score - avg_score_last_month, 1)

    if score_change > 0:
        score_color = 'text-green-600'
    elif score_change < 0:
        score_color = 'text-red-600'
    else:
        score_color = 'text-gray-600'

    completion_percentage = round(completion_percentage, 1)
    avg_score = round(avg_score, 1)


    learning_paths = LearningPath.objects.filter(user=user).select_related('module')
    xp_earned = learning_paths.filter(status='completed').aggregate(
        total_xp=Sum('module__xp_reward')
    )['total_xp'] or 0

    # XP from coding problems (stored in profile)
    coding_xp = profile.total_xp if profile else 0
    total_xp = coding_xp + xp_earned
    context = {
        'user': user,
        'coding_problems': coding_problems,
        'recent_submissions': recent_submissions,
        'user_competencies': user_competencies,
        'competencies': competencies,
         'total_xp': total_xp,
        'streak': get_daily_streak(user),
        'problems_solved': accepted_problems_count,
        'modules_completed': ModuleCompletion.objects.filter(user=user, is_completed=True).count(),
        'accepted_problem_ids': accepted_problem_ids,
        'user_modules': user_modules,
        'user_certificates': user_certificates,
        'hackathons': hackathons,
        'certificates_count': certificates_count,
        'hackathons_won': hackathon_wins,
        'current_rank': current_rank,

        # Assessment dashboard values
        'completed_assessments': f"{completed_assessments}/{total_assessments}" if total_assessments else "0/0",
        'completion_percentage': completion_percentage,
        'average_score': round(avg_score, 1),
    'score_change': score_change,
    'score_color': score_color,
    }

    return render(request, 'user/dashboard.html', context)


from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CodeSubmission, XPRecord

@receiver(post_save, sender=CodeSubmission)
def award_xp_on_first_accept(sender, instance, created, **kwargs):
    """
    Give XP only the first time a coding problem is accepted.
    """
    if instance.status == 'accepted':
        profile = getattr(instance.user, 'profile', None)
        if not profile:
            return

        # Check if XP already awarded
        if not XPRecord.objects.filter(user_profile=profile, problem_id=str(instance.problem.id)).exists():
            XPRecord.objects.create(
                user_profile=profile,
                problem_id=str(instance.problem.id),
                xp=10,  # XP per problem
                earned_at=timezone.now()
            )









from django.utils.timezone import now, localdate
# from datetime import timedelta

def get_daily_streak(user):
    # Get distinct dates on which user has done something (submissions in this case)
    activity_dates = CodeSubmission.objects.filter(
        user=user
    ).values_list('submitted_at', flat=True).order_by('-submitted_at')

    # Convert to unique date set
    unique_dates = sorted({dt.date() for dt in activity_dates}, reverse=True)

    streak = 0
    today = localdate()

    for i, activity_date in enumerate(unique_dates):
        if activity_date == today - timedelta(days=i):
            streak += 1
        else:
            break

    return streak





@login_required
def assessment_view(request):
    user = request.user

    if request.method == 'POST':
        form = AssessmentForm(request.POST, request.FILES)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.user = user
            assessment.save()
            messages.success(request, 'Assessment submitted successfully!')
            return redirect('assessment')
    else:
        form = AssessmentForm()

    competencies = Competency.objects.filter(is_active=True).order_by('name')
    user_comp_qs = UserCompetency.objects.filter(user=user)
    user_comp_map = {uc.competency_id: uc for uc in user_comp_qs}

    user_competencies = []
    for comp in competencies:
        uc = user_comp_map.get(comp.id)
        has_in_progress_attempt = QuizAttempt.objects.filter(user=user, competency=comp, status='in_progress').exists()
        latest_attempt = QuizAttempt.objects.filter(user=user, competency=comp).order_by('-start_time').first()

        user_competencies.append({
            'competency': comp,
            'score': uc.score if uc else 0,
            'attempted': uc is not None,
            'has_in_progress_attempt': has_in_progress_attempt,
            'reached_max_attempts': False,
            'attempts_count': uc.attempts_count if uc else 0,
            'best_score': uc.best_score if uc else 0,
            'latest_attempt': latest_attempt,
        })

    # ADDED: Updated assessment and quiz metrics
    completed_file_assessments = Assessment.objects.filter(user=user, completed=True).count()
    completed_quiz_assessments = QuizAttempt.objects.filter(user=user, status='completed').values('competency_id').distinct().count()
    completed_assessments = completed_file_assessments + completed_quiz_assessments

    total_file_assessments = Assessment.objects.filter(user=user).count()
    total_quiz_competencies = Competency.objects.filter(is_active=True).count()
    total_assessments = total_file_assessments + total_quiz_competencies

    completion_percentage = (completed_assessments / total_assessments * 100) if total_assessments > 0 else 0
    avg_score = Assessment.objects.filter(user=user, completed=True).aggregate(avg=Avg('score'))['avg'] or 0

    last_month = now() - timedelta(days=30)
    avg_score_last_month = Assessment.objects.filter(
        user=user,
        completed=True,
        timestamp__lt=last_month
    ).aggregate(avg=Avg('score'))['avg'] or 0

    score_change = round(avg_score - avg_score_last_month, 1)

    completion_percentage = round(completion_percentage, 1)
    avg_score = round(avg_score, 1)

    context = {
        'form': form,
        'assessments': Assessment.objects.filter(user=user).order_by('-timestamp'),
        'competencies': competencies,
        'user_competencies': user_competencies,

        # Updated assessment summary
        'completed_assessments': f"{completed_assessments}/{total_assessments}" if total_assessments else "0/0",
        'completion_percentage': completion_percentage,
        'average_score': avg_score,
        'score_change': score_change,
    }

    return render(request, 'user/assessment.html', context)


from django.db.models import Prefetch

from django.db.models import Sum, Count, Q, F
from django.shortcuts import render
from .models import LearningPath
@login_required
def learning_path_view(request):
    user = request.user
    learning_paths = LearningPath.objects.filter(user=user).select_related('module')

    total_count = learning_paths.count()
    completed_count = learning_paths.filter(status='completed').count()

    overall_progress = 0
    total_progress_sum = 0

    for path in learning_paths:
        module = path.module
        total_required = module.contents.filter(is_required=True).count()
        completed_required = ModuleCompletion.objects.filter(
            user=user,
            content__module=module,
            content__is_required=True,
            is_completed=True
        ).count()

        if total_required > 0:
            progress_percent = int((completed_required / total_required) * 100)
        else:
            progress_percent = 0

        # Update the progress and status dynamically
        path.progress = progress_percent
        
        # Automatically update status based on progress
        if progress_percent == 100 and path.status != 'completed':
            path.status = 'completed'
            path.completed_at = timezone.now()
            path.save()  # Save the status change to database
        elif progress_percent > 0 and path.status == 'not_started':
            path.status = 'in_progress'
            path.started_at = timezone.now() if not path.started_at else path.started_at
            path.save()  # Save the status change to database

        total_progress_sum += progress_percent

    if total_count > 0:
        overall_progress = round(total_progress_sum / total_count)

    xp_earned = learning_paths.filter(status='completed').aggregate(
        total_xp=Sum('module__xp_reward')
    )['total_xp'] or 0

    context = {
        'learning_paths': learning_paths,
        'total_count': total_count,
        'completed_count': completed_count,
        'overall_progress': overall_progress,
        'xp_earned': xp_earned,
    }

    return render(request, 'user/learning_path.html', context)

@login_required
def add_to_path(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    if request.method == 'POST':
        position = request.POST.get('position', 'end')
        start_now = request.POST.get('start_now', False) == 'true'

        try:
            learning_path, created = LearningPath.objects.get_or_create(
                user=request.user,
                module=module,
                defaults={
                    'status': 'in_progress' if start_now else 'not_started',
                    'progress': 0,
                    'started_at': timezone.now() if start_now else None
                }
            )

            if not created:
                if start_now and learning_path.status != 'in_progress':
                    learning_path.status = 'in_progress'
                    learning_path.started_at = timezone.now()
                    learning_path.save()

            if position in ['start', 'next']:
                paths = list(LearningPath.objects.filter(user=request.user).order_by('id'))
                paths = [p for p in paths if p.id != learning_path.id]
                if position == 'start':
                    paths.insert(0, learning_path)
                elif position == 'next':
                    current_index = next(
                        (i for i, p in enumerate(paths) if p.status == 'in_progress'), 0
                    )
                    paths.insert(current_index + 1, learning_path)

                for index, path in enumerate(paths):
                    if hasattr(path, 'order'):
                        path.order = index
                        path.save()

            response_data = {
                'success': True,
                'message': f'"{module.name}" added to your learning path!',
                'status': learning_path.get_status_display(),
                'progress': learning_path.progress
            }

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data)

            messages.success(request, response_data['message'])
            return redirect('learning_path')

        except Exception as e:
            response_data = {
                'success': False,
                'message': f'Error adding module: {str(e)}'
            }

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data, status=400)

            messages.error(request, response_data['message'])
            return redirect('module_list')

    return redirect('module_list')

@login_required
def refresh_recommendations(request):
    if request.method == 'POST':
        return JsonResponse({'success': True})

    return JsonResponse({'success': False}, status=400)

@login_required
def remove_from_path(request, module_id):
    learning_path = get_object_or_404(
        LearningPath,
        user=request.user,
        module_id=module_id
    )
    module_name = learning_path.module.name
    learning_path.delete()

    messages.success(request, f'"{module_name}" has been removed from your learning path')
    return redirect('learning_path')

def module_list_view(request):
    # Get all modules with annotation for enrollment count
    modules = Module.objects.annotate(
        enrollment_count=Count('learningpath')
    ).all()
    
    # Get IDs of modules already in user's path (if authenticated)
    user_paths = []
    if request.user.is_authenticated:
        user_paths = request.user.learningpath_set.values_list('module_id', flat=True)
    
    # Get content count for each module (if you have a Content model)
    for module in modules:
        if hasattr(module, 'contents'):
            module.contents_count = module.contents.count()
    
    return render(request, 'user/module_list.html', {
        'modules': modules,
        'user_paths': user_paths
    })

@login_required
@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module.objects.prefetch_related('contents'), id=module_id)
    learning_path = LearningPath.objects.filter(user=request.user, module=module).first()
    # Get last visited date for this user and module
    

    # Get completed contents for this module
    completed_contents = list(ModuleCompletion.objects.filter(
        user=request.user,
        content__module=module,
        is_completed=True
    ).values_list('content_id', flat=True))
    
    contents = module.contents.all().order_by('order')

    # Calculate progress for this module
    total_required_contents = module.contents.filter(is_required=True).count()
    completed_required_contents = ModuleCompletion.objects.filter(
        user=request.user,
        content__module=module,
        content__is_required=True,
        is_completed=True
    ).count()

    progress_percent = int((completed_required_contents / total_required_contents) * 100) if total_required_contents > 0 else 0
    
    # Check module completion (learning path status)
    is_module_completed = learning_path and learning_path.status == 'completed'
    
    # Check if certificate exists
    has_certificate = Certificate.objects.filter(
        user=request.user,
        module=module
    ).exists()

    # NEW: Count total completed modules for this user
    total_completed_modules = LearningPath.objects.filter(
        user=request.user,
        status='completed'
    ).count()


    context = {
        'module': module,
        'learning_path': learning_path,
        'completed_contents': completed_contents,
        'contents': contents,
        'progress_percent': progress_percent,
        'is_module_completed': is_module_completed,
        'has_certificate': has_certificate,
        'total_completed_modules': total_completed_modules,  # Added total count
        # Additional useful context
        'total_required_contents': total_required_contents,
        'completed_required_contents': completed_required_contents,
    }
    return render(request, 'user/module_detail.html', context)

@login_required
def module_start(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    learning_path, created = LearningPath.objects.get_or_create(
        user=request.user,
        module=module,
        defaults={'status': 'in_progress', 'progress': 0}
    )

    if not created and learning_path.status == 'not_started':
        learning_path.status = 'in_progress'
        learning_path.save()

    return redirect('module_detail', module_id=module.id)

@login_required
def module_review(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    learning_path = LearningPath.objects.filter(user=request.user, module=module).first()

    if learning_path:
        learning_path.status = 'completed'
        learning_path.progress = 100
        learning_path.save()

    return redirect('module_detail', module_id=module.id)

@login_required
def continue_module_view(request, module_id):
    module = get_object_or_404(Module, id=module_id)

    learning_path, created = LearningPath.objects.get_or_create(
        user=request.user,
        module=module,
        defaults={
            'status': 'in_progress',
            'started_at': timezone.now()
        }
    )

    if not created and learning_path.status != 'in_progress':
        learning_path.status = 'in_progress'
        learning_path.started_at = timezone.now()
        learning_path.save()

    incomplete_content = ModuleContent.objects.filter(
        module=module,
        is_required=True
    ).exclude(
        id__in=ModuleCompletion.objects.filter(
            user=request.user,
            is_completed=True
        ).values('content')
    ).first()

    if incomplete_content:
        return redirect('module_content', module_id=module.id)
    return redirect('module_detail', module_id=module.id)

def module_content(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    return render(request, 'user/module_content.html', {'module': module})

@login_required
def toggle_content_completion(request, content_id):
    content = get_object_or_404(ModuleContent, id=content_id)
    user = request.user

    completion, created = ModuleCompletion.objects.get_or_create(
        user=user,
        content=content,
        defaults={'is_completed': True}
    )

    if not created:
        completion.is_completed = not completion.is_completed
        completion.save()

    learning_path = LearningPath.objects.filter(user=user, module=content.module).first()

    badge_awarded = False
    if learning_path:
        learning_path.progress = calculate_module_progress(user, content.module)

        if learning_path.progress == 100:
            learning_path.status = 'completed'
            learning_path.completed_at = timezone.now()
            learning_path.save()

            # Award XP and badge (assumes you have this helper implemented)
            # badge_awarded = complete_module_for_user(user, content.module, learning_path)
        elif learning_path.progress > 0:
            learning_path.status = 'in_progress'
            if not learning_path.started_at:
                learning_path.started_at = timezone.now()
            learning_path.save()
        else:
            learning_path.status = 'not_started'
            learning_path.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_completed': completion.is_completed,
            'progress': learning_path.progress if learning_path else 0,
            'status': learning_path.status if learning_path else 'not_started',
            'badge_awarded': badge_awarded,
        })

    return redirect('module_detail', module_id=content.module.id)



# -------------------
# Hackathon Views
# -------------------

# ============================================
# UTILITY FUNCTIONS
# ============================================

def github_api_request(url, token=None):
    """Make GitHub API request"""
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token and hasattr(settings, 'GITHUB_API_TOKEN'):
        headers['Authorization'] = f'token {settings.GITHUB_API_TOKEN}'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"GitHub API Error: {e}")
        return None

def send_notification(webhook_url, message, platform='slack'):
    """Send notification to Slack/Discord"""
    if not webhook_url:
        return False
    
    if platform == 'slack':
        payload = {'text': message}
    else:  # Discord
        payload = {'content': message}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Notification Error: {e}")
        return False

def process_github_submission(submission):
    """Process and verify GitHub repository"""
    try:
        github_url = submission.github_url
        if 'github.com' not in github_url:
            return False
        
        # Extract owner and repo name
        parts = github_url.replace('https://github.com/', '').replace('.git', '').split('/')
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            
            # Get repository info from GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            repo_data = github_api_request(api_url)
            
            if repo_data:
                # Get commits
                commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
                commits_data = github_api_request(commits_url)
                
                # Get languages
                languages_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
                languages_data = github_api_request(languages_url)
                
                # Create or update GitHubRepository
                github_repo, created = GitHubRepository.objects.get_or_create(
                    submission=submission,
                    defaults={
                        'repo_url': github_url,
                        'repo_owner': owner,
                        'repo_name': repo,
                        'last_commit_hash': commits_data[0]['sha'] if commits_data else '',
                        'commit_count': len(commits_data) if commits_data else 0,
                        'contributors': [commit['author']['login'] for commit in commits_data[:10] if commit.get('author')] if commits_data else [],
                        'languages': languages_data or {},
                        'is_verified': True
                    }
                )
                
                # Update submission metadata
                submission.submission_metadata.update({
                    'github_verified': True,
                    'languages_used': list(languages_data.keys()) if languages_data else [],
                    'commit_count': len(commits_data) if commits_data else 0
                })
                submission.save()
                return True
                
    except Exception as e:
        print(f"Error processing GitHub submission: {e}")
        submission.submission_metadata['github_error'] = str(e)
        submission.save()
    
    return False

# ============================================
# MAIN VIEWS
# ============================================

@login_required
@require_POST
def assign_project_idea(request):
    """
    Allow ANY team member (not just leader) to assign project for their team.
    """
    try:
        hackathon_id = request.POST.get("hackathon_id")
        project_title = request.POST.get("project_title")
        project_description = request.POST.get("project_description")

        if not all([hackathon_id, project_title, project_description]):
            return JsonResponse({"success": False, "error": "Missing required data."}, status=400)

        hackathon = get_object_or_404(Hackathon, id=hackathon_id)
        user = request.user

        # Make sure caller is registered
        try:
            registration = HackathonRegistration.objects.get(
                hackathon=hackathon,
                user=user,
                is_active=True,
            )
        except HackathonRegistration.DoesNotExist:
            return JsonResponse({"success": False, "error": "You are not registered for this hackathon."}, status=403)

        user_team = registration.team

        with transaction.atomic():
            if user_team:
                # 🔥 FIXED: ANY team member can assign for the team (not just leader)
                obj, created = HackathonSubmission.objects.update_or_create(
                    hackathon=hackathon,
                    team=user_team,
                    individual_user__isnull=True,
                    defaults={
                        "project_title": project_title,
                        "project_description": project_description,
                        "individual_user": None,
                    },
                )
                print(f"✅ Team assignment: {obj.project_title} for team {user_team.name} by {user.username}")
            else:
                # Individual assignment
                obj, created = HackathonSubmission.objects.update_or_create(
                    hackathon=hackathon,
                    individual_user=user,
                    team__isnull=True,
                    defaults={
                        "project_title": project_title,
                        "project_description": project_description,
                        "team": None,
                    },
                )
                print(f"✅ Individual assignment: {obj.project_title} for user {user.username}")

        return JsonResponse({"success": True, "title": obj.project_title})

    except Exception as e:
        print(f"❌ Error in assign_project_idea: {e}")
        return JsonResponse({"success": False, "error": f"Server error: {str(e)}"}, status=500)



def extract_weighted_keywords(text):
    """
    Extracts keywords from text and assigns a weight based on their technical importance.
    """
    weights = {
        'predict': 3, 'maintenance': 3, 'dashboard': 3, 'model': 2, 'algorithm': 2, 'classification': 2,
        'sklearn': 5, 'pandas': 5, 'numpy': 5, 'tensorflow': 5, 'pytorch': 5, 'keras': 5, 'scipy': 4,
        'matplotlib': 4, 'seaborn': 4, 'plotly': 4, 'data': 1, 'analysis': 2, 'visualize': 2, 'dataset': 2,
        'api': 3, 'backend': 2, 'frontend': 2, 'database': 2, 'request': 1, 'response': 1, 'endpoint': 2,
        'react': 5, 'angular': 5, 'vue': 5, 'django': 5, 'flask': 5, 'fastapi': 5, 'node': 4, 'express': 4,
        'html': 2, 'css': 2, 'javascript': 2, 'typescript': 3, 'bootstrap': 3, 'tailwind': 3,
        'chatbot': 3, 'emotion': 3, 'recognition': 2, 'nlp': 4, 'nltk': 5, 'spacy': 5, 'automation': 2,
        'user': 1, 'interface': 2, 'authentication': 3, 'security': 3, 'performance': 2
    }
    
    stop_words = set([
        'a', 'an', 'the', 'and', 'or', 'in', 'on', 'for', 'with', 'is', 'are', 'was', 'were',
        'to', 'of', 'it', 'that', 'this', 'you', 'he', 'she', 'we', 'they', 'i', 'me', 'my',
        'project', 'develop', 'using', 'based', 'features', 'system', 'implement', 'create', 'app',
        'key', 'short', 'description', 'file', 'code', 'help', 'professionals'
    ])
    
    words = re.findall(r'\b\w+\b', text.lower())
    return {word: weights.get(word, 1) for word in words if word not in stop_words and len(word) > 2 and not word.isdigit()}

@login_required
def submit_project(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    now = timezone.now()
    show_all = request.GET.get('show', 'summary')
    
    if request.method != 'POST':
        try:
            ai_project_details = Submission.objects.get(hackathon=hackathon, user=request.user)
            context = {
                'hackathon': hackathon,
                'submission': ai_project_details,
                'existing_submission': HackathonSubmission.objects.filter(hackathon=hackathon, individual_user=request.user).first(),
                'max_file_size_mb': 50,
            }
            return render(request, 'user/submit_project.html', context)
        except Submission.DoesNotExist:
            messages.error(request, "Error: You must be assigned a project idea before you can submit.")
            return redirect('hackathon_detail', hackathon_id=hackathon.id)

    try:
        ai_project_details = Submission.objects.get(hackathon=hackathon, user=request.user)
        uploaded_file = request.FILES.get('project_files')
        
        if not uploaded_file:
            messages.error(request, "File upload failed. Please ensure you have selected a .zip file and try again.")
            return redirect('submit_hackathon_project', hackathon_id=hackathon.id)

        submission, created = HackathonSubmission.objects.update_or_create(
            hackathon=hackathon, individual_user=request.user,
            defaults={
                'project_title': ai_project_details.project_title,
                'project_description': ai_project_details.project_description,
                'submission_file': uploaded_file, 'evaluation_status': 'in_progress'
            }
        )

        project_text = f"{ai_project_details.project_title} {ai_project_details.project_description}"
        project_keywords = extract_weighted_keywords(project_text)
        total_possible_score = sum(project_keywords.values())

        submission_content = ""
        file_count = 0
        file_types = set()
        with zipfile.ZipFile(submission.submission_file, 'r') as zf:
            for filename in zf.namelist():
                if not filename.startswith('__MACOSX/') and zf.getinfo(filename).file_size < 150000:
                    try:
                        submission_content += zf.read(filename).decode('utf-8', errors='ignore') + "\n"
                        file_count += 1
                        file_types.add(filename.split('.')[-1].lower())
                    except: continue
        
        submission_keywords = extract_weighted_keywords(submission_content)
        achieved_score = 0
        matching_keywords = []
        for keyword, weight in project_keywords.items():
            if keyword in submission_keywords:
                achieved_score += weight
                matching_keywords.append(keyword)

        match_percentage = (achieved_score / total_possible_score) * 100 if total_possible_score > 0 else 0
        final_score = min(100, 10 + int(match_percentage * 0.9))
        
        tech_stack = {tech for tech in ['react', 'django', 'flask', 'pandas', 'sklearn', 'tensorflow', 'pytorch', 'vue', 'api'] if tech in submission_keywords}
        
        if final_score > 85: feedback_summary = "Excellent Match!"
        elif final_score > 60: feedback_summary = "Good Alignment."
        else: feedback_summary = "Low Alignment."
        
        ai_notes = f"### AI Evaluation Report\n\n**Overall Assessment:** {feedback_summary}\n\n"
        ai_notes += f"**Analysis Summary:**\n- Our system analyzed **{file_count}** source files from your submission.\n"
        if tech_stack:
            ai_notes += f"- Identified technologies: **{', '.join(sorted(list(tech_stack))).title()}**.\n"
        if matching_keywords:
            ai_notes += f"- Your submission shares **{len(matching_keywords)} key concepts** with the project description, including: `{', '.join(sorted(matching_keywords)[:5])}`."
        else:
            ai_notes += "- No significant overlapping technical concepts were found. Please ensure you uploaded the correct project files corresponding to the assignment."
            
        submission.ai_evaluation_score = final_score
        submission.ai_evaluation_notes = ai_notes
        submission.evaluation_status = 'completed'
        submission.save()
        
        messages.success(request, f'🎉 Project submitted and evaluated! Your alignment score is {final_score}/100.')
        return redirect('hackathon_detail', hackathon_id=hackathon.id)

    except Exception as e:
        messages.error(request, "A critical error occurred while submitting your project. Please try again.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)

@login_required
@require_POST
def generate_project_idea(request):
    """Generate a dynamic project idea using Mistral AI via OpenRouter"""
    skills = request.POST.getlist('skills')
    
    if not skills:
        return JsonResponse({'error': 'Please select at least one skill'})
    
    try:
        # ✅ DYNAMIC: Generate unique project with AI
        project_idea = generate_with_mistral_ai(skills)
        
        return JsonResponse({
            'idea': project_idea,
            'success': True
        })
        
    except Exception as e:
        print(f"AI Generation failed: {e}")  # Debug log
        # Fallback to enhanced template-based generation
        return JsonResponse({
            'idea': generate_fallback_project(skills),
            'success': True
        })

def generate_with_mistral_ai(skills):
    """Use Mistral AI via OpenRouter to generate unique project ideas"""
    
    # Create intelligent prompt based on skills
    prompt = create_smart_prompt(skills)
    
    # Use your existing OpenRouter configuration
    api_key = settings.OPENROUTER_API_KEY

    
    url = 'https://openrouter.ai/api/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': settings.OPENROUTER_SITE_URL,
        'X-Title': settings.OPENROUTER_SITE_NAME
    }
    
    payload = {
        "model": settings.AI_EVALUATION_SETTINGS["MODEL"],  # Use your existing model
        "messages": [
            {"role": "system", "content": "You are an expert hackathon mentor who generates innovative, feasible project ideas based on specific technology stacks."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,  # Higher creativity than evaluation
        "max_tokens": 600,
        "top_p": 0.9
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        return format_ai_response(data['choices'][0]['message']['content'].strip())
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")

def create_smart_prompt(skills):
    """Create intelligent prompts based on skill combinations"""
    
    # Categorize skills for better context
    skill_context = categorize_skills(skills)
    project_context = get_project_context(skill_context)
    
    # Limit skills for better focus
    skill_list = ", ".join(skills[:6])
    
    prompt = f"""
Generate a UNIQUE and INNOVATIVE hackathon project idea using these specific technologies: {skill_list}

Project Context: {project_context}

STRICT Requirements:
- Must meaningfully utilize ALL the provided technologies
- Feasible to build in 24-48 hours during a hackathon
- Include real-world practical applications
- Avoid generic ideas like "E-Learning Platform", "Task Manager", or "Social Media"
- Be specific about how each technology is used

Format your response EXACTLY like this:

**Project Title:** [Creative, specific name that reflects the technology stack]

**Description:** [2-3 sentences describing the core innovative concept and its real-world application]

**Core Features:**
• [Feature 1 - specific to Arduino/hardware if present]
• [Feature 2 - database/storage functionality if present]
• [Feature 3 - user interface/interaction feature]
• [Feature 4 - unique technical challenge or innovation]

**Technical Implementation:**
• [Explain how Arduino/hardware will be used - be specific]
• [Explain database design and data flow]
• [Describe system architecture and integration]
• [Detail any real-time or advanced features]

**Bonus Features:**
• [Advanced feature that showcases technical skills]
• [Scalability or future enhancement possibility]

**Recommended Tech Stack:** {skill_list}

Remember: Make it unique, innovative, and perfectly matched to the selected technologies!
"""
    
    return prompt

def categorize_skills(skills):
    """Analyze skill combinations to provide better context"""
    categories = {
        'hardware': ['Arduino', 'Raspberry Pi', 'Internet of Things'],
        'database': ['MySQL', 'PostgreSQL', 'MongoDB', 'Microsoft SQL Server', 'SQLite', 'Redis', 'Firebase'],
        'frontend': ['React', 'Angular', 'Vue.js', 'JavaScript', 'TypeScript', 'HTML', 'CSS'],
        'backend': ['Django', 'Flask', 'Express.js', 'Spring Boot', 'Ruby on Rails', 'PHP', 'Laravel'],
        'mobile': ['React Native', 'Flutter', 'iOS Development', 'Android Development', 'Xamarin', 'Ionic'],
        'ai_ml': ['Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Computer Vision', 'Natural Language Processing'],
        'cloud': ['AWS', 'Azure', 'Google Cloud Platform', 'Docker', 'Kubernetes'],
        'blockchain': ['Blockchain', 'Smart Contracts', 'Web3'],
        'game': ['Unity', 'Unreal Engine'],
        'data': ['Pandas', 'NumPy', 'Data Analysis', 'Scikit-learn']
    }
    
    user_categories = []
    for category, category_skills in categories.items():
        if any(skill in skills for skill in category_skills):
            user_categories.append(category)
    
    return user_categories

def get_project_context(skill_context):
    """Provide context hints based on skill combinations"""
    
    if 'hardware' in skill_context and 'database' in skill_context:
        return "IoT system with real-time data collection, storage, and analytics dashboard"
    elif 'ai_ml' in skill_context and 'database' in skill_context:
        return "AI-powered data analysis platform with machine learning predictions"
    elif 'blockchain' in skill_context:
        return "Decentralized application with smart contracts and cryptocurrency integration"
    elif 'mobile' in skill_context and 'backend' in skill_context:
        return "Full-stack mobile application with robust backend services"
    elif 'game' in skill_context:
        return "Interactive game or gamified application with engaging mechanics"
    elif 'hardware' in skill_context:
        return "Physical computing project with sensors and real-world interaction"
    elif 'frontend' in skill_context and 'backend' in skill_context and 'database' in skill_context:
        return "Full-stack web application with comprehensive data management"
    else:
        return "Innovative software solution addressing a real-world problem"

def format_ai_response(ai_text):
    """Clean and format the AI response"""
    # Ensure proper formatting
    if not ai_text.startswith('**Project Title:**'):
        # If AI didn't follow format exactly, add proper formatting
        lines = ai_text.split('\n')
        if lines:
            first_line = lines[0].strip()
            if not first_line.startswith('**'):
                ai_text = f"**Project Title:** {first_line}\n\n" + '\n'.join(lines[1:])
    
    return ai_text

def generate_fallback_project(skills):
    """Enhanced fallback system with skill-specific templates"""
    
    skill_context = categorize_skills(skills)
    
    # Smart template selection based on skills
    if 'hardware' in skill_context and 'database' in skill_context:
        templates = [
            {
                'title': 'Smart Environmental Monitoring Hub',
                'description': 'Real-time environmental monitoring system using Arduino sensors with comprehensive data logging, analysis, and alert system for environmental conditions.',
                'focus': 'IoT data collection and database management'
            },
            {
                'title': 'Industrial Equipment Tracker',
                'description': 'Arduino-based equipment monitoring system with SQL database for tracking machinery performance, maintenance schedules, and predictive analytics.',
                'focus': 'Industrial IoT with robust data storage'
            }
        ]
    elif 'ai_ml' in skill_context:
        templates = [
            {
                'title': 'Intelligent Content Analyzer',
                'description': 'AI-powered content analysis platform that processes text, images, or audio to extract insights, sentiment, and actionable intelligence.',
                'focus': 'Machine learning and data processing'
            }
        ]
    elif 'mobile' in skill_context:
        templates = [
            {
                'title': 'Community Connection Platform',
                'description': 'Location-based mobile app connecting people with shared interests, skills, or needs in their local community.',
                'focus': 'Mobile development with social features'
            }
        ]
    else:
        templates = [
            {
                'title': 'Collaborative Workflow Optimizer',
                'description': 'Web-based platform that analyzes team workflows and suggests optimizations using data-driven insights and automation.',
                'focus': 'Web development with analytics'
            }
        ]
    
    selected = random.choice(templates)
    skill_list = ', '.join(skills[:5])
    
    return f"""**Project Title:** {selected['title']}

**Description:** {selected['description']}

**Core Features:**
• User authentication and profile management
• Real-time data processing and visualization
• Interactive dashboard with analytics
• Notification and alert system

**Technical Implementation:**
• {selected['focus']} using the selected technology stack
• Scalable architecture with efficient data handling
• Modern user interface with responsive design
• Integration capabilities with external services

**Recommended Tech Stack:** {skill_list}"""

@login_required
def hackathon_view(request):
    """
    Dashboard that lists all hackathons, user activity, etc.
    Adds `unscored` to each hackathon so creators can jump straight to the
    evaluation table from this page.
    """
    now = timezone.now()
    show_all = request.GET.get("show", "summary")

    # keep statuses fresh
    from .models import Hackathon, HackathonRegistration, HackathonSubmission, HackathonTeam
    for h in Hackathon.objects.filter(is_active=True):
        h.update_status()

    # common annotation for every queryset
    UN_SCORED = Count(
        "user_uploaded_submissions",  # ✅ Fixed: Changed from ai_project_submissions
        filter=Q(
            user_uploaded_submissions__submission_file__isnull=False,
            user_uploaded_submissions__final_score__isnull=True,
        ),
    )

    open_hackathons = (
        Hackathon.objects.filter(is_active=True, status="registration_open")
        .annotate(
            participant_count=Count("registrations", filter=Q(registrations__is_active=True)),
            unscored=UN_SCORED,
        )
        .order_by("registration_end")
    )

    active_hackathons = (
        Hackathon.objects.filter(is_active=True, status="in_progress")
        .annotate(
            participant_count=Count("registrations", filter=Q(registrations__is_active=True)),
            submission_count=Count("user_uploaded_submissions", distinct=True),
            unscored=UN_SCORED,
        )
        .order_by("end_date")
    )

    # ✅ NEW: Add evaluation hackathons
    evaluation_hackathons = (
        Hackathon.objects.filter(is_active=True, status="evaluation")
        .annotate(
            participant_count=Count("registrations", filter=Q(registrations__is_active=True)),
            submission_count=Count("user_uploaded_submissions", distinct=True),
            unscored=UN_SCORED,
        )
        .order_by("-end_date")
    )

    upcoming_hackathons = (
        Hackathon.objects.filter(is_active=True, status="upcoming")
        .annotate(
            participant_count=Count("registrations", filter=Q(registrations__is_active=True)),
            unscored=UN_SCORED,
        )
        .order_by("registration_start")
    )

    completed_hackathons = (
        Hackathon.objects.filter(is_active=True, status="completed")
        .annotate(
            participant_count=Count("registrations", filter=Q(registrations__is_active=True)),
            submission_count=Count("user_uploaded_submissions", distinct=True),
            winner_count=Count("user_uploaded_submissions", 
              filter=Q(user_uploaded_submissions__prize_category__isnull=False) & 
                    ~Q(user_uploaded_submissions__prize_category='')),
            unscored=UN_SCORED,
        )
        .prefetch_related("user_uploaded_submissions__team", "user_uploaded_submissions__individual_user")
        .order_by("-end_date")
    )

    # deadline helpers
    for h in upcoming_hackathons:
        diff = h.registration_start - now
        h.days_until_registration = max(0, diff.days)

    for h in open_hackathons:
        diff = h.registration_end - now
        h.registration_closing_hours = max(0, int(diff.total_seconds() // 3600))
        h.registration_closing_days = max(0, diff.days)

    for h in active_hackathons:
        diff = h.end_date - now
        h.hours_remaining = max(0, int(diff.total_seconds() // 3600))
        h.days_remaining = max(0, diff.days)
        h.minutes_remaining = max(0, int((diff.total_seconds() % 3600) // 60))

    # ✅ REMOVED: Don't set current_participants since it's a property
    # The template will use hackathon.participant_count instead

    # slice completed list
    paginated_completed = completed_hackathons[:20 if show_all == "all" else 5]
    for h in paginated_completed:
        h.winners = h.user_uploaded_submissions.filter(is_winner=True).order_by("-final_score")
        h.first_place_winner = h.winners.filter(prize_category="first_place").first()
        h.total_prize_categories = h.winners.values("prize_category").distinct().count()

    # USER-CENTRIC DATA -----------------------------------------------------------------
    my_registrations = (
        HackathonRegistration.objects.filter(user=request.user, is_active=True)
        .select_related("hackathon", "team")
        .annotate(hackathon_status=F("hackathon__status"))
    )

    for r in my_registrations:
        q = Q(hackathon=r.hackathon, is_winner=True)
        q &= Q(team=r.team) if r.team else Q(individual_user=request.user)
        wins = HackathonSubmission.objects.filter(q)
        r.winning_submissions = wins
        r.has_won = wins.exists()
        r.prize_categories = [s.prize_category for s in wins]

    my_teams = (
        HackathonTeam.objects.filter(Q(leader=request.user) | Q(members=request.user))
        .distinct()
        .select_related("hackathon")
    )

    my_submissions = (
        HackathonSubmission.objects.filter(Q(individual_user=request.user) | Q(team__members=request.user))
        .distinct()
        .select_related("hackathon", "team")
        .order_by("-submitted_at")
    )

    for s in my_submissions:
        s.has_github_repo = getattr(s, "github_repository", None) is not None
        s.is_evaluated = s.final_score is not None
        if s.is_winner:
            s.prize_display = s.prize_category.replace("_", " ").title()

    # quick numbers
    user_stats = {
        "total_registrations": my_registrations.count(),
        "active_participations": my_registrations.filter(hackathon__status__in=["registration_open", "in_progress"]).count(),
        "completed_hackathons": my_registrations.filter(hackathon__status="completed").count(),
        "total_submissions": my_submissions.count(),
        "winning_submissions": my_submissions.filter(is_winner=True).count(),
        "teams_led": my_teams.filter(leader=request.user).count(),
        "teams_joined": my_teams.exclude(leader=request.user).count(),
        "total_prizes_won": my_submissions.filter(is_winner=True).count(),  # ✅ Added missing field
        "win_rate": round((my_submissions.filter(is_winner=True).count() / max(my_submissions.count(), 1)) * 100, 1),
    }

    featured = list(open_hackathons[:3]) if open_hackathons.exists() else list(upcoming_hackathons[:3])
    my_regs_disp = my_registrations if show_all == "all" else my_registrations[:3]
    my_subs_disp = my_submissions if show_all == "all" else my_submissions[:2]

    return render(
        request,
        "user/hackathon.html",
        {
            "upcoming_hackathons": upcoming_hackathons,
            "open_hackathons": open_hackathons,
            "active_hackathons": active_hackathons,
            "evaluation_hackathons": evaluation_hackathons,  # ✅ NEW: Added evaluation hackathons
            "completed_hackathons": paginated_completed,
            "featured_hackathons": featured,
            "my_registrations": my_regs_disp,
            "my_teams": my_teams,
            "my_submissions": my_subs_disp,
            "user_stats": user_stats,
            "current_time": now,
            "show_all": show_all,
        },
    )




@login_required
def register_hackathon(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    hackathon.update_status()
    
    now = timezone.now()
    
    if hackathon.registration_start > now:
        messages.warning(request, f'Registration opens on {hackathon.registration_start.strftime("%B %d, %Y at %I:%M %p")}')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    if hackathon.registration_end < now:
        time_diff = now - hackathon.registration_end
        messages.warning(request, f'Registration closed {time_diff.days} days and {time_diff.seconds//3600} hours ago.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    if hackathon.status != 'registration_open':
        messages.warning(request, f'Registration is not available. Current status: {hackathon.get_status_display()}')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    existing_registration = HackathonRegistration.objects.filter(
        user=request.user,
        hackathon=hackathon,
        is_active=True
    ).first()
    
    if existing_registration:
        messages.info(request, 'You are already registered for this hackathon.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    current_participants = HackathonRegistration.objects.filter(
        hackathon=hackathon,
        is_active=True
    ).count()
    
    if current_participants >= hackathon.max_participants:
        messages.warning(request, 'This hackathon is full. Registration is no longer available.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    if not hackathon.is_active:
        messages.error(request, 'This hackathon is not currently active.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    try:
        registration = HackathonRegistration.objects.create(
            user=request.user,
            hackathon=hackathon,
            is_active=True
        )
        
        hackathon.save()
        
        messages.success(request, f'🎉 Successfully registered for {hackathon.name}!')
        
        if hackathon.slack_webhook:
            message = f"🎉 New registration: {request.user.get_full_name() or request.user.username} joined {hackathon.name}"
            send_notification(hackathon.slack_webhook, message, 'slack')
        
    except Exception as e:
        messages.error(request, 'Registration failed due to a technical issue. Please try again.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    return redirect('hackathon_detail', hackathon_id=hackathon_id)

# @login_required
# def edit_hackathon(request, hackathon_id):
#     hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
#     # Check if user is creator
#     if request.user != hackathon.creator:
#         raise PermissionDenied
    
#     if request.method == 'POST':
#         form = HackathonForm(request.POST, instance=hackathon)
#         if form.is_valid():
#             form.save()
#             return redirect('hackathon_detail', hackathon_id=hackathon.id)
#     else:
#         form = HackathonForm(instance=hackathon)
    
#     return render(request, 'user/edit_hackathon.html', {
#         'form': form,
#         'hackathon': hackathon
#     })

@login_required
def create_hackathon(request):
    if request.method == 'POST':
        post_data = request.POST.copy()
        if not post_data.get('max_file_size_mb'):
            post_data['max_file_size_mb'] = '50'
        
        form = EnhancedHackathonCreateForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                hackathon = form.save(commit=False)
                hackathon.created_by = request.user
                
                now = timezone.now()
                if hackathon.registration_start <= now <= hackathon.registration_end:
                    hackathon.status = 'registration_open'
                elif now < hackathon.registration_start:
                    hackathon.status = 'upcoming'
                elif hackathon.start_date <= now <= hackathon.end_date:
                    hackathon.status = 'in_progress'
                
                if not hackathon.allowed_file_types:
                    hackathon.allowed_file_types = ['pdf', 'zip', 'tar.gz', 'docx', 'pptx']
                
                hackathon.save()
                
                if hackathon.slack_webhook:
                    message = f"🚀 New hackathon created: *{hackathon.name}* by {request.user.get_full_name() or request.user.username}"
                    send_notification(hackathon.slack_webhook, message, 'slack')
                
                messages.success(request, f'🎉 Hackathon "{hackathon.name}" created successfully!')
                return redirect('hackathon_detail', hackathon_id=hackathon.id)
                
            except Exception as e:
                messages.error(request, f'Error creating hackathon: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = EnhancedHackathonCreateForm()
    
    context = {
        'form': form,
        'max_file_size': 50,
        'supported_apis': ['GitHub', 'Slack', 'Discord']
    }
    
    return render(request, 'user/create_hackathon.html', context)

@login_required
def hackathon_detail(request, hackathon_id):
    try:
        hackathon = get_object_or_404(Hackathon, id=hackathon_id)
        hackathon.update_status()
        
        now = timezone.now()
        user = request.user
        
        context = {
            'hackathon': hackathon,
            'current_time': now,
            'user_registration': None,
            'user_team': None,
            'user_submission': None,
            'ai_assigned_project': None,
            'is_creator': False,
            'can_edit': False,
        }

        if user.is_authenticated:
            # Get user registration and team
            context['user_registration'] = HackathonRegistration.objects.filter(
                user=user, 
                hackathon=hackathon,
                is_active=True
            ).select_related('team').first()
            
            if context['user_registration']:
                context['user_team'] = context['user_registration'].team
                
                print(f"🔍 DEBUG - User: {user.username}")
                print(f"🔍 DEBUG - Team: {context['user_team']}")
                if context['user_team']:
                    print(f"🔍 DEBUG - Team ID: {context['user_team'].id}")
                
                if context['user_team']:
                    # Check all submissions for this team
                    all_team_submissions = HackathonSubmission.objects.filter(
                        hackathon=hackathon,
                        team=context['user_team']
                    )
                    print(f"🔍 DEBUG - Total team submissions found: {all_team_submissions.count()}")
                    
                    for i, sub in enumerate(all_team_submissions):
                        print(f"  Submission {i+1}:")
                        print(f"    - ID: {sub.id}")
                        print(f"    - Title: '{sub.project_title}'")
                        print(f"    - Has File: {bool(sub.submission_file)}")
                        print(f"    - File value: '{sub.submission_file}'")
                        print(f"    - File name: '{sub.submission_file.name if sub.submission_file else 'None'}'")
                    
                    # 🔥 ALWAYS SHOW AI assignments (even after hackathon ends)
                    ai_assignment_candidates = all_team_submissions.filter(
                        models.Q(submission_file__isnull=True) | 
                        models.Q(submission_file='') |
                        models.Q(submission_file__exact='')
                    )
                    
                    print(f"🔍 DEBUG - AI candidates (no files): {ai_assignment_candidates.count()}")
                    
                    # Get valid AI assignments (have title but no files)
                    valid_ai_assignments = []
                    for candidate in ai_assignment_candidates:
                        if candidate.project_title and candidate.project_title.strip():
                            valid_ai_assignments.append(candidate)
                            print(f"  ✅ Valid AI assignment: '{candidate.project_title}'")
                    
                    # 🔥 ALWAYS show AI assignment regardless of hackathon status
                    context['ai_assigned_project'] = valid_ai_assignments[0] if valid_ai_assignments else None
                    
                    # File submissions (have actual uploaded files)
                    file_submissions = all_team_submissions.exclude(
                        models.Q(submission_file__isnull=True) | 
                        models.Q(submission_file='') |
                        models.Q(submission_file__exact='')
                    )
                    
                    context['user_submission'] = file_submissions.first()
                    
                    print(f"🔍 DEBUG - Final AI project: {context['ai_assigned_project']}")
                    print(f"🔍 DEBUG - File submission: {context['user_submission']}")
                    
                else:
                    # Individual user logic (same fix)
                    individual_submissions = HackathonSubmission.objects.filter(
                        hackathon=hackathon,
                        individual_user=user,
                        team__isnull=True
                    )
                    
                    # AI assignments (no files) - ALWAYS show
                    ai_candidates = individual_submissions.filter(
                        models.Q(submission_file__isnull=True) | 
                        models.Q(submission_file='') |
                        models.Q(submission_file__exact='')
                    )
                    
                    valid_individual_assignments = []
                    for candidate in ai_candidates:
                        if candidate.project_title and candidate.project_title.strip():
                            valid_individual_assignments.append(candidate)
                    
                    # 🔥 ALWAYS show AI assignment regardless of hackathon status
                    context['ai_assigned_project'] = valid_individual_assignments[0] if valid_individual_assignments else None
                    
                    # File submissions
                    context['user_submission'] = individual_submissions.exclude(
                        models.Q(submission_file__isnull=True) | 
                        models.Q(submission_file='') |
                        models.Q(submission_file__exact='')
                    ).first()

            # Check if user is creator
            context['is_creator'] = hackathon.is_user_creator(user)
            context['can_edit'] = context['is_creator'] or user.is_staff

        # Add additional context data
        context.update({
            'timeline_status': hackathon.get_timeline_status(),
            'hackathon_stats': hackathon.get_registration_stats(),
            'submission_stats': hackathon.get_submission_stats(),
            'team_stats': {'total_teams': hackathon.teams.filter(is_active=True).count()},
        })

        # Add user progress if registered
        if context['user_registration']:
            context['user_progress'] = {
                'registered': True,
                'has_team': bool(context['user_team']),
                'has_submission': bool(context['user_submission']),
                # 🔥 Add submission status for better UI handling
                'submission_status': context['user_submission'].evaluation_status if context['user_submission'] else None,
                'can_reenter': True,  # Always allow re-entry to check status
            }

        return render(request, 'user/hackathon_detail.html', context)

    except Exception as e:
        print(f"Error in hackathon_detail view: {e}")
        raise


# views.py



from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .forms import EnhancedHackathonCreateForm  # Using your existing form
from .models import Hackathon

@login_required
def edit_hackathon(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    # Check permissions
    if not (request.user == hackathon.creator or request.user.is_staff):
        messages.error(request, "You don't have permission to edit this hackathon.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    if request.method == 'POST':
        form = EnhancedHackathonCreateForm(request.POST, request.FILES, instance=hackathon)
        if form.is_valid():
            updated_hackathon = form.save()
            
            # Handle evaluation criteria JSON conversion
            if 'evaluation_criteria' in form.cleaned_data:
                try:
                    criteria = json.loads(form.cleaned_data['evaluation_criteria'])
                    updated_hackathon.evaluation_criteria = criteria
                    updated_hackathon.save()
                except json.JSONDecodeError:
                    messages.warning(request, "Evaluation criteria wasn't saved due to invalid format")
            
            messages.success(request, 'Hackathon updated successfully!')
            return redirect('hackathon_detail', hackathon_id=hackathon.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Initialize form with instance data
        initial_data = {
            'evaluation_criteria': json.dumps(hackathon.evaluation_criteria) 
            if hackathon.evaluation_criteria else '{}'
        }
        form = EnhancedHackathonCreateForm(instance=hackathon, initial=initial_data)
    
    context = {
        'form': form,
        'hackathon': hackathon,
        'current_tab': 'edit'
    }
    return render(request, 'user/edit_hackathon.html', context)

from django.db import transaction

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from .models import Hackathon, HackathonRegistration, HackathonSubmission
from .forms import HackathonSubmissionForm
import logging

logger = logging.getLogger(__name__)

@login_required
def submit_hackathon_project(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    reg = get_object_or_404(
        HackathonRegistration,
        hackathon=hackathon, user=request.user, is_active=True
    )

    team_flag = bool(reg.team)
    existing = HackathonSubmission.objects.filter(
        hackathon=hackathon,
        team=reg.team if team_flag else None,
        individual_user=None if team_flag else request.user
    ).first()

    # ---------- POST ----------
    if request.method == "POST":
        form = HackathonSubmissionForm(
            request.POST, request.FILES,
            instance=existing,
            hackathon=hackathon,
            user_registration=reg,
            is_update=bool(existing),
        )

        # fix: guarantee exactly one fk
        form.instance.team = reg.team if team_flag else None
        form.instance.individual_user = None if team_flag else request.user

        if form.is_valid():
            try:
                with transaction.atomic():
                    sub = form.save(commit=False)
                    sub.hackathon = hackathon
                    sub.evaluation_status = HackathonSubmission.EvaluationStatus.IN_PROGRESS
                    sub.save()

                    # 🔥 REAL AI EVALUATION - Replace the fake evaluation
                    print(f"🚀 Starting automatic evaluation for submission {sub.id}: {sub.project_title}")
                    
                    try:
                        # Call your real evaluation function
                        evaluate_submission_task(sub.id)
                        
                        # Refresh from database to get updated scores
                        sub.refresh_from_db()
                        
                        if sub.evaluation_status == HackathonSubmission.EvaluationStatus.COMPLETED:
                            messages.success(request, f"Project submitted and evaluated successfully! Score: {sub.ai_evaluation_score}/100")
                        else:
                            messages.warning(request, "Project submitted. Evaluation completed with fallback scoring due to AI processing issues.")
                            
                    except Exception as eval_error:
                        print(f"❌ Evaluation failed: {eval_error}")
                        
                        # Fallback: Set basic completion status
                        sub.ai_evaluation_notes = f"Evaluation error occurred: {eval_error}. Manual review required."
                        sub.ai_evaluation_score = 50
                        sub.evaluation_status = HackathonSubmission.EvaluationStatus.COMPLETED
                        sub.save(update_fields=['ai_evaluation_notes', 'ai_evaluation_score', 'evaluation_status'])
                        
                        messages.warning(request, "Project submitted but automatic evaluation failed. Manual review will be conducted.")
                    
                return redirect("submission_success", submission_id=sub.id)
                
            except Exception as e:
                print(f"❌ Error during submission: {e}")
                messages.error(request, f"An error occurred while saving your submission: {e}")
        else:
            messages.error(request, "Please fix the errors below.")
            
    # ---------- GET ----------
    else:
        # if we already had an AI idea but no submission_file, pre-fill
        initial = {}
        if existing and not existing.submission_file:
            initial = {
                "project_title": existing.project_title,
                "project_description": existing.project_description,
            }
        form = HackathonSubmissionForm(
            instance=existing if existing and existing.submission_file else None,
            initial=initial,
            hackathon=hackathon,
            user_registration=reg,
            is_update=bool(existing and existing.submission_file),
        )

    return render(request, "user/submit_hackathon.html", {
        "form": form,
        "hackathon": hackathon,
        "existing_submission": existing,
        "user_registration": reg,
        "now": timezone.now(),
        "max_file_size_mb": getattr(hackathon, 'max_file_size_mb', 50),
    })






@login_required
def submission_success(request, submission_id):
    try:
        submission = get_object_or_404(HackathonSubmission, id=submission_id)
        
        # Verify ownership
        if not (submission.individual_user == request.user or 
                (submission.team and request.user in submission.team.members.all())):
            messages.error(request, "You don't have permission to view this submission")
            return redirect('hackathon_detail', hackathon_id=submission.hackathon.id)
        
        context = {
            'submission': submission,
            'hackathon': submission.hackathon,
        }
        return render(request, 'user/submission_success.html', context)
        
    except Exception as e:
        logger.error(f"Error in success view: {str(e)}", exc_info=True)
        messages.error(request, "Error loading submission details")
        return redirect('hackathon_detail', hackathon_id=submission.hackathon.id)

@login_required
def hackathon_dashboard(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    user_registration = HackathonRegistration.objects.filter(
        user=request.user, hackathon=hackathon, is_active=True
    ).first()
    
    if not user_registration:
        messages.error(request, "You must be registered to access the dashboard.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    user_submission = HackathonSubmission.objects.filter(
        hackathon=hackathon,
        individual_user=request.user if not user_registration.team else None,
        team=user_registration.team
    ).select_related('github_repository').first()
    
    team_members = user_registration.team.members.all() if user_registration.team else []
    
    now = timezone.now()
    time_remaining = hackathon.end_date - now if hackathon.end_date > now else None
    
    dashboard_stats = {
        'total_participants': hackathon.current_participants,
        'total_submissions': hackathon.submissions.count(),
        'my_team_size': team_members.count() if team_members else 1,
        'submission_status': 'Submitted' if user_submission else 'Not Submitted'
    }
    
    context = {
        'hackathon': hackathon,
        'user_registration': user_registration,
        'user_submission': user_submission,
        'team_members': team_members,
        'time_remaining': time_remaining,
        'dashboard_stats': dashboard_stats,
        'can_submit': hackathon.can_submit and not user_submission
    }
    return render(request, 'user/hackathon_dashboard.html', context)


# views.py


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Hackathon, HackathonSubmission
from .forms import WinnerSelectionForm  # Assuming you have this form
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .models import Hackathon, HackathonSubmission
from .forms import WinnerSelectionForm


@login_required
def select_winners(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)

    # ─── permissions ───────────────────────────────────────────────
    if hackathon.created_by != request.user:
        messages.error(
            request,
            "You do not have permission to select winners for this hackathon.",
        )
        return redirect("hackathon_detail", hackathon_id=hackathon_id)

    # ─── gather & sort evaluated submissions ───────────────────────
    all_submissions = HackathonSubmission.objects.filter(hackathon=hackathon)

    submissions = [
        sub
        for sub in all_submissions
        if sub.submission_file
        and (sub.final_score or sub.ai_evaluation_score)
    ]

    submissions.sort(
        key=lambda s: s.final_score or s.ai_evaluation_score or 0,
        reverse=True,
    )

    winners = [s for s in submissions if s.is_winner]

    # ─── POST: save every prize choice ─────────────────────────────
    if request.method == "POST":
        try:
            with transaction.atomic():
                # Clear-all button
                if "clear_winners" in request.POST:
                    for s in submissions:
                        s.is_winner = False
                        s.prize_category = ""
                        s.save(update_fields=["is_winner", "prize_category"])
                    messages.info(request, "All winners cleared.")
                    return redirect("select_winners", hackathon_id=hackathon_id)

                updated, winners_chosen = 0, 0

                # Save every row exactly as organiser chose
                for s in submissions:
                    prize = request.POST.get(f"winner_{s.id}", "").strip()

                    if prize:
                        s.prize_category = prize
                        s.is_winner = True
                        winners_chosen += 1
                    else:
                        s.prize_category = ""
                        s.is_winner = False

                    s.save(update_fields=["prize_category", "is_winner"])
                    updated += 1

                messages.success(
                    request,
                    f"Saved {updated} rows – {winners_chosen} prize"
                    f"{'' if winners_chosen == 1 else 's'} assigned.",
                )

                # Publish button or auto-publish
                if (
                    ("publish_results" in request.POST)
                    or ("auto_publish" in request.POST and winners_chosen)
                ):
                    # rank by score
                    for rank, s in enumerate(
                        sorted(
                            submissions,
                            key=lambda x: x.final_score
                            or x.ai_evaluation_score
                            or 0,
                            reverse=True,
                        ),
                        start=1,
                    ):
                        s.rank = rank
                        s.save(update_fields=["rank"])

                    if hackathon.status != "completed":
                        hackathon.status = "completed"
                        hackathon.save(update_fields=["status"])
                        messages.success(
                            request,
                            "🎉 Results published! Hackathon marked completed.",
                        )

                    return redirect(
                        "hackathon_results", hackathon_id=hackathon_id
                    )

        except Exception as e:
            messages.error(request, f"Error selecting winners: {e}")
            return redirect("select_winners", hackathon_id=hackathon_id)

        # After processing POST, always redirect (already done above).

    # ─── GET: render the page ──────────────────────────────────────
    submissions_with_scores = [
        {
            "submission": s,
            "display_score": s.final_score or s.ai_evaluation_score or 0,
            "score_type": "Manual" if s.final_score else "AI",
        }
        for s in submissions
    ]

    prize_categories = [
        ("first_place", "🥇 1st Place"),
        ("second_place", "🥈 2nd Place"),
        ("third_place", "🥉 3rd Place"),
        ("best_innovation", "💡 Best Innovation"),
        ("best_design", "🎨 Best Design"),
        ("peoples_choice", "👥 People's Choice"),
        ("special_recognition", "🏆 Special Recognition"),
    ]

    context = {
        "hackathon": hackathon,
        "submissions": submissions,
        "submissions_with_scores": submissions_with_scores,
        "winners": winners,
        "prize_categories": prize_categories,
        "total_submissions": len(submissions),
        "winners_count": len(winners),
        "can_publish": bool(submissions),
    }
    return render(request, "user/select_winners.html", context)




@login_required
def publish_results(request, hackathon_id):
    """
    Final step: make winners public and mark the hackathon as completed.
    Only the creator can perform this action.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    hackathon = get_object_or_404(Hackathon, id=hackathon_id)

    # Security – only the creator may publish
    if hackathon.created_by != request.user:
        messages.error(request, "You do not have permission to publish results.")
        return redirect("select_winners", hackathon_id=hackathon_id)

    # There must be at least one winner
    winners_qs = HackathonSubmission.objects.filter(
        hackathon=hackathon, is_winner=True
    )
    if not winners_qs.exists():
        messages.error(request, "Select at least one winner before publishing.")
        return redirect("select_winners", hackathon_id=hackathon_id)

    with transaction.atomic():
        # Ensure every winner has a rank; fall back to 1-based order if missing
        for idx, sub in enumerate(
            winners_qs.order_by("rank", "-final_score", "-ai_evaluation_score"), 1
        ):
            if not sub.rank:
                sub.rank = idx
                sub.save(update_fields=["rank"])

        # Close the hackathon
        if hackathon.status != "completed":
            hackathon.status = "completed"
            hackathon.save(update_fields=["status"])

    messages.success(request, "🎉 Results published and hackathon marked as completed!")
    return redirect("hackathon_results", hackathon_id=hackathon_id)




from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from celery import shared_task
from .models import Hackathon, HackathonSubmission, HackathonEvaluation

# -----------------------------
# Single Submission Evaluation
# -----------------------------
@login_required
def evaluate_single_submission(request, submission_id):
    submission = get_object_or_404(HackathonSubmission, id=submission_id)
    hackathon = submission.hackathon

    if not hackathon:
        messages.error(request, "Hackathon not found for this submission.")
        return redirect('home')

    # Permission check
    if not (request.user == hackathon.created_by or request.user.is_staff):
        messages.error(request, "You don't have permission to evaluate this submission.")
        return redirect('hackathon_detail', hackathon.id)

    # Load criteria
    criteria = hackathon.evaluation_criteria or {}
    if not isinstance(criteria, dict) or not criteria:
        messages.error(request, "Evaluation criteria not set or invalid.")
        return redirect('evaluate_submissions', hackathon_id=hackathon.id)

    # Get or create evaluation
    evaluation, _ = HackathonEvaluation.objects.get_or_create(
        submission=submission,
        evaluator=request.user,
        defaults={'scores': {}, 'comments': ''}
    )

    # Dynamic form generation
    class DynamicEvaluationForm(forms.Form):
        comments = forms.CharField(
            widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            required=False,
            label="Evaluator Comments"
        )
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for key, max_score in criteria.items():
                self.fields[f'score_{key}'] = forms.IntegerField(
                    label=key.replace('_', ' ').capitalize(),
                    min_value=0,
                    max_value=max_score,
                    initial=evaluation.scores.get(key, 0),
                    widget=forms.NumberInput(attrs={'class': 'form-range slider', 'step': 1})
                )

    if request.method == 'POST':
        form = DynamicEvaluationForm(request.POST)
        if form.is_valid():
            try:
                evaluation.scores = {
                    key: form.cleaned_data[f'score_{key}']
                    for key in criteria
                }
                evaluation.comments = form.cleaned_data['comments']
                evaluation.save()

                # Update submission final score
                total_score = sum(evaluation.scores.values())
                avg_score = round(total_score / len(criteria), 2)
                submission.final_score = avg_score
                submission.save()

                messages.success(request, "Evaluation saved successfully.")
                return redirect('evaluate_submissions', hackathon_id=hackathon.id)
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        initial_data = {f'score_{key}': evaluation.scores.get(key, 0) for key in criteria}
        initial_data['comments'] = evaluation.comments
        form = DynamicEvaluationForm(initial=initial_data)

    return render(request, 'user/evaluation_form.html', {
        'submission': submission,
        'form': form,
        'criteria': criteria,
        'max_score': max(criteria.values()) if criteria else 10,
        'hackathon_id': hackathon.id,  # ✅ This line is the key fix
    })

# -----------------------------
# Hackathon Submission List View
# -----------------------------


logger = logging.getLogger('ai_evaluation')


def evaluate_submission_task(submission_id):
    """
    Evaluate submission using OpenRouter Mistral model with comprehensive error handling
    """
    try:
        _do_evaluation_internal(submission_id)
    except Exception as exc:
        # Absolute last-chance error handler
        logger.exception(f"Fatal error during evaluation of submission {submission_id}: {exc}")
        try:
            submission = HackathonSubmission.objects.get(id=submission_id)
            submission.evaluation_status = HackathonSubmission.EvaluationStatus.ERROR
            submission.ai_evaluation_notes = f"Fatal evaluation error: {exc}"
            submission.ai_evaluation_score = settings.AI_EVALUATION_SETTINGS["FALLBACK_SCORE"]
            submission.final_score = submission.ai_evaluation_score
            submission.save(update_fields=[
                "evaluation_status", "ai_evaluation_notes",
                "ai_evaluation_score", "final_score"
            ])
            logger.error(f"Marked submission {submission_id} as ERROR due to fatal exception")
        except Exception as save_exc:
            logger.exception(f"Could not even save error status for submission {submission_id}: {save_exc}")


def _do_evaluation_internal(submission_id):
    """
    Internal evaluation logic - all your existing code moved here
    """
    try:
        submission = HackathonSubmission.objects.get(id=submission_id)
        logger.info(f"Starting AI evaluation for submission {submission_id} - Type: {'Team' if submission.team else 'Individual'}")
    except HackathonSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found")
        return

    # Mark as in progress
    submission.evaluation_status = HackathonSubmission.EvaluationStatus.IN_PROGRESS
    submission.save(update_fields=['evaluation_status'])
    logger.info(f"Marked submission {submission_id} as IN_PROGRESS")

    # Process the uploaded zip file
    try:
        if not submission.submission_file:
            raise ValueError("No submission file uploaded")

        logger.info(f"Processing zip file for submission {submission_id}: {submission.submission_file}")
        file_content = ""
        
        with zipfile.ZipFile(submission.submission_file, 'r') as z:
            file_list = z.namelist()
            logger.info(f"Zip contains {len(file_list)} files: {file_list[:10]}...")  # Log first 10 files
            
            for filename in file_list:
                if any(filename.endswith(ext) for ext in settings.AI_EVALUATION_SETTINGS['SUPPORTED_EXTENSIONS']):
                    try:
                        content = z.read(filename).decode('utf-8', errors='ignore')
                        file_content += f"--- File: {filename} ---\n{content}\n\n"
                        logger.debug(f"Successfully read {filename} ({len(content)} chars)")
                    except Exception as e:
                        logger.warning(f"Could not read {filename}: {e}")
                        file_content += f"--- File: {filename} (unreadable) ---\n\n"

        if not file_content.strip():
            file_content = "No supported code files found in submission."
            logger.warning(f"No supported code files found in submission {submission_id}")
        else:
            logger.info(f"Extracted {len(file_content)} characters from submission {submission_id}")

    except zipfile.BadZipFile as e:
        logger.error(f"Bad zip file for submission {submission_id}: {e}")
        submission.evaluation_status = HackathonSubmission.EvaluationStatus.ERROR
        submission.ai_evaluation_notes = f"Invalid zip file: {e}"
        submission.ai_evaluation_score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        submission.final_score = submission.ai_evaluation_score
        submission.save(update_fields=['evaluation_status', 'ai_evaluation_notes', 'ai_evaluation_score', 'final_score'])
        return
    except Exception as e:
        logger.error(f"Error processing submission {submission_id}: {e}")
        submission.evaluation_status = HackathonSubmission.EvaluationStatus.ERROR
        submission.ai_evaluation_notes = f"File processing error: {e}"
        submission.ai_evaluation_score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        submission.final_score = submission.ai_evaluation_score
        submission.save(update_fields=['evaluation_status', 'ai_evaluation_notes', 'ai_evaluation_score', 'final_score'])
        return

    # Truncate if too large
    max_size = settings.AI_EVALUATION_SETTINGS['MAX_FILE_SIZE']
    if len(file_content) > max_size:
        logger.info(f"Truncating content from {len(file_content)} to {max_size} chars for submission {submission_id}")
        file_content = file_content[:max_size] + "\n\n...[content truncated]"

    # Build the evaluation prompt
    submission_type = "Team" if submission.team else "Individual"
    prompt = f"""You are an expert code reviewer evaluating a hackathon submission.

SUBMISSION DETAILS:
- Type: {submission_type} submission
- Project: {submission.project_title}
- Description: {submission.project_description}
- Hackathon: {submission.hackathon.name}

CODE FILES:
{file_content}

Please evaluate this submission and respond with ONLY valid JSON:
{{
  "summary": "Brief overview of the submission",
  "strength": "Main strengths identified", 
  "improvement": "Areas for improvement",
  "score": <number from 0 to 100>
}}

Scoring criteria:
- Code quality and structure (25%)
- Project completion (25%) 
- Innovation and creativity (25%)
- Alignment with description (25%)"""

    # Prepare API request
    try:
        api_key = settings.VALIDATE_OPENROUTER_SETUP()
        logger.info(f"API key validated successfully for submission {submission_id}")
    except Exception as e:
        logger.error(f"API key validation failed for submission {submission_id}: {e}")
        submission.evaluation_status = HackathonSubmission.EvaluationStatus.ERROR
        submission.ai_evaluation_notes = f"API key validation error: {e}"
        submission.ai_evaluation_score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        submission.final_score = submission.ai_evaluation_score
        submission.save(update_fields=['evaluation_status', 'ai_evaluation_notes', 'ai_evaluation_score', 'final_score'])
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.OPENROUTER_SITE_URL,
        "X-Title": settings.OPENROUTER_SITE_NAME,
    }

    payload = {
        "model": settings.AI_EVALUATION_SETTINGS['MODEL'],
        "messages": [
            {"role": "system", "content": "You are an experienced software engineer and hackathon judge. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": settings.AI_EVALUATION_SETTINGS['MAX_TOKENS'],
        "temperature": settings.AI_EVALUATION_SETTINGS['TEMPERATURE'],
    }

    logger.info(f"Prepared API request for submission {submission_id} with model {settings.AI_EVALUATION_SETTINGS['MODEL']}")

    # Call OpenRouter API
    try:
        logger.info(f"Calling OpenRouter API for submission {submission_id}")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=settings.AI_EVALUATION_SETTINGS['TIMEOUT']
        )
        
        logger.info(f"OpenRouter API responded with status {response.status_code} for submission {submission_id}")
        
        if response.status_code == 200:
            api_response = response.json()
            content = api_response['choices'][0]['message']['content'].strip()
            logger.info(f"Received API response for submission {submission_id}: {content[:100]}...")
            
            # ✅ IMPROVED: Better JSON parsing with multiple extraction methods
            try:
                logger.info(f"Raw API response for submission {submission_id}: {content[:200]}...")
                
                # Method 1: Try to find complete JSON object
                start = content.find('{')
                end = content.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = content[start:end]
                    logger.info(f"Extracted JSON string: {json_str[:100]}...")
                    
                    try:
                        json_data = json.loads(json_str)
                        logger.info(f"Successfully parsed JSON for submission {submission_id}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode failed: {e}. Trying to fix truncated JSON...")
                        
                        # Method 2: Try to fix truncated JSON by adding missing closing braces
                        if json_str.count('{') > json_str.count('}'):
                            missing_braces = json_str.count('{') - json_str.count('}')
                            json_str += '}' * missing_braces
                            logger.info(f"Added {missing_braces} closing braces")
                            
                            try:
                                json_data = json.loads(json_str)
                                logger.info(f"Successfully parsed fixed JSON for submission {submission_id}")
                            except json.JSONDecodeError:
                                raise ValueError("Could not parse even after fixing braces")
                        else:
                            raise ValueError("JSON structure is corrupted")
                else:
                    raise ValueError("No JSON found in response")
                
                # ✅ Handle both old and new response formats
                if 'score' in json_data:
                    # New format with score field
                    score = float(json_data.get('score', settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']))
                    summary = json_data.get('summary', 'AI evaluation completed')
                    strength = json_data.get('strength', json_data.get('strengths', 'Code structure present'))
                    improvement = json_data.get('improvement', json_data.get('improvements', 'Continue developing'))
                else:
                    # Old format - extract from summary/strength text and assign fallback score
                    summary = json_data.get('summary', 'AI evaluation completed')
                    strength = json_data.get('strength', 'Code analysis performed')
                    improvement = json_data.get('improvement', 'Areas for enhancement identified')
                    
                    # ✅ FIXED: Handle strength as array (which is what we're seeing)
                    if isinstance(strength, list):
                        strength = ' '.join(strength)
                    if isinstance(improvement, list):
                        improvement = ' '.join(improvement)
                    
                    # Generate score based on content analysis (fallback)
                    score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
                    
                    # Try to infer score from text content
                    combined_text = f"{summary} {strength}".lower()
                    if any(word in combined_text for word in ['excellent', 'great', 'outstanding']):
                        score = 85
                    elif any(word in combined_text for word in ['good', 'well', 'solid']):
                        score = 75
                    elif any(word in combined_text for word in ['basic', 'simple', 'needs']):
                        score = 60
                
                score = max(0, min(100, score))  # Ensure score is between 0-100
                
                notes = f"AI Evaluation Summary:\n{summary}\n\nStrengths:\n{strength}\n\nAreas for Improvement:\n{improvement}"
                
                logger.info(f"OpenRouter evaluation successful for submission {submission_id}: Score {score}")
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not parse JSON response for submission {submission_id}: {e}")
                logger.warning(f"Raw response was: {content[:1000]}...")
                
                # ✅ FALLBACK: Extract data using regex if JSON parsing fails completely
                score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
                
                # Try to extract summary using regex
                import re
                summary_match = re.search(r'"summary":\s*"([^"]*)"', content)
                summary = summary_match.group(1) if summary_match else "AI evaluation completed"
                
                # Try to extract strength using regex
                strength_match = re.search(r'"strength":\s*\[?"([^"]*)"', content)
                strength = strength_match.group(1) if strength_match else "Code analysis performed"
                
                # Smart scoring based on extracted content
                combined_text = f"{summary} {strength}".lower()
                if any(word in combined_text for word in ['excellent', 'great', 'outstanding', 'comprehensive']):
                    score = 80
                elif any(word in combined_text for word in ['good', 'well', 'solid', 'demonstrates']):
                    score = 70
                elif any(word in combined_text for word in ['basic', 'simple', 'needs', 'limited']):
                    score = 55
                
                notes = f"AI Evaluation Summary:\n{summary}\n\nStrengths:\n{strength}\n\nAreas for Improvement:\nContinue developing and refining the implementation"
                
                logger.info(f"Fallback parsing successful for submission {submission_id}: Score {score}")
        
        else:
            error_text = response.text
            logger.error(f"OpenRouter API error {response.status_code} for submission {submission_id}: {error_text}")
            score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
            notes = f"OpenRouter API error {response.status_code}: {error_text}"

    except requests.exceptions.Timeout:
        logger.error(f"OpenRouter API timeout for submission {submission_id}")
        score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        notes = "Evaluation timed out - OpenRouter API did not respond within the timeout period"

    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter API request exception for submission {submission_id}: {e}")
        score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        notes = f"Network error during evaluation: {e}"

    except Exception as e:
        logger.error(f"OpenRouter API exception for submission {submission_id}: {e}")
        score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
        notes = f"Unexpected evaluation error: {str(e)}"

    # Save results
    logger.info(f"Saving evaluation results for submission {submission_id}: score={score}")
    
    submission.ai_evaluation_notes = notes
    submission.ai_evaluation_score = score
    submission.final_score = score  # Keep both in sync
    submission.evaluation_status = HackathonSubmission.EvaluationStatus.COMPLETED
    submission.save(update_fields=[
        'ai_evaluation_notes',
        'ai_evaluation_score',
        'final_score', 
        'evaluation_status'
    ])
    
    logger.info(f"✅ Evaluation completed for submission {submission_id} with score {score}/100")



# ✅ NEW: Add manual retry function
@login_required
def retry_ai_evaluation(request, submission_id):
    """Allow manual retry of AI evaluation"""
    submission = get_object_or_404(HackathonSubmission, id=submission_id)
    
    # Check permissions
    can_retry = False
    if submission.individual_user == request.user:
        can_retry = True
    elif submission.team and request.user in submission.team.members.all():
        can_retry = True
    elif submission.hackathon.created_by == request.user:
        can_retry = True
    
    if not can_retry:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if not submission.submission_file:
        return JsonResponse({'error': 'No file to evaluate'}, status=400)
    
    # Reset and retry
    submission.ai_evaluation_triggered = False
    submission.evaluation_status = submission.EvaluationStatus.PENDING
    submission.ai_evaluation_score = None
    submission.ai_evaluation_notes = ""
    submission.save()
    
    # Trigger evaluation
    submission.trigger_ai_evaluation()
    
    return JsonResponse({
        'success': True, 
        'message': 'AI evaluation started. Refresh the page in a few moments.'
    })


def _write_results(submission, score, detail):
    """Store notes + score; keep both ai_evaluation_score & final_score"""
    if not isinstance(score, (int, float)):
        score = settings.AI_EVALUATION_SETTINGS["FALLBACK_SCORE"]
    score = max(0, min(100, float(score)))

    if isinstance(detail, dict):
        notes = (
            f"Summary: {detail.get('summary', '—')}\n"
            f"Strength: {detail.get('strength', '—')}\n"
            f"Improvement: {detail.get('improvement', '—')}"
        )
    else:
        notes = detail  # simple string fallback

    submission.ai_evaluation_notes = notes
    submission.ai_evaluation_score = score       # public leaderboard
    submission.final_score = score               # keep in sync for admin
    submission.evaluation_status = HackathonSubmission.EvaluationStatus.COMPLETED
    submission.save(
        update_fields=[
            "ai_evaluation_notes",
            "ai_evaluation_score",
            "final_score",
            "evaluation_status",
        ]
    )

    logger.info("Finished submission %s – score %.0f/100", submission.id, score)


# ------------------------------------------------------------------ helpers
def _parse_ai_json(text: str) -> dict:
    try:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise ValueError("No JSON found")
    except Exception as e:
        logger.warning(f"JSON parse error: {e}")
        return {"summary": "Parse error", "strength": "N/A", "improvement": "N/A", "score": 50}


def _rule_based_fallback(file_content: str, submission) -> dict:
    logger.info(f"Using fallback scoring for submission {submission.id}")
    score = settings.AI_EVALUATION_SETTINGS["FALLBACK_SCORE"]
    lines = file_content.splitlines()
    file_cnt = file_content.count("--- File:")

    if file_cnt >= 3:
        score += 15
    if len(lines) > 50:
        score += 10
    if any(k in file_content for k in ("def ", "function ")):
        score += 10
    if "class " in file_content:
        score += 5
    if any(k in file_content.lower() for k in ("import", "require", "include")):
        score += 5
    if "readme" in file_content.lower():
        score += 10

    words = (submission.project_title + " " + submission.project_description).lower().split()
    matches = sum(1 for w in words if len(w) > 3 and w in file_content.lower())
    score += min(15, matches * 2)

    score = max(0, min(100, score))
    return {
        "summary": f"Fallback analysis – {file_cnt} files, {len(lines)} lines",
        "strength": "Basic code structure present",
        "improvement": "Add documentation and tests",
        "score": score,
    }


@login_required
def evaluate_submissions(request, hackathon_id):
    """
    Creator-only view that shows all submissions, lets you grade each
    one, and writes the result into BOTH final_score and
    ai_evaluation_score so the public leaderboard updates immediately.
    """
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)

    # ─── permission guard ────────────────────────────────
    if hackathon.created_by != request.user:
        messages.error(request, "You don't have permission to evaluate here.")
        return redirect("hackathon_detail", hackathon_id=hackathon.id)

    # ─── POST: save one submission ───────────────────────
    if request.method == "POST":
        sub_id = request.POST.get("submission_id")
        submission = get_object_or_404(
            HackathonSubmission, id=sub_id, hackathon=hackathon
        )

        form = ManualScoreForm(request.POST, instance=submission)
        if form.is_valid():
            sub = form.save(commit=False)

            total = form.cleaned_data["calculated_overall"]    # 0-100

            # keep both columns in sync
            sub.final_score         = total
            sub.ai_evaluation_score = total
            
            # ✅ ADD PRIZE ASSIGNMENT LOGIC
            prize_category = request.POST.get('prize_category', '')
            
            if prize_category:
                sub.prize_category = prize_category
                sub.is_winner = True
                messages.success(
                    request,
                    f'Saved {total}/100 for "{sub.project_title}" and assigned {prize_category.replace("_", " ").title()} prize!'
                )
            else:
                sub.prize_category = ''
                sub.is_winner = False
                messages.success(
                    request,
                    f'Saved {total}/100 for "{sub.project_title}".'
                )
            
            sub.save()

        else:
            messages.error(request, "Please correct the errors and try again.")

        return redirect("evaluate_submissions", hackathon_id=hackathon.id)

    # ─── GET: list all submissions ───────────────────────
    submissions = (
        HackathonSubmission.objects
        .filter(hackathon=hackathon, submission_file__isnull=False)
        .select_related("individual_user", "team")
        .order_by("-submitted_at")
    )

    return render(
        request,
        "user/evaluate_submissions.html",
        {"hackathon": hackathon, "submissions": submissions},
    )





@login_required
def hackathon_results(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    if hackathon.status != 'completed':
        messages.info(request, 'Results for this hackathon are not yet available.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    # Get all submissions and filter in Python
    all_submissions_raw = hackathon.user_uploaded_submissions.all()
    
    all_submissions = []
    scores = []
    
    for sub in all_submissions_raw:
        # Skip AI assignments without files
        if not sub.submission_file:
            continue
        # Skip if no evaluation
        if not sub.final_score and not sub.ai_evaluation_score:
            continue
            
        score = sub.final_score or sub.ai_evaluation_score
        scores.append(score)
        all_submissions.append(sub)
    
    # Sort by score
    all_submissions.sort(key=lambda x: x.final_score or x.ai_evaluation_score or 0, reverse=True)
    
    winners = [sub for sub in all_submissions if sub.is_winner]
    
    stats = {
        'total_participants': hackathon.current_participants,
        'total_submissions': len(all_submissions),
        'total_winners': len(winners),
        'average_score': sum(scores) / len(scores) if scores else 0,
        'top_score': max(scores) if scores else 0,
    }
    
    context = {
        'hackathon': hackathon,
        'winners': winners,
        'all_submissions': all_submissions[:20],  # Top 20
        'stats': stats,
        'is_creator': hackathon.created_by == request.user,
    }
    
    return render(request, 'user/hackathon_results.html', context)

@login_required
def manage_team(request, hackathon_id):
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    is_creator = hackathon.created_by == request.user
    user_registration = HackathonRegistration.objects.filter(
        user=request.user,
        hackathon=hackathon,
        is_active=True
    ).first()
    
    if not is_creator and not user_registration:
        messages.error(request, 'You must be registered for this hackathon.')
        return redirect('hackathon_detail', hackathon_id=hackathon_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_team':
            team_name = request.POST.get('team_name', '').strip()
            team_description = request.POST.get('team_description', '').strip()
            
            if team_name and user_registration and not user_registration.team:
                try:
                    team = HackathonTeam.objects.create(
                        hackathon=hackathon,
                        name=team_name,
                        description=team_description,
                        leader=request.user,
                        is_active=True
                    )
                    
                    user_registration.team = team
                    user_registration.participation_type = 'team'
                    user_registration.save()
                    
                    messages.success(request, f'🎉 Team "{team_name}" created! Invite code: {team.invite_code}')
                except Exception as e:
                    messages.error(request, f'Error creating team: {str(e)}')
        
        elif action == 'join_team':
            invite_code = request.POST.get('invite_code', '').strip().upper()
            if invite_code and user_registration and not user_registration.team:
                try:
                    team = HackathonTeam.objects.get(
                        invite_code=invite_code, 
                        hackathon=hackathon, 
                        is_active=True
                    )
                    if team.member_count < hackathon.team_size_max:
                        team.members.add(request.user)
                        user_registration.team = team
                        user_registration.participation_type = 'team'
                        user_registration.save()
                        messages.success(request, f'🎉 Joined team "{team.name}"!')
                    else:
                        messages.error(request, 'Team is full.')
                except HackathonTeam.DoesNotExist:
                    messages.error(request, 'Invalid invite code.')
                except Exception as e:
                    messages.error(request, f'Error joining team: {str(e)}')
        
        # ✅ REMOVED: join_team_direct action completely
        
        elif action == 'leave_team':
            if user_registration and user_registration.team:
                try:
                    team = user_registration.team
                    team.members.remove(request.user)
                    
                    if team.leader == request.user:
                        remaining_members = team.members.all()
                        if remaining_members.exists():
                            team.leader = remaining_members.first()
                            team.save()
                        else:
                            team.delete()
                    
                    user_registration.team = None
                    user_registration.participation_type = 'individual'
                    user_registration.save()
                    
                    messages.success(request, 'Left team successfully.')
                except Exception as e:
                    messages.error(request, f'Error leaving team: {str(e)}')
        
        return redirect('manage_team', hackathon_id=hackathon_id)
    
    user_team = user_registration.team if user_registration else None
    all_teams = HackathonTeam.objects.filter(
        hackathon=hackathon,
        is_active=True
    ).prefetch_related('members', 'leader').order_by('-created_at')
    
    total_participants = HackathonRegistration.objects.filter(
        hackathon=hackathon,
        is_active=True
    ).count()
    
    context = {
        'hackathon': hackathon,
        'is_creator': is_creator,
        'user_registration': user_registration,
        'user_team': user_team,
        'all_teams': all_teams,
        'total_participants': total_participants,
    }
    
    return render(request, 'user/manage_team.html', context)




# ============================================
# ADMIN HACKATHON MANAGEMENT VIEWS
# ============================================

# @login_required
# @user_passes_test(is_admin)
# def admin_hackathon_management(request):
#     """Enhanced admin hackathon management"""
#     if request.method == 'POST':
#         form = HackathonCreateForm(request.POST, request.FILES)
#         if form.is_valid():
#             hackathon = form.save(commit=False)
#             hackathon.created_by = request.user
#             hackathon.save()
#             messages.success(request, 'Hackathon created successfully!')
#             return redirect('admin_hackathon_management')
#     else:
#         form = HackathonCreateForm()
    
#     hackathons = Hackathon.objects.annotate(
#         participant_count=Count('registrations', filter=Q(registrations__is_active=True)),
#         submission_count=Count('submissions'),
#         team_count=Count('teams', filter=Q(teams__is_active=True))
#     ).order_by('-created_at')
    
#     context = {
#         'form': form,
#         'hackathons': hackathons,
#     }
    
#     return render(request, 'admin/hackathon_management.html', context)

# @login_required
# @user_passes_test(is_admin)
# def evaluate_submissions(request, hackathon_id):
#     """Evaluate hackathon submissions"""
#     hackathon = get_object_or_404(Hackathon, id=hackathon_id)
#     submissions = hackathon.submissions.all().order_by('-submitted_at')
    
#     if request.method == 'POST':
#         submission_id = request.POST.get('submission_id')
#         submission = get_object_or_404(HackathonSubmission, id=submission_id)
        
#         # Create evaluation form with hackathon criteria
#         form = HackathonEvaluationForm(request.POST, criteria=hackathon.evaluation_criteria)
        
#         if form.is_valid():
#             # Extract scores
#             scores = {}
#             for criterion in hackathon.evaluation_criteria.keys():
#                 score = form.cleaned_data.get(f'score_{criterion}')
#                 if score is not None:
#                     scores[criterion] = score
            
#             # Create or update evaluation
#             evaluation, created = HackathonEvaluation.objects.get_or_create(
#                 submission=submission,
#                 evaluator=request.user,
#                 defaults={
#                     'scores': scores,
#                     'comments': form.cleaned_data.get('comments', '')
#                 }
#             )
            
#             if not created:
#                 evaluation.scores = scores
#                 evaluation.comments = form.cleaned_data.get('comments', '')
#                 evaluation.save()
            
#             # Calculate weighted final score
#             total_weight = sum(hackathon.evaluation_criteria.values())
#             final_score = sum(
#                 score * hackathon.evaluation_criteria[criterion] / hackathon.evaluation_criteria[criterion] * 100
#                 for criterion, score in scores.items()
#             ) / len(scores) if scores else 0
            
#             submission.scores = scores
#             submission.final_score = final_score
#             submission.save()
            
#             messages.success(request, 'Evaluation saved successfully!')
#             return redirect('evaluate_submissions', hackathon_id=hackathon.id)
    
#     # Create forms for each submission
#     submission_forms = []
#     for submission in submissions:
#         form = HackathonEvaluationForm(criteria=hackathon.evaluation_criteria)
        
#         # Pre-populate if already evaluated by current user
#         existing_eval = HackathonEvaluation.objects.filter(
#             submission=submission,
#             evaluator=request.user
#         ).first()
        
#         if existing_eval:
#             initial_data = {'comments': existing_eval.comments}
#             for criterion, score in existing_eval.scores.items():
#                 initial_data[f'score_{criterion}'] = score
#             form = HackathonEvaluationForm(initial=initial_data, criteria=hackathon.evaluation_criteria)
        
#         submission_forms.append({
#             'submission': submission,
#             'form': form,
#             'evaluated': existing_eval is not None
#         })
    
#     context = {
#         'hackathon': hackathon,
#         'submission_forms': submission_forms,
#     }
    
#     return render(request, 'admin/evaluate_submissions.html', context)

# @login_required
# @user_passes_test(is_admin)
# def select_winners(request, hackathon_id):
#     """Select hackathon winners"""
#     hackathon = get_object_or_404(Hackathon, id=hackathon_id)
#     submissions = hackathon.submissions.filter(
#         final_score__isnull=False
#     ).order_by('-final_score')
    
#     if request.method == 'POST':
#         action = request.POST.get('action')
        
#         if action == 'mark_winners':
#             winner_ids = request.POST.getlist('winners')
            
#             # Clear existing winners
#             hackathon.submissions.update(is_winner=False, prize_category='')
            
#             # Mark new winners
#             for i, submission_id in enumerate(winner_ids):
#                 submission = get_object_or_404(HackathonSubmission, id=submission_id)
#                 submission.is_winner = True
                
#                 # Set prize category based on rank
#                 if i == 0:
#                     submission.prize_category = '1st Place'
#                 elif i == 1:
#                     submission.prize_category = '2nd Place'
#                 elif i == 2:
#                     submission.prize_category = '3rd Place'
#                 else:
#                     submission.prize_category = f'{i+1}th Place'
                
#                 submission.save()
            
#             messages.success(request, f'{len(winner_ids)} winners selected successfully!')
        
#         elif action == 'complete_hackathon':
#             hackathon.status = 'completed'
#             hackathon.save()
#             messages.success(request, 'Hackathon marked as completed!')
    
#     context = {
#         'hackathon': hackathon,
#         'submissions': submissions,
#     }
    
#     return render(request, 'admin/select_winners.html', context)

# ============================================
# ASSESSMENT AND QUIZ RELATED VIEWS (ORGANIZED)
# ============================================



@login_required
def start_quiz(request, competency_id):
    """Start a new quiz or continue existing in-progress attempt"""
    competency = get_object_or_404(Competency, id=competency_id, is_active=True)
    
    # Ensure UserCompetency exists
    user_comp, _ = UserCompetency.objects.get_or_create(
        user=request.user, 
        competency=competency, 
        defaults={'score': 0}
    )
    
    # Get or create quiz settings
    settings, _ = QuizSettings.objects.get_or_create(competency=competency)

    # Check for existing in-progress attempt
    ongoing = QuizAttempt.objects.filter(
        user=request.user, 
        competency=competency, 
        status='in_progress'
    ).first()
    
    if ongoing:
        # Check if attempt has expired
        if ongoing.is_expired:
            ongoing.status = 'timed_out'
            ongoing.save()
            messages.warning(request, "Previous quiz attempt timed out. Starting new attempt.")
        else:
            return redirect('take_quiz', attempt_id=ongoing.id)

    # Check if there are enough questions
    available_questions = Question.objects.filter(
        competency=competency, 
        is_active=True
    ).count()
    
    if available_questions < settings.question_count:
        messages.error(request, f"Not enough questions available for this competency. Contact administrator.")
        return redirect('assessment')

    # Create new quiz attempt
    try:
        attempt = QuizAttempt.objects.create(
            user=request.user,
            competency=competency,
            ip_address=get_client_ip(request),
            metadata={
                'time_limit': settings.time_limit,
                'question_count': settings.question_count,
                'passing_score': settings.passing_score,
                'shuffle_questions': settings.shuffle_questions,
                'shuffle_answers': settings.shuffle_answers,
            }
        )
        
        # CRITICAL FIX: Generate questions once and store them
        question_objs = get_quiz_questions(attempt)
        attempt.metadata['question_ids'] = [q.id for q in question_objs]
        attempt.save(update_fields=['metadata'])
        
        # Update user competency attempt count
        user_comp.attempts_count += 1
        user_comp.save()
        
        return redirect('take_quiz', attempt_id=attempt.id)
        
    except Exception as e:
        messages.error(request, "Error starting quiz. Please try again.")
        return redirect('assessment')

@login_required
def submit_answer(request, attempt_id):
    """Handle quiz answer submission with proper error handling and flow control"""
    if request.method != 'POST':
        messages.error(request, "Invalid request method")
        return redirect('assessment')

    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)
    
    # Check if quiz is still in progress
    if attempt.status != 'in_progress':
        return redirect('quiz_results', attempt_id=attempt.id)

    # Validate required data
    question_id = request.POST.get('question_id')
    answer_id = request.POST.get('answer_id')
    time_used = request.POST.get('time_used', 0)

    if not question_id or not answer_id:
        messages.error(request, "Missing answer data")
        return redirect('take_quiz', attempt_id=attempt.id)

    try:
        question = get_object_or_404(Question, id=question_id)
        answer = get_object_or_404(Answer, id=answer_id, question=question)

        # Create or update quiz response (handle duplicates gracefully)
        quiz_response, created = QuizResponse.objects.get_or_create(
            quiz_attempt=attempt,
            question=question,
            defaults={
                'answer': answer,
                'is_correct': answer.is_correct,
                'response_time': float(time_used) if time_used else 0
            }
        )

        # If response already existed, update it with new answer
        if not created:
            quiz_response.answer = answer
            quiz_response.is_correct = answer.is_correct
            quiz_response.response_time = float(time_used) if time_used else 0
            quiz_response.save()

        # Get question IDs from metadata (FIXED)
        question_ids = attempt.metadata.get('question_ids', [])
        total_questions = len(question_ids)

        # Move to next question
        attempt.current_question += 1
        attempt.save()

        # Check if quiz is complete
        if attempt.current_question >= total_questions:
            return complete_quiz(request, attempt)

        # Continue to next question
        return redirect('take_quiz', attempt_id=attempt.id)

    except Exception as e:
        messages.error(request, "Error processing your answer. Please try again.")
        return redirect('take_quiz', attempt_id=attempt.id)

def complete_quiz(request, attempt):
    """Complete quiz and calculate final score"""
    try:
        # Get all responses for this attempt
        responses = QuizResponse.objects.filter(quiz_attempt=attempt)
        total_responses = responses.count()
        correct_responses = responses.filter(is_correct=True).count()

        # Calculate final score
        final_score = (correct_responses / total_responses * 100) if total_responses > 0 else 0

        # Update attempt with final results
        attempt.score = final_score
        attempt.status = 'completed'
        attempt.end_time = timezone.now()
        attempt.time_taken = (attempt.end_time - attempt.start_time).total_seconds()
        attempt.save()

        # Update user competency
        user_competency, created = UserCompetency.objects.get_or_create(
            user=attempt.user,
            competency=attempt.competency,
            defaults={
                'score': final_score,
                'best_score': final_score,
                'attempts_count': 1
            }
        )

        if not created:
            # Update existing competency record
            user_competency.attempts_count += 1
            # Weighted average: recent attempts have more weight
            user_competency.score = (user_competency.score * 0.6) + (final_score * 0.4)
            # Update best score if this attempt is better
            if final_score > user_competency.best_score:
                user_competency.best_score = final_score
            user_competency.save()

        # Add completion message
        passing_score = attempt.metadata.get('passing_score', 70)
        if final_score >= passing_score:
            messages.success(request, f"🎉 Congratulations! You scored {final_score:.1f}% and passed!")
        else:
            messages.info(request, f"You scored {final_score:.1f}%. Keep practicing to improve!")

    except Exception as e:
        # Even if there's an error, mark attempt as completed to avoid hanging
        attempt.status = 'completed'
        attempt.save()
        messages.warning(request, "Quiz completed but there was an issue calculating results.")

    return redirect('quiz_results', attempt_id=attempt.id)

@login_required 
def take_quiz(request, attempt_id):
    """Display current quiz question"""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)

    # If quiz is not in progress, redirect to results
    if attempt.status != 'in_progress':
        return redirect('quiz_results', attempt_id=attempt.id)

    # Check time remaining
    time_limit = attempt.metadata.get('time_limit', 10) * 60  # Convert to seconds
    time_elapsed = (timezone.now() - attempt.start_time).total_seconds()
    time_remaining = max(0, time_limit - time_elapsed)

    # If time expired, complete the quiz
    if time_remaining <= 0:
        attempt.status = 'timed_out'
        attempt.save()
        messages.warning(request, "⏰ Time's up! Quiz has been submitted automatically.")
        return redirect('quiz_results', attempt_id=attempt.id)

    # CRITICAL FIX: Get question IDs from metadata instead of calling get_quiz_questions
    question_ids = attempt.metadata.get('question_ids', [])
    if not question_ids:
        # Fallback if something went wrong (shouldn't happen in normal flow)
        question_objs = get_quiz_questions(attempt)
        question_ids = [q.id for q in question_objs]
        attempt.metadata['question_ids'] = question_ids
        attempt.save(update_fields=['metadata'])
    
    total_questions = len(question_ids)
    
    # Check if we've reached the end
    if attempt.current_question >= total_questions:
        return complete_quiz(request, attempt)

    # Get current question by ID (FIXED)
    current_question_id = question_ids[attempt.current_question]
    current_question = get_object_or_404(Question, id=current_question_id)
    
    # Get answers for current question
    answers = list(current_question.answers.all().order_by('order'))
    
    # Shuffle answers if enabled
    if attempt.metadata.get('shuffle_answers', True):
        random.shuffle(answers)

    context = {
        'attempt': attempt,
        'question': current_question,
        'answers': answers,
        'time_remaining': int(time_remaining),
        'progress': {
            'current': attempt.current_question + 1,
            'total': total_questions,
            'percentage': ((attempt.current_question + 1) / total_questions) * 100
        }
    }
    
    return render(request, 'user/quiz.html', context)

@login_required
def quiz_results(request, attempt_id):
    """Display comprehensive quiz results"""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, user=request.user)

    # Get all responses with related data
    responses = QuizResponse.objects.filter(
        quiz_attempt=attempt
    ).select_related('question', 'answer').order_by('question__id')

    # Calculate statistics
    total_questions = responses.count()
    correct_answers = responses.filter(is_correct=True).count()
    incorrect_answers = total_questions - correct_answers
    
    # GET THE PASSING SCORE FROM ATTEMPT METADATA
    passing_score = attempt.metadata.get('passing_score', 70)  # Default to 70%
    
    # Performance by difficulty
    difficulty_stats = {}
    for difficulty in ['easy', 'medium', 'hard']:
        diff_responses = responses.filter(question__difficulty=difficulty)
        diff_total = diff_responses.count()
        diff_correct = diff_responses.filter(is_correct=True).count()
        
        if diff_total > 0:
            difficulty_stats[difficulty] = {
                'total': diff_total,
                'correct': diff_correct,
                'percentage': round((diff_correct / diff_total) * 100, 1)
            }

    # Get user's overall competency data
    user_competency = UserCompetency.objects.filter(
        user=request.user,
        competency=attempt.competency
    ).first()

    # Quiz settings for display
    settings = attempt.competency.settings if hasattr(attempt.competency, 'settings') else None

    context = {
        'attempt': attempt,
        'responses': responses,
        'stats': {
            'total': total_questions,
            'correct': correct_answers,
            'incorrect': incorrect_answers,
            'percentage': round((correct_answers / total_questions) * 100, 1) if total_questions > 0 else 0,
            'passing_score': passing_score,
            'passed': attempt.score >= passing_score if attempt.score else False
        },
        'difficulty_stats': difficulty_stats,
        'user_competency': user_competency,
        'show_correct_answers': settings.show_correct_answers if settings else True,
        'time_taken_formatted': format_duration(attempt.time_taken) if attempt.time_taken else "N/A",
        'passing_score': passing_score
    }
    
    return render(request, 'user/quiz_results.html', context)

def get_quiz_questions(attempt):
    """Get questions for quiz based on adaptive difficulty and user competency"""
    user_comp = UserCompetency.objects.filter(
        user=attempt.user,
        competency=attempt.competency
    ).first()

    # Determine difficulty distribution based on user's current competency level
    if user_comp and user_comp.score >= 80:
        # Expert level: mostly hard questions
        distribution = {'easy': 0.1, 'medium': 0.3, 'hard': 0.6}
    elif user_comp and user_comp.score >= 60:
        # Advanced level: balanced with more medium/hard
        distribution = {'easy': 0.2, 'medium': 0.4, 'hard': 0.4}
    elif user_comp and user_comp.score >= 40:
        # Intermediate level: mostly medium questions
        distribution = {'easy': 0.3, 'medium': 0.5, 'hard': 0.2}
    else:
        # Beginner level: mostly easy questions
        distribution = {'easy': 0.6, 'medium': 0.3, 'hard': 0.1}

    questions = []
    total_needed = attempt.metadata.get('question_count', 5)

    # Get questions by difficulty level - FIXED: Convert to list immediately
    for difficulty, ratio in distribution.items():
        count = max(1, round(total_needed * ratio))
        
        # CRITICAL FIX: Convert sliced QuerySet to list immediately
        difficulty_questions = list(Question.objects.filter(
            competency=attempt.competency,
            difficulty=difficulty,
            is_active=True
        ).order_by('?')[:count])
        
        questions.extend(difficulty_questions)

    # If we don't have enough questions, fill with any available questions
    if len(questions) < total_needed:
        existing_ids = [q.id for q in questions]
        additional_needed = total_needed - len(questions)
        
        # CRITICAL FIX: Convert sliced QuerySet to list immediately
        additional_questions = list(Question.objects.filter(
            competency=attempt.competency,
            is_active=True
        ).exclude(id__in=existing_ids).order_by('?')[:additional_needed])
        
        questions.extend(additional_questions)

    # Shuffle questions if enabled
    if attempt.metadata.get('shuffle_questions', True):
        random.shuffle(questions)

    return questions[:total_needed]  # Ensure we don't exceed the required count

# -------------------
# Admin Views
# -------------------

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_users = CustomUser.objects.count()
    total_assessments = Assessment.objects.count()
    total_hackathons = Hackathon.objects.count()
    recent_users = CustomUser.objects.order_by('-date_joined')[:5]

    # Quiz statistics
    total_quiz_attempts = QuizAttempt.objects.count()
    completed_quizzes = QuizAttempt.objects.filter(status='completed').count()
    avg_quiz_score = QuizAttempt.objects.filter(status='completed').aggregate(
        avg_score=Avg('score')
    )['avg_score'] or 0

    context = {
        'total_users': total_users,
        'total_assessments': total_assessments,
        'total_hackathons': total_hackathons,
        'recent_users': recent_users,
        'total_quiz_attempts': total_quiz_attempts,
        'completed_quizzes': completed_quizzes,
        'avg_quiz_score': round(avg_quiz_score, 1),
    }
    return render(request, 'admin/dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def admin_users(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    query = request.GET.get('q')

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(profile__skills__icontains=query)
        )

    context = {
        'users': users,
        'query': query,
    }
    return render(request, 'admin/users.html', context)

@login_required
@user_passes_test(is_admin)
def admin_reports(request):
    user_progress = ProgressNode.objects.values('step').annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(is_completed=True))
    )

    assessment_stats = Assessment.objects.aggregate(
        avg_score=Avg('score'),
        total=Count('id')
    )

    learning_path_stats = LearningPath.objects.values('status').annotate(
        count=Count('id')
    )

    hackathon_stats = Hackathon.objects.annotate(
        total_participants=Count('submissions', distinct=True) +
        Count('submissions__team_members', distinct=True),
        total_submissions=Count('submissions')
    ).values('name', 'total_participants', 'total_submissions')

    # Quiz statistics
    quiz_stats = {
        'total_attempts': QuizAttempt.objects.count(),
        'completed_attempts': QuizAttempt.objects.filter(status='completed').count(),
        'average_score': QuizAttempt.objects.filter(status='completed').aggregate(
            avg=Avg('score')
        )['avg'] or 0,
        'competency_performance': UserCompetency.objects.values('competency__name').annotate(
            avg_score=Avg('score'),
            total_users=Count('user', distinct=True)
        ).order_by('-avg_score')
    }

    context = {
        'user_progress': user_progress,
        'assessment_stats': assessment_stats,
        'learning_path_stats': learning_path_stats,
        'hackathon_stats': hackathon_stats,
        'quiz_stats': quiz_stats,
    }
    return render(request, 'admin/reports.html', context)

# ============================
# UNIVERSAL CODE EXECUTOR
# ============================

import json
import subprocess
import os
import ast
import time
import re
import traceback
import platform
import shutil
from typing import Dict, List, Any, Union, Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

class UniversalCodeExecutor:
    """Universal code execution service that handles ANY problem type automatically"""
    
    def __init__(self):
        self.timeout = 10  # seconds
        self.memory_limit = 256 * 1024 * 1024  # 256MB
        self.max_output_size = 10000  # Maximum output size in characters
    
    def execute_submission(self, code: str, language: str, problem, test_cases: List[Dict]) -> Dict:
        """Execute code against all test cases using problem's function signature"""
        logger.info(f"🔍 Executing {language} code for problem {problem.id}")
        
        if not test_cases:
            logger.warning(f"No test cases found for problem {problem.id}")
            return {
                'status': 'wrong_answer',
                'test_results': [],
                'execution_time': 0,
                'memory_used': 0,
                'tests_passed': 0,
                'total_tests': 0,
                'error': 'No test cases defined for this problem'
            }
        
        results = []
        total_time = 0
        max_memory = 0
        
        try:
            for i, test_case in enumerate(test_cases):
                logger.info(f"🔍 Running test case {i+1}/{len(test_cases)}")
                
                # Validate test case structure
                if not isinstance(test_case, dict) or 'input' not in test_case or 'expected_output' not in test_case:
                    logger.error(f"Invalid test case structure at index {i}: {test_case}")
                    result = {
                        'passed': False,
                        'error': f'Invalid test case structure at index {i}',
                        'input': str(test_case.get('input', 'N/A')),
                        'expected': str(test_case.get('expected_output', 'N/A')),
                        'actual': 'N/A',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                else:
                    result = self._run_single_test(code, language, problem, test_case)
                
                results.append(result)
                logger.info(f"🔍 Test case {i+1} result: {'PASSED' if result['passed'] else 'FAILED'}")
                
                if not result['passed']:
                    logger.info(f"Stopping execution after first failure at test case {i+1}")
                    break
                    
                total_time += result.get('execution_time', 0)
                max_memory = max(max_memory, result.get('memory_used', 0))
            
            # Determine overall status
            all_passed = all(r['passed'] for r in results)
            status = 'accepted' if all_passed else 'wrong_answer'
            
            logger.info(f"🔍 Final status: {status} ({sum(1 for r in results if r['passed'])}/{len(results)} tests passed)")
            
            return {
                'status': status,
                'test_results': results,
                'execution_time': total_time,
                'memory_used': max_memory,
                'tests_passed': sum(1 for r in results if r['passed']),
                'total_tests': len(test_cases)
            }
            
        except Exception as e:
            logger.error(f"❌ Executor error: {e}")
            logger.error(traceback.format_exc())
            
            return {
                'status': 'runtime_error',
                'test_results': results if results else [{
                    'passed': False,
                    'error': str(e),
                    'input': 'N/A',
                    'expected': 'N/A',
                    'actual': 'N/A',
                    'execution_time': 0,
                    'memory_used': 0
                }],
                'execution_time': total_time,
                'memory_used': max_memory,
                'tests_passed': 0,
                'total_tests': len(test_cases) if test_cases else 0,
                'error': str(e)
            }
    
    def _run_single_test(self, code: str, language: str, problem, test_case: Dict) -> Dict:
        """Run code against a single test case using universal parsing"""
        try:
            if language == 'python':
                return self._run_python_universal(code, problem, test_case)
            elif language == 'javascript':
                return self._run_javascript_universal(code, problem, test_case)
            elif language == 'java':
                return self._run_java_universal(code, problem, test_case)
            else:
                return {
                    'passed': False, 
                    'error': f'Unsupported language: {language}',
                    'input': test_case.get('input', 'N/A'),
                    'expected': test_case.get('expected_output', 'N/A'),
                    'actual': 'N/A',
                    'execution_time': 0,
                    'memory_used': 0
                }
        except Exception as e:
            logger.error(f"Error in _run_single_test: {e}")
            return {
                'passed': False,
                'error': str(e),
                'input': test_case.get('input', 'N/A'),
                'expected': test_case.get('expected_output', 'N/A'),
                'actual': 'N/A',
                'execution_time': 0,
                'memory_used': 0
            }
    
    def _get_python_command(self):
        """Get the correct Python command for the current platform"""
        python_commands = []
        
        if platform.system() == 'Windows':
            python_commands = ['python', 'py', 'python3']
        else:
            python_commands = ['python3', 'python']
        
        for cmd in python_commands:
            if shutil.which(cmd):
                logger.info(f"Found Python command: {cmd}")
                return cmd
        
        logger.error("No Python command found in PATH")
        return None

    def _get_node_command(self):
        """Get the correct Node.js command for the current platform"""
        node_commands = ['node', 'nodejs']
        
        for cmd in node_commands:
            if shutil.which(cmd):
                logger.info(f"Found Node.js command: {cmd}")
                return cmd
        
        logger.error("No Node.js command found in PATH")
        return None
    
    def _parse_universal_input(self, input_str: str, function_params: List[Dict]) -> List[Any]:
        """
        Universal input parser that handles ANY problem type based on function signature
        
        Examples:
        - Single string: "hello" → ["hello"]
        - Single number: "42" → [42]
        - Two Sum format: "[2,7,11,15]\n9" → [[2,7,11,15], 9]
        - Valid Parentheses: "()" → ["()"]
        - Multiple arrays: "[1,3]\n[2]" → [[1,3], [2]]
        """
        try:
            if not input_str:
                return []
            
            # Remove outer quotes if present
            if input_str.startswith('"') and input_str.endswith('"'):
                input_str = input_str[1:-1]
            
            # Handle multi-line input (common format)
            if '\n' in input_str:
                lines = input_str.strip().split('\n')
                args = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]
                    
                    # Parse each line
                    if line.startswith('[') and line.endswith(']'):
                        try:
                            args.append(ast.literal_eval(line))
                        except:
                            args.append(line)
                    elif line.replace('-', '').replace('.', '').isdigit():
                        args.append(float(line) if '.' in line else int(line))
                    else:
                        args.append(line)
                
                return args
            
            # Single line input
            param_count = len(function_params) if function_params else 1
            
            if param_count == 1:
                # Single parameter function
                if function_params:
                    param_type = function_params[0].get('type', 'str')
                    return [self._convert_to_type(input_str, param_type)]
                else:
                    # No function params defined, try to infer
                    return [self._smart_convert(input_str)]
            
            elif param_count >= 2:
                # Multiple parameter function - try to parse as JSON array
                if input_str.startswith('[') and input_str.endswith(']'):
                    try:
                        parsed = json.loads(input_str)
                        if isinstance(parsed, list):
                            return parsed[:param_count]  # Take only needed parameters
                    except:
                        # Fallback to literal eval
                        try:
                            return [ast.literal_eval(input_str)]
                        except:
                            return [input_str]
                
                # Try comma-separated values
                if ', ' in input_str:
                    parts = [part.strip() for part in input_str.split(', ')]
                    return [self._smart_convert(part) for part in parts[:param_count]]
            
            # Fallback: single argument
            return [self._smart_convert(input_str)]
            
        except Exception as e:
            logger.error(f"Error parsing input '{input_str}': {e}")
            # Last resort: return as string
            return [input_str]
    
    def _smart_convert(self, value: str) -> Any:
        """Smart conversion that tries to infer the best type"""
        try:
            if not isinstance(value, str):
                return value
                
            # Try array/list first
            if value.startswith('[') and value.endswith(']'):
                return ast.literal_eval(value)
            
            # Try number
            if value.replace('-', '').replace('.', '').isdigit():
                return float(value) if '.' in value else int(value)
            
            # Try boolean
            if value.lower() in ['true', 'false']:
                return value.lower() == 'true'
            
            # Return as string
            return value
        except Exception as e:
            logger.error(f"Error in smart_convert for value '{value}': {e}")
            return value
    
    def _convert_to_type(self, value: str, target_type: str) -> Any:
        """Convert string value to target type"""
        try:
            if target_type.lower() in ['str', 'string']:
                return value
            elif target_type.lower() in ['int', 'integer']:
                return int(value)
            elif target_type.lower() in ['float', 'double']:
                return float(value)
            elif target_type.lower() in ['bool', 'boolean']:
                return value.lower() in ['true', '1', 'yes']
            elif 'list' in target_type.lower() or 'array' in target_type.lower():
                return ast.literal_eval(value)
            else:
                return ast.literal_eval(value)
        except Exception as e:
            logger.error(f"Error converting '{value}' to type '{target_type}': {e}")
            return value
    
    def _run_python_universal(self, code: str, problem, test_case: Dict) -> Dict:
        """Execute Python code with universal input handling - Mac and Windows compatible"""
        temp_file = None
        try:
            test_input = test_case['input']
            expected_output = test_case['expected_output']
            function_params = getattr(problem, 'function_params', None) or []
            function_name = getattr(problem, 'function_name', None) or 'solution'
            
            # Get platform-appropriate Python command
            python_cmd = self._get_python_command()
            if not python_cmd:
                return {
                    'passed': False,
                    'error': 'Python interpreter not found. Please install Python and add it to PATH.',
                    'input': test_case['input'],
                    'expected': test_case['expected_output'],
                    'actual': 'No Python found',
                    'execution_time': 0,
                    'memory_used': 0
                }
            
            # Parse input based on function signature
            parsed_args = self._parse_universal_input(test_input, function_params)
            
            # ✅ FIXED: Improved wrapper code with safer resource handling
            wrapper_code = "import sys\n"
            wrapper_code += "import json\n"
            wrapper_code += "import time\n"
            wrapper_code += "import ast\n\n"
            
            wrapper_code += "# Try to import and use resource, but don't fail if it's not available\n"
            wrapper_code += "def safe_resource_usage():\n"
            wrapper_code += "    try:\n"
            wrapper_code += "        import resource\n"
            wrapper_code += "        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024\n"
            wrapper_code += "    except (ImportError, AttributeError):\n"
            wrapper_code += "        return 0\n\n"
            
            wrapper_code += "def safe_memory_limit():\n"
            wrapper_code += "    try:\n"
            wrapper_code += "        import resource\n"
            wrapper_code += "        # Get current limits\n"
            wrapper_code += "        soft, hard = resource.getrlimit(resource.RLIMIT_AS)\n"
            wrapper_code += f"        target_limit = {self.memory_limit}\n"
            wrapper_code += "        # Only set limit if it's smaller than current soft limit\n"
            wrapper_code += "        if soft == resource.RLIM_INFINITY or target_limit < soft:\n"
            wrapper_code += "            # Make sure target doesn't exceed hard limit\n"
            wrapper_code += "            if hard != resource.RLIM_INFINITY and target_limit > hard:\n"
            wrapper_code += "                target_limit = hard\n"
            wrapper_code += "            resource.setrlimit(resource.RLIMIT_AS, (target_limit, hard))\n"
            wrapper_code += "    except (ImportError, AttributeError, ValueError, OSError):\n"
            wrapper_code += "        # Silently ignore any resource limit errors\n"
            wrapper_code += "        pass\n\n"
            
            wrapper_code += "# Set memory limit if possible\n"
            wrapper_code += "safe_memory_limit()\n\n"
            
            wrapper_code += f"# Parsed arguments\nargs = {repr(parsed_args)}\n\n"
            
            wrapper_code += f"# User's code\n{code}\n\n"
            
            wrapper_code += "# Execute user's function\n"
            wrapper_code += "try:\n"
            wrapper_code += "    start_time = time.time()\n\n"
            
            wrapper_code += "    # Call function with correct number of arguments\n"
            wrapper_code += "    if len(args) == 0:\n"
            wrapper_code += f"        result = {function_name}()\n"
            wrapper_code += "    elif len(args) == 1:\n"
            wrapper_code += f"        result = {function_name}(args[0])\n"
            wrapper_code += "    elif len(args) == 2:\n"
            wrapper_code += f"        result = {function_name}(args[0], args[1])\n"
            wrapper_code += "    elif len(args) == 3:\n"
            wrapper_code += f"        result = {function_name}(args[0], args[1], args[2])\n"
            wrapper_code += "    else:\n"
            wrapper_code += f"        result = {function_name}(*args)\n\n"
            
            wrapper_code += "    end_time = time.time()\n"
            wrapper_code += "    execution_time = (end_time - start_time) * 1000\n\n"
            
            wrapper_code += "    # Get memory usage safely\n"
            wrapper_code += "    memory_used = safe_resource_usage()\n\n"
            
            wrapper_code += "    # Output results\n"
            wrapper_code += "    output = {\n"
            wrapper_code += "        'result': result,\n"
            wrapper_code += "        'execution_time': execution_time,\n"
            wrapper_code += "        'memory_used': memory_used\n"
            wrapper_code += "    }\n"
            wrapper_code += "    print(json.dumps(output, default=str))\n\n"
            
            wrapper_code += "except Exception as e:\n"
            wrapper_code += "    error_output = {\n"
            wrapper_code += "        'error': str(e),\n"
            wrapper_code += "        'error_type': type(e).__name__\n"
            wrapper_code += "    }\n"
            wrapper_code += "    print(json.dumps(error_output))\n"
            
            # Execute in isolated environment
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(wrapper_code)
                temp_file = f.name
            
            try:
                # Better subprocess execution for both platforms
                is_windows = platform.system() == 'Windows'
                
                result = subprocess.run(
                    [python_cmd, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=is_windows
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr.strip() if result.stderr else 'Python execution failed'
                    return {
                        'passed': False,
                        'error': f'Execution failed: {error_msg}',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': result.stdout.strip() if result.stdout else 'No output',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                # Parse output
                if not result.stdout.strip():
                    return {
                        'passed': False,
                        'error': 'No output from code execution',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': 'No output',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                try:
                    output_data = json.loads(result.stdout.strip())
                except json.JSONDecodeError as e:
                    return {
                        'passed': False,
                        'error': f'Invalid JSON output: {e}',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': result.stdout.strip()[:self.max_output_size],
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                if 'error' in output_data:
                    return {
                        'passed': False,
                        'error': output_data['error'],
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': 'Error during execution',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                # Universal result comparison
                user_result = output_data['result']
                expected_result = self._parse_expected_output(expected_output)
                
                passed = self._compare_results(user_result, expected_result)
                
                return {
                    'passed': passed,
                    'input': test_case['input'],
                    'expected': test_case['expected_output'],
                    'actual': str(user_result),
                    'execution_time': output_data.get('execution_time', 0),
                    'memory_used': output_data.get('memory_used', 0)
                }
                
            finally:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                
        except subprocess.TimeoutExpired:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return {
                'passed': False, 
                'error': 'Time Limit Exceeded',
                'input': test_case.get('input', 'N/A'),
                'expected': test_case.get('expected_output', 'N/A'),
                'actual': 'Timeout',
                'execution_time': self.timeout * 1000,
                'memory_used': 0
            }
        except Exception as e:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return {
                'passed': False, 
                'error': str(e),
                'input': test_case.get('input', 'N/A'),
                'expected': test_case.get('expected_output', 'N/A'),
                'actual': 'Error',
                'execution_time': 0,
                'memory_used': 0
            }




    
    def _run_javascript_universal(self, code: str, problem, test_case: Dict) -> Dict:
        """Execute JavaScript code with universal input handling - Windows compatible"""
        temp_file = None
        try:
            test_input = test_case['input']
            expected_output = test_case['expected_output']
            function_params = getattr(problem, 'function_params', None) or []
            function_name = getattr(problem, 'function_name', None) or 'solution'
            
            # ✅ FIXED: Get platform-appropriate Node.js command
            node_cmd = self._get_node_command()
            if not node_cmd:
                return {
                    'passed': False,
                    'error': 'Node.js not found. Please install Node.js and add it to PATH.',
                    'input': test_case['input'],
                    'expected': test_case['expected_output'],
                    'actual': 'No Node.js found',
                    'execution_time': 0,
                    'memory_used': 0
                }
            
            # Parse input based on function signature
            parsed_args = self._parse_universal_input(test_input, function_params)
            
            wrapper_code = f"""
const args = {json.dumps(parsed_args)};

{code}

try {{
    const startTime = Date.now();
    let result;
    
    // Call function with correct number of arguments
    if (args.length === 0) {{
        result = {function_name}();
    }} else if (args.length === 1) {{
        result = {function_name}(args[0]);
    }} else if (args.length === 2) {{
        result = {function_name}(args[0], args[1]);
    }} else if (args.length === 3) {{
        result = {function_name}(args[0], args[1], args[2]);
    }} else {{
        result = {function_name}(...args);
    }}
    
    const endTime = Date.now();
    const executionTime = endTime - startTime;
    
    console.log(JSON.stringify({{
        result: result,
        execution_time: executionTime
    }}));
}} catch (error) {{
    console.log(JSON.stringify({{
        'error': error.message,
        'error_type': error.name
    }}));
}}
"""
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(wrapper_code)
                temp_file = f.name
            
            try:
                # ✅ FIXED: Use detected Node command and shell for Windows
                result = subprocess.run(
                    [node_cmd, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=platform.system() == 'Windows'
                )
                
                if result.returncode != 0:
                    return {
                        'passed': False, 
                        'error': result.stderr or 'JavaScript execution failed',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': result.stdout.strip() if result.stdout else 'No output',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                if not result.stdout.strip():
                    return {
                        'passed': False,
                        'error': 'No output from code execution',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': 'No output',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                try:
                    output_data = json.loads(result.stdout.strip())
                except json.JSONDecodeError as e:
                    return {
                        'passed': False, 
                        'error': f'Invalid JSON output: {e}',
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': result.stdout.strip()[:self.max_output_size],
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                if 'error' in output_data:
                    return {
                        'passed': False, 
                        'error': output_data['error'],
                        'input': test_case['input'],
                        'expected': test_case['expected_output'],
                        'actual': 'Error during execution',
                        'execution_time': 0,
                        'memory_used': 0
                    }
                
                user_result = output_data['result']
                expected_result = self._parse_expected_output(expected_output)
                
                return {
                    'passed': self._compare_results(user_result, expected_result),
                    'input': test_case['input'],
                    'expected': test_case['expected_output'],
                    'actual': str(user_result),
                    'execution_time': output_data.get('execution_time', 0),
                    'memory_used': 0  # JavaScript doesn't easily provide memory usage
                }
                
            finally:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                
        except subprocess.TimeoutExpired:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return {
                'passed': False, 
                'error': 'Time Limit Exceeded',
                'input': test_case.get('input', 'N/A'),
                'expected': test_case.get('expected_output', 'N/A'),
                'actual': 'Timeout',
                'execution_time': self.timeout * 1000,
                'memory_used': 0
            }
        except Exception as e:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return {
                'passed': False, 
                'error': str(e),
                'input': test_case.get('input', 'N/A'),
                'expected': test_case.get('expected_output', 'N/A'),
                'actual': 'Error',
                'execution_time': 0,
                'memory_used': 0
            }
    
    def _run_java_universal(self, code: str, problem, test_case: Dict) -> Dict:
        """Execute Java code with universal input handling - Basic implementation"""
        # For now, return a message that Java support is limited
        return {
            'passed': False, 
            'error': 'Java execution is not fully implemented in this version. Use Python or JavaScript.',
            'input': test_case.get('input', 'N/A'),
            'expected': test_case.get('expected_output', 'N/A'),
            'actual': 'Not executed',
            'execution_time': 0,
            'memory_used': 0
        }
    
    def _parse_expected_output(self, expected_str: str) -> Any:
        """Parse expected output string to proper Python type"""
        try:
            if not expected_str:
                return ""
                
            # Handle string literals
            if expected_str.startswith('"') and expected_str.endswith('"'):
                return expected_str[1:-1]
            
            # Handle boolean literals
            if expected_str.lower() == 'true':
                return True
            elif expected_str.lower() == 'false':
                return False
            
            # Try to parse as Python literal
            return ast.literal_eval(expected_str)
        except Exception as e:
            logger.error(f"Error parsing expected output '{expected_str}': {e}")
            return expected_str
    
    def _compare_results(self, actual: Any, expected: Any) -> bool:
        """Universal result comparison that handles different data types"""
        try:
            # Direct comparison
            if actual == expected:
                return True
            
            # Handle None/null cases
            if actual is None and expected is None:
                return True
            if (actual is None) != (expected is None):
                return False
            
            # Handle string vs boolean comparison
            if isinstance(actual, bool) and isinstance(expected, str):
                return str(actual).lower() == expected.lower()
            if isinstance(expected, bool) and isinstance(actual, str):
                return str(expected).lower() == actual.lower()
            
            # Handle list comparison (order matters)
            if isinstance(actual, list) and isinstance(expected, list):
                if len(actual) != len(expected):
                    return False
                return all(self._compare_results(a, e) for a, e in zip(actual, expected))
            
            # Handle numeric comparison with tolerance
            if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                return abs(float(actual) - float(expected)) < 1e-9
            
            # String comparison (case-sensitive)
            actual_str = str(actual).strip()
            expected_str = str(expected).strip()
            return actual_str == expected_str
            
        except Exception as e:
            logger.error(f"Error comparing results: actual={actual}, expected={expected}, error={e}")
            return False

# -------------------
# CODING PROBLEMS - FIXED VERSION
# -------------------
# ============================
# ENHANCED TEMPLATE GENERATOR
# ============================

class UniversalTemplateGenerator:
    """Generate starter code templates that work with any problem type"""
    
    @staticmethod
    def generate_templates(problem: CodingProblem) -> dict:
        """Generate language-specific starter templates WITHOUT SOLUTIONS"""
        
        # Get function parameters safely
        params = getattr(problem, 'function_params', None) or []
        param_names = [p.get('name', f'param{i}') for i, p in enumerate(params)]
        function_name = getattr(problem, 'function_name', None) or 'solution'
        return_type = getattr(problem, 'return_type', None) or 'Any'
        
        # Python template
        python_params = ', '.join(param_names) if param_names else 'input_data'
        python_template = f"""def {function_name}({python_params}):
    \"\"\"
    {problem.title}
    
    Args:
        {chr(10).join(f"        {p.get('name', f'param{i}')}: {p.get('type', 'Any')}" for i, p in enumerate(params)) if params else '        input_data: Input for the problem'}
    
    Returns:
        {return_type}: Your solution result
    \"\"\"
    # Write your solution here
    pass"""
        
        # JavaScript template
        js_params = ', '.join(param_names) if param_names else 'inputData'
        javascript_template = f"""function {function_name}({js_params}) {{
    /**
     * {problem.title}
     * 
     * {chr(10).join(f"     * @param {{{p.get('type', 'any')}}} {p.get('name', f'param{i}')}" for i, p in enumerate(params)) if params else '     * @param {any} inputData'}
     * @return {{{return_type}}} Your solution result
     */
    // Write your solution here
}}"""
        
        # Java template
        java_params = ', '.join(f"{p.get('type', 'Object')} {p.get('name', f'param{i}')}" for i, p in enumerate(params)) if params else 'Object inputData'
        java_template = f"""public class Solution {{
    /**
     * {problem.title}
     * 
     * {chr(10).join(f"     * @param {p.get('name', f'param{i}')} {p.get('type', 'Object')}" for i, p in enumerate(params)) if params else '     * @param inputData Input for the problem'}
     * @return {return_type} Your solution result
     */
    public {return_type} {function_name}({java_params}) {{
        // Write your solution here
        return null;
    }}
}}"""
        
        return {
            'python': python_template,
            'javascript': javascript_template,
            'java': java_template
        }

import json
import subprocess

import os
import ast
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

# ============================
# DJANGO VIEWS INTEGRATION
# ============================

def problem_list(request):
    """List all coding problems"""
    try:
        problems = CodingProblem.objects.filter(is_active=True)
        
        # Filter by difficulty
        difficulty = request.GET.get('difficulty')
        if difficulty in ['easy', 'medium', 'hard']:
            problems = problems.filter(difficulty=difficulty)
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            problems = problems.filter(title__icontains=search)
        
        accepted_problem_ids = set()
        if request.user.is_authenticated:
            accepted_problem_ids = set(
                CodeSubmission.objects.filter(
                    user=request.user,
                    status='accepted'
                ).values_list('problem_id', flat=True).distinct()
            )
        
        context = {
            'problems': problems,
            'current_difficulty': difficulty,
            'search_query': search,
            'accepted_problem_ids': accepted_problem_ids,  # Pass accepted problems set
        }
        return render(request, 'coding/problem_list.html', context)
    except Exception as e:
        logger.error(f"Error in problem_list: {e}")
        return render(request, 'coding/problem_list.html', {'problems': [], 'error': str(e)})


def problem_detail(request, problem_id):
    """Individual problem page with universal code editor"""
    try:
        problem = get_object_or_404(CodingProblem, id=problem_id, is_active=True)
        
        # Get user's previous submissions
        user_submissions = []
        if request.user.is_authenticated:
            user_submissions = CodeSubmission.objects.filter(
                user=request.user, 
                problem=problem
            ).order_by('-submitted_at')[:10]
        
        # Generate universal templates
        template_generator = UniversalTemplateGenerator()
        code_templates = template_generator.generate_templates(problem)
        
        # Split tags safely
        problem_tags = []
        if hasattr(problem, 'tags') and problem.tags:
            problem_tags = [tag.strip() for tag in problem.tags.split(',') if tag.strip()]
        
        context = {
            'problem': problem,
            'problem_tags': problem_tags,
            'user_submissions': user_submissions,
            'code_templates': json.dumps(code_templates),
        }
        return render(request, 'coding/problem_detail.html', context)
    except Exception as e:
        logger.error(f"Error in problem_detail: {e}")
        return render(request, 'coding/error.html', {'error': str(e)})


@csrf_exempt
@require_POST
@login_required
@never_cache
def submit_code(request):
    """Universal code submission handler with comprehensive error handling"""
    submission = None
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)
        
        problem_id = data.get('problem_id')
        code = data.get('code')
        language = data.get('language')
        
        # Validate required fields
        if not all([problem_id, code, language]):
            missing_fields = []
            if not problem_id: missing_fields.append('problem_id')
            if not code: missing_fields.append('code')
            if not language: missing_fields.append('language')
            
            return JsonResponse({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)
        
        # Validate language
        if language not in ['python', 'javascript', 'java']:
            return JsonResponse({
                'error': f'Unsupported language: {language}'
            }, status=400)
        
        # Get problem
        try:
            problem = get_object_or_404(CodingProblem, id=problem_id, is_active=True)
        except Exception as e:
            logger.error(f"Problem not found: {problem_id}")
            return JsonResponse({'error': 'Problem not found'}, status=404)
        
        # Create submission record
        try:
            submission = CodeSubmission.objects.create(
                user=request.user,
                problem=problem,
                code=code,
                language=language,
                status='running'
            )
            logger.info(f"Created submission {submission.id} for user {request.user.id} and problem {problem.id}")
        except Exception as e:
            logger.error(f"Error creating submission: {e}")
            return JsonResponse({'error': 'Failed to create submission record'}, status=500)
        
        # Execute code using universal executor
        try:
            executor = UniversalCodeExecutor()
            result = executor.execute_submission(code, language, problem, problem.test_cases)
            
            # Update submission with results
            submission.status = result['status']
            submission.execution_time = result.get('execution_time', 0)
            submission.memory_used = result.get('memory_used', 0)
            submission.test_results = result['test_results']
            if 'error' in result:
                submission.error_message = result['error']
            submission.save()
            
            logger.info(f"Updated submission {submission.id} with status {result['status']}")
            
        except Exception as e:
            logger.error(f"Error during code execution: {e}")
            logger.error(traceback.format_exc())
            
            # Update submission with error
            if submission:
                submission.status = 'runtime_error'
                submission.error_message = str(e)
                submission.save()
            
            return JsonResponse({
                'submission_id': submission.id if submission else None,
                'status': 'runtime_error',
                'error': str(e),
                'results': {
                    'status': 'runtime_error',
                    'test_results': [],
                    'execution_time': 0,
                    'memory_used': 0,
                    'tests_passed': 0,
                    'total_tests': 0,
                    'error': str(e)
                }
            })
        
        # ✅ FIXED: Update problem statistics without setting acceptance_percentage
        try:
            problem.total_submissions = (problem.total_submissions or 0) + 1
            if result['status'] == 'accepted':
                problem.accepted_submissions = (problem.accepted_submissions or 0) + 1
            
            # ✅ REMOVED: Don't manually set acceptance_percentage as it's a computed property
            # The acceptance_percentage property will calculate this automatically
            
            problem.save()
            logger.info(f"Updated problem {problem.id} statistics: {problem.accepted_submissions}/{problem.total_submissions}")
            
        except Exception as e:
            logger.error(f"Error updating problem statistics: {e}")
            # Don't fail the request if statistics update fails
        
        # Return successful response
        return JsonResponse({
            'submission_id': submission.id,
            'status': submission.status,
            'results': result
        })
        
    except Exception as e:
        logger.error(f"Unexpected error in submit_code: {e}")
        logger.error(traceback.format_exc())
        
        # Update submission with error if it exists
        if submission:
            try:
                submission.status = 'runtime_error'
                submission.error_message = str(e)
                submission.save()
            except:
                pass
        
        return JsonResponse({
            'error': f'Internal server error: {str(e)}',
            'submission_id': submission.id if submission else None
        }, status=500)








# Extra added
@login_required
def start_module(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    learning_path, created = LearningPath.objects.get_or_create(
        user=request.user,
        module=module,
        defaults={'status': 'in_progress', 'started_at': timezone.now()}
    )
    
    if not created:
        learning_path.status = 'in_progress'
        learning_path.started_at = timezone.now()
        learning_path.save()
    
    return redirect('module_detail', module_id=module_id)

@login_required
def continue_module(request, module_id):
    # Redirect to the first incomplete content item
    module = get_object_or_404(Module, id=module_id)
    completed_contents = ModuleCompletion.objects.filter(
        user=request.user,
        content__module=module
    ).values_list('content_id', flat=True)
    
    next_content = ModuleContent.objects.filter(
        module=module,
        is_required=True
    ).exclude(id__in=completed_contents).order_by('order').first()
    
    if next_content:
        return redirect('content_detail', content_id=next_content.id)
    return redirect('module_detail', module_id=module_id)

@login_required
def review_module(request, module_id):
    # Redirect to the module detail page for review
    return redirect('module_detail', module_id=module_id)

@login_required
def remove_from_path(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    LearningPath.objects.filter(user=request.user, module=module).delete()
    messages.success(request, f"Removed {module.name} from your learning path")
    return redirect('learning_path')



from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from .models import Module, ModuleContent, LearningPath, ModuleCompletion

@login_required
def module_list(request):
    modules = Module.objects.all()
    user_paths = LearningPath.objects.filter(user=request.user).values_list('module_id', flat=True)
    return render(request, 'user/module_list.html', {
        'modules': modules,
        'user_paths': user_paths
    })

@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    contents = module.contents.order_by('order')
    learning_path = LearningPath.objects.filter(user=request.user, module=module).first()
    
    # Calculate completion status for each content
    completed_contents = ModuleCompletion.objects.filter(
        user=request.user,
        content__module=module
    ).values_list('content_id', flat=True)
    
    return render(request, 'user/module_detail.html', {
        'module': module,
        'contents': contents,
        'learning_path': learning_path,
        'completed_contents': completed_contents
    })

import json
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import ModuleContent, QuizAttemptLearningPath

def get_next_content(current_content):
    """
    Returns the next ModuleContent object in the same module by order.
    """
    return ModuleContent.objects.filter(
        module=current_content.module,
        order__gt=current_content.order
    ).order_by('order').first()

from .models import ModuleContent, QuizAttemptLearningPath, AssignmentSubmission

@login_required
def content_detail(request, content_id):
    content = get_object_or_404(ModuleContent, id=content_id)

    completed = ModuleCompletion.objects.filter(
        user=request.user,
        content=content,
        is_completed=True,
    ).exists()

    embed_url = content.get_video_embed_url()

    quiz_questions = []
    quiz_taken = False
    user_quiz_answers = {}
    attempt = None
    user_assignment_submission = None
    # Initialize pdf_url with None or a default value
    pdf_url = None
    pdf_exists = False
    pdf_size = None

    if content.content_type == 'quiz':
        quiz_questions = content.get_quiz_questions()
        attempt = QuizAttemptLearningPath.objects.filter(user=request.user, content=content).first()
        if attempt:
            quiz_taken = True
            user_quiz_answers = {a.question_index: a.selected_answer for a in attempt.user_answers.all()}
        else:
            quiz_taken = False

    elif content.content_type == 'assignment':
        user_assignment_submission = AssignmentSubmission.objects.filter(user=request.user, assignment=content).first()

    elif content.content_type == 'pdf':
        pdf_exists = content.pdf_file_exists()
        pdf_size = content.get_pdf_file_size()
        pdf_url = request.build_absolute_uri(content.pdf_file.url) if pdf_exists else None


    context = {
        'content': content,
        'module': content.module,
        'completed': completed,
        'embed_url': embed_url,
        'quiz_questions': quiz_questions,
        'quiz_taken': quiz_taken,
        'user_quiz_answers': user_quiz_answers,
        'attempt': attempt,
        'user_assignment_submission': user_assignment_submission,
        'pdf_exists': pdf_exists,
        'pdf_size': pdf_size,
         'pdf_url': pdf_url,  # Add this
    }
    return render(request, 'user/content_detail.html', context)


import json
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import ModuleContent, QuizAttemptLearningPath

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@login_required
def submit_quiz(request, content_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    content = get_object_or_404(ModuleContent, id=content_id)
    if content.content_type != 'quiz':
        return JsonResponse({'error': 'Content is not a quiz'}, status=400)

    # Prevent multiple attempts per user per content
    if QuizAttemptLearningPath.objects.filter(user=request.user, content=content).exists():
        return JsonResponse({'error': 'Quiz already taken'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)

    user_answers = data.get('answers', {})
    questions = content.get_quiz_questions()

    correct_count = 0
    total = len(questions)

    # Create quiz attempt record first
    quiz_attempt = QuizAttemptLearningPath.objects.create(
        user=request.user,
        content=content,
        score=0,  # will update later
        total=total
    )

    for i, q in enumerate(questions):
        q_key = f'q{i}'
        correct_answer = q.get('correct_answer') or ''
        user_answer = user_answers.get(q_key) or ''

        if isinstance(correct_answer, str):
            correct_answer = correct_answer.strip()
        if isinstance(user_answer, str):
            user_answer = user_answer.strip()

        if user_answer == correct_answer and correct_answer != '':
            correct_count += 1

        # Save user's answer in QuizUserAnswer table
        QuizUserAnswer.objects.create(
            quiz_attempt=quiz_attempt,
            question_index=i,
            selected_answer=user_answer
        )

    # Update score in quiz_attempt
    quiz_attempt.score = correct_count
    quiz_attempt.save()

    return JsonResponse({'score': correct_count, 'total': total})


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import ModuleContent, AssignmentSubmission


from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from django.contrib import messages

@login_required
@require_POST
def submit_quiz_form(request, content_id):
    content = get_object_or_404(ModuleContent, id=content_id)
    if content.content_type != 'quiz':
        messages.error(request, "Content is not a quiz.")
        return redirect('content_detail', content_id=content_id)

    if QuizAttemptLearningPath.objects.filter(user=request.user, content=content).exists():
        messages.error(request, "You have already taken this quiz.")
        return redirect('content_detail', content_id=content_id)

    quiz_questions = content.get_quiz_questions()
    total = len(quiz_questions)
    correct_count = 0

    # Collect user answers: keys like q0, q1 ...
    user_answers = {}
    for i in range(total):
        ans = request.POST.get(f'q{i}', '').strip()
        user_answers[f'q{i}'] = ans

    quiz_attempt = QuizAttemptLearningPath.objects.create(
        user=request.user,
        content=content,
        score=0,
        total=total
    )

    for i, q in enumerate(quiz_questions):
        correct_answer = (q.get('correct_answer') or '').strip()
        user_answer = user_answers.get(f'q{i}', '')

        if user_answer == correct_answer and correct_answer != '':
            correct_count += 1

        QuizUserAnswer.objects.create(
            quiz_attempt=quiz_attempt,
            question_index=i,
            selected_answer=user_answer
        )

    quiz_attempt.score = correct_count
    quiz_attempt.save()

    # Mark quiz content completed
    ModuleCompletion.objects.get_or_create(
        user=request.user,
        content=content,
        defaults={'is_completed': True}
    )

    messages.success(request, f"You scored {correct_count} out of {total}.")
    return redirect('content_detail', content_id=content_id)








@login_required
def submit_assignment(request, content_id):
    assignment = get_object_or_404(ModuleContent, id=content_id, content_type='assignment')

    if AssignmentSubmission.objects.filter(user=request.user, assignment=assignment).exists():
        messages.error(request, "You have already submitted this assignment.")
        return redirect('content_detail', content_id=content_id)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('assignment_zip')
        if not uploaded_file:
            messages.error(request, "Please upload a ZIP file.")
            return redirect('content_detail', content_id=content_id)

        if not uploaded_file.name.endswith('.zip'):
            messages.error(request, "Only ZIP files are allowed.")
            return redirect('content_detail', content_id=content_id)

        AssignmentSubmission.objects.create(
            user=request.user,
            assignment=assignment,
            uploaded_file=uploaded_file
        )

        # Mark assignment content completed
        ModuleCompletion.objects.get_or_create(
            user=request.user,
            content=assignment,
            defaults={'is_completed': True}
        )

        messages.success(request, "Your assignment has been submitted successfully.")
        return redirect('content_detail', content_id=content_id)

    return redirect('content_detail', content_id=content_id)

# def content_detail(request, content_id):
#     content = get_object_or_404(ModuleContent, id=content_id)
    
#     # For video embed
#     content.embed_url = content.get_video_embed_url()
    
#     # Check PDF existence and size safely
#     pdf_exists = content.pdf_file_exists()
#     pdf_size = content.get_pdf_file_size()
    
#     # You may have logic to get 'next_content' and 'module'
#     module = content.module
#     next_content = None  # Replace with your actual logic
    
#     context = {
#         'content': content,
#         'module': module,
#         'next_content': next_content,
#         'pdf_exists': pdf_exists,
#         'pdf_size': pdf_size,
#     }
    
#     return render(request, 'user/content_detail.html', context)




# ... keep your existing learning_path_view, add_to_path, and other views ...



def get_video_embed_url(self):
    if not hasattr(self, 'video_url') or not self.video_url:
        return None
        
    try:
        if self.is_youtube_video():
            # Handle YouTube URLs
            if 'youtu.be' in self.video_url:
                # Short URL format: https://youtu.be/VIDEO_ID
                video_id = self.video_url.split('/')[-1].split('?')[0]
            elif 'embed' in self.video_url:
                # Already an embed URL
                return self.video_url.split('?')[0]
            else:
                # Standard URL formats:
                # https://www.youtube.com/watch?v=VIDEO_ID
                # https://youtube.com/watch?v=VIDEO_ID&other=params
                # https://www.youtube.com/v/VIDEO_ID
                if 'v=' in self.video_url:
                    video_id = self.video_url.split('v=')[1].split('&')[0]
                elif '/v/' in self.video_url:
                    video_id = self.video_url.split('/v/')[1].split('/')[0]
                else:
                    return None
            
            # Validate YouTube video ID (typically 11 characters)
            if len(video_id) == 11 and all(c.isalnum() or c in ['-', '_'] for c in video_id):
                return f'https://www.youtube.com/embed/{video_id}'
            return None
            
        elif self.is_vimeo_video():
            # Handle Vimeo URLs
            if 'player.vimeo.com' in self.video_url:
                # Already an embed URL
                return self.video_url.split('?')[0]
            
            # Standard URL formats:
            # https://vimeo.com/VIDEO_ID
            # https://vimeo.com/channels/whatever/VIDEO_ID
            video_id = self.video_url.split('/')[-1].split('?')[0]
            
            # Validate Vimeo video ID (numeric)
            if video_id.isdigit():
                return f'https://player.vimeo.com/video/{video_id}'
            return None
            
        return self.video_url  # Return as-is if not YouTube/Vimeo
        
    except Exception as e:
        print(f"Error processing video URL: {e}")
        return None

def is_youtube_video(self):
    if not hasattr(self, 'video_url') or not self.video_url:
        return False
    return any(
        domain in self.video_url 
        for domain in ['youtube.com', 'youtu.be']
    )

def is_vimeo_video(self):
    if not hasattr(self, 'video_url') or not self.video_url:
        return False
    return 'vimeo.com' in self.video_url



import os
from django.conf import settings

def pdf_file_exists(self):
    if self.pdf_file:
        full_path = os.path.join(settings.MEDIA_ROOT, self.pdf_file.name)
        return os.path.exists(full_path)
    return False

def get_pdf_file_size(self):
    if self.pdf_file:
        full_path = os.path.join(settings.MEDIA_ROOT, self.pdf_file.name)
        try:
            return os.path.getsize(full_path)
        except FileNotFoundError:
            return None
    return None



from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import ModuleContent, ModuleCompletion


@require_POST
@login_required
def mark_content_as_read(request, content_id):
    # Fetch content or 404
    content = get_object_or_404(ModuleContent, id=content_id)

    # Mark as completed (create or update)
    completion, created = ModuleCompletion.objects.get_or_create(
        user=request.user,
        content=content,
        defaults={'is_completed': True}
    )
    if not created and not completion.is_completed:
        completion.is_completed = True
        completion.save()

    # Update learning path progress & status if exists
    learning_path = LearningPath.objects.filter(user=request.user, module=content.module).first()
    if learning_path:
        # Calculate and update progress
        progress = learning_path.calculate_progress()
        learning_path.progress = progress

        # Handle status changes
        if progress == 100 and learning_path.status != 'completed':
            learning_path.status = 'completed'
            learning_path.completed_at = timezone.now()
            learning_path.save()
            # learning_path.award_badge_and_xp()

        elif progress > 0 and learning_path.status == 'not_started':
            learning_path.status = 'in_progress'
            if not learning_path.started_at:
                learning_path.started_at = timezone.now()
            learning_path.save()

        else:
            # Save any progress changes if needed even without status change
            learning_path.save()

    messages.success(request, f'Content "{content.title}" marked as completed.')
    return redirect('content_detail', content_id=content.id)


@login_required
@require_POST
def complete_module(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    user = request.user

    total_required = module.contents.filter(is_required=True).count()
    completed_count = ModuleCompletion.objects.filter(
        user=user,
        content__module=module,
        is_completed=True
    ).count()

    if total_required == 0:
        messages.error(request, "This module has no required contents.")
        return redirect('module_detail', module_id=module.id)

    if total_required == completed_count:
        learning_path, _ = LearningPath.objects.get_or_create(user=user, module=module)
        learning_path.status = 'completed'
        learning_path.progress = 100
        learning_path.completed_at = timezone.now()
        learning_path.save()

        # Award badge and XP
        learning_path.award_badge_and_xp()

        messages.success(request, f'Module "{module.name}" marked as completed!')
    else:
        messages.error(request, "Please complete all required contents before completing the module.")

    return redirect('module_detail', module_id=module.id)


def calculate_module_progress(user, module):
    total_req = module.contents.filter(is_required=True).count()
    if total_req == 0:
        return 0
    completed = ModuleCompletion.objects.filter(
        user=user,
        content__module=module,
        is_completed=True
    ).count()
    progress_percent = int((completed / total_req) * 100)
    return progress_percent


from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.http import HttpResponseForbidden
from django.conf import settings
from .models import Certificate, Module
from reportlab.pdfgen import canvas
from io import BytesIO
import os
from datetime import datetime


@login_required
def generate_certificate(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    learning_path = get_object_or_404(LearningPath, user=request.user, module=module)
    
    if learning_path.status != 'completed':
        return HttpResponseForbidden("Module not completed")
    
    if Certificate.objects.filter(user=request.user, module=module).exists():
        return redirect('view_certificate', module_id=module.id)
    
    # Create certificate
    certificate = Certificate.objects.create(
        user=request.user,
        module=module
    )
    
    return redirect('view_certificate', module_id=module.id)
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from math import sin, cos, pi

@login_required
def view_certificate(request, module_id):
    module = get_object_or_404(Module, id=module_id)
    certificate = get_object_or_404(Certificate, user=request.user, module=module)
    
    def draw_star(canvas, x, y, size, points, inner_ratio):
        """Helper function to draw a star shape"""
        path = canvas.beginPath()
        for i in range(points * 2):
            angle = pi * i / points - pi/2
            radius = size if i % 2 == 0 else size * inner_ratio
            if i == 0:
                path.moveTo(x + radius * cos(angle), y + radius * sin(angle))
            else:
                path.lineTo(x + radius * cos(angle), y + radius * sin(angle))
        path.close()
        canvas.drawPath(path, fill=1, stroke=0)

    if request.GET.get('format') == 'pdf':
        try:
            # Create PDF buffer
            buffer = BytesIO()
            
            # Create PDF document
            p = canvas.Canvas(buffer, pagesize=landscape(A4))
            width, height = landscape(A4)
            
            # Set white background
            p.setFillColor(colors.white)
            p.rect(0, 0, width, height, fill=True, stroke=False)
            
            # Draw blue border with margin
            border_margin = 20
            p.setStrokeColor(colors.HexColor('#002366'))
            p.setLineWidth(15)
            p.rect(border_margin, border_margin, 
                   width-2*border_margin, height-2*border_margin, 
                   fill=False, stroke=True)
            
            # Add header
            p.setFont("Helvetica-Bold", 36)
            p.setFillColor(colors.HexColor('#002366'))
            p.drawCentredString(width/2, height-100, "CERTIFICATE OF ACHIEVEMENT")
            
            p.setFont("Helvetica-Oblique", 18)
            p.setFillColor(colors.HexColor('#555555'))
            p.drawCentredString(width/2, height-140, 
                              f"This certificate is proudly presented by {getattr(settings, 'SITE_NAME', 'Our Learning Platform')}")

            # ====== Enhanced Right Side Badge Design ======
            badge_margin = 60  # Increased margin from right edge
            badge_center_x = width - badge_margin - 75  # 75 is badge radius
            badge_center_y = height/2 + 40
            badge_radius = 75
            
            # Badge outer circle (blue)
            p.setFillColor(colors.HexColor('#002366'))
            p.circle(badge_center_x, badge_center_y, badge_radius, fill=True, stroke=False)
            
            # Badge inner circle (white)
            p.setFillColor(colors.white)
            p.circle(badge_center_x, badge_center_y, badge_radius-15, fill=True, stroke=False)
            
            # Badge border (blue)
            p.setStrokeColor(colors.HexColor('#002366'))
            p.setLineWidth(3)
            p.circle(badge_center_x, badge_center_y, badge_radius-15, fill=False, stroke=True)
            
            # Badge content - Course abbreviation
            course_abbr = ''.join([word[0].upper() for word in str(module.name).split()[:3]])
            p.setFont("Helvetica-Bold", 24)
            p.setFillColor(colors.HexColor('#002366'))
            p.drawCentredString(badge_center_x, badge_center_y-8, course_abbr)
            
            # Badge content - Completion year
            p.setFont("Helvetica", 12)
            p.drawCentredString(badge_center_x, badge_center_y-30, 
                               certificate.date_issued.strftime('%Y'))
            
            # Ribbon banner with proper margin
            ribbon_width = 180  # Reduced from 200
            ribbon_y = badge_center_y + badge_radius - 15
            p.setFillColor(colors.HexColor('#1a237e'))
            p.setStrokeColor(colors.HexColor('#002366'))
            p.setLineWidth(1)
            p.roundRect(badge_center_x-ribbon_width/2, ribbon_y, 
                       ribbon_width, 30, 10, fill=1, stroke=1)
            p.setFont("Helvetica-Bold", 14)
            p.setFillColor(colors.white)
            p.drawCentredString(badge_center_x, ribbon_y+10, "EXCELLENCE")
            # ====== End of Badge Design ======
            
            # Left-aligned content with proper margin
            content_margin = 80
            
            # Recipient name
            p.setFont("Helvetica-Bold", 32)
            p.setFillColor(colors.HexColor('#002366'))
            p.drawString(content_margin, height/2-30, "This is to certify that")
            p.drawString(content_margin, height/2-80, str(certificate.user.username))
            
            # Course info
            p.setFont("Helvetica", 24)
            p.setFillColor(colors.HexColor('#333333'))
            p.drawString(content_margin, height/2-130, "has successfully completed the course")
            
            p.setFont("Helvetica-Bold", 28)
            p.setFillColor(colors.HexColor('#1a237e'))
            p.drawString(content_margin, height/2-180, str(module.name))
            
            # Date
            p.setFont("Helvetica-Oblique", 18)
            p.setFillColor(colors.HexColor('#666666'))
            p.drawString(content_margin, height/2-230, 
                       f"Awarded on {certificate.date_issued.strftime('%B %d, %Y')}")
            
            # Footer with verification info
            p.setFont("Helvetica", 12)
            p.setFillColor(colors.black)
            p.drawString(50, 50, f"Certificate ID: {certificate.certificate_id}")
            p.drawString(50, 30, f"Verify at: {request.build_absolute_uri(f'/verify-certificate/{certificate.certificate_id}/')}")
            
            # Signature line
            p.line(width-250, 80, width-50, 80)
            p.setFont("Helvetica", 12)
            p.drawString(width-250, 60, "Authorized Signature")
            
            # Save the PDF
            p.showPage()
            p.save()
            
            # Save to model if not already saved
            if not certificate.pdf_file:
                filename = f"Certificate_{certificate.certificate_id}.pdf"
                certificate.pdf_file.save(filename, ContentFile(buffer.getvalue()))
                certificate.save()
            
            # Return the PDF response
            buffer.seek(0)
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="Certificate_{certificate.certificate_id}.pdf"'
            return response
            
        except Exception as e:
            return HttpResponse(f"Error generating PDF: {str(e)}", status=500)
    
    verification_url = request.build_absolute_uri(
        f"/verify-certificate/{certificate.certificate_id}/"
    )
    
    return render(request, 'certificates/certificate_detail.html', {
        'certificate': certificate,
        'module': module,
        'user': request.user,
        'verification_url': verification_url,
        'site_name': getattr(settings, 'SITE_NAME', 'Our Learning Platform')
    })

# @login_required
def verify_certificate(request, certificate_id):
    cert = get_object_or_404(Certificate, certificate_id=certificate_id)
    return render(request, 'certificates/verify_certificate.html', {
        'certificate': cert,
        'is_valid': cert.is_verified
    })



# signals.py (to auto-generate certificates)
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ModuleCompletion, Certificate


@receiver(post_save, sender=ModuleCompletion)
def check_for_certificate(sender, instance, **kwargs):
    user = instance.user
    module = instance.content.module
    
    if module.contents.filter(is_required=True).count() == \
       ModuleCompletion.objects.filter(
           user=user,
           content__module=module,
           content__is_required=True,
           is_completed=True
       ).count():
        Certificate.objects.get_or_create(
            user=user,
            module=module,
            defaults={'certificate_id': uuid.uuid4().hex[:8].upper()}
        )


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CustomUser, UserProfile, Resume
from .forms import ProfileUpdateForm, ResumeUploadForm


@login_required
def profile_view(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    profile_form = ProfileUpdateForm(instance=request.user)
    resume_form = ResumeUploadForm()
    learning_paths = LearningPath.objects.filter(user=user).select_related('module')
    xp_earned = learning_paths.filter(status='completed').aggregate(
        total_xp=Sum('module__xp_reward')
    )['total_xp'] or 0

    # XP from coding problems (stored in profile)
    coding_xp = profile.total_xp if profile else 0
    total_xp = coding_xp + xp_earned
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
        
        elif form_type == 'resume':
            resume_form = ResumeUploadForm(request.POST, request.FILES)
            if resume_form.is_valid():
                # Delete existing resume and its file if it exists
                existing_resume = Resume.objects.filter(user=request.user).first()
                if existing_resume:
                    existing_resume.delete()  # This will trigger the file deletion via model's delete()
                
                # Create new resume
                resume = resume_form.save(commit=False)
                resume.user = request.user
                
                # Extract skills from resume file
                try:
                    extracted_text = extract_text_from_file(resume.resume_file)
                    skills = extract_skills_from_text(extracted_text)
                    resume.extracted_skills = ', '.join(skills)
                except Exception as e:
                    messages.warning(request, f'Resume uploaded but skill extraction failed: {str(e)}')
                    resume.extracted_skills = ''
                
                resume.save()
                
                # Update user profile skills
                if resume.extracted_skills:
                    profile, created = UserProfile.objects.get_or_create(user=request.user)
                    current_skills = set(profile.skills.split(',')) if profile.skills else set()
                    new_skills = {s.strip() for s in resume.extracted_skills.split(',') if s.strip()}
                    updated_skills = current_skills.union(new_skills)
                    profile.skills = ', '.join(updated_skills)
                    profile.save()
                
                messages.success(request, 'Resume uploaded and processed successfully!')
                return redirect('profile')
    
    # Get user's resume (should be only one or none)
    resume = Resume.objects.filter(user=request.user).first()

     # ---- Recommend modules that do not match profile skills ----
    recommended_modules = []
    if profile and profile.skills:
        profile_skills_words = set()
        for skill in profile.skills.split(','):
            profile_skills_words.update(re.findall(r'\w+', skill.lower()))

        for module in Module.objects.all():
            module_name_words = set(re.findall(r'\w+', module.name.lower()))
            if profile_skills_words.isdisjoint(module_name_words):
                recommended_modules.append(module)
    else:
        # If no skills, recommend all modules
        recommended_modules = list(Module.objects.all())
    
    return render(request, 'user/profile.html', {
        'profile_form': profile_form,
        'resume_form': resume_form,
        'resume': resume,  # Single resume object instead of queryset
        'user': request.user,
        'total_xp': total_xp,
        'recommended_modules': recommended_modules

    })

import PyPDF2
# Utility functions for text and skill extraction
def extract_text_from_file(file):
    """Extract text from uploaded file (PDF or TXT)"""
    file_extension = file.name.split('.')[-1].lower()
    file.seek(0)  # Ensure we're at start of file
    
    if file_extension == 'pdf':
        pdf_reader = PyPDF2.PdfReader(file)
        text = '\n'.join([page.extract_text() for page in pdf_reader.pages])
    else:  # txt
        text = file.read().decode('utf-8')
    
    return text

def extract_skills_from_text(text):
    """Extract skills from text using basic matching (enhance with NLP if needed)"""
    # Define common skills to look for (expand this list)
    COMMON_SKILLS = {
        # Programming Languages
        'python', 'java', 'c', 'c++', 'c#', 'javascript', 'typescript', 'ruby', 
        'go', 'rust', 'php', 'swift', 'kotlin', 'scala', 'perl', 'shell scripting',

        # Web Technologies & Frameworks
        'html', 'css', 'react', 'angular', 'vue.js', 'django', 'flask', 'spring', 
        'express', 'next.js', 'nuxt.js', 'bootstrap', 'tailwind css', 'jquery',

        # Databases
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'oracle', 'sqlite', 

        # Cloud Platforms & DevOps
        'aws', 'azure', 'google cloud platform', 'docker', 'kubernetes', 'terraform', 
        'ansible', 'jenkins', 'git', 'ci/cd', 'linux', 'bash', 'powershell',

        # Data, AI & Machine Learning
        'machine learning', 'deep learning', 'data analysis', 'data science', 
        'pandas', 'numpy', 'tensorflow', 'pytorch', 'scikit-learn', 'matplotlib', 
        'seaborn', 'natural language processing', 'computer vision',

        # Others / Methodologies
        'rest api', 'graphql', 'microservices', 'agile', 'scrum', 'oop', 'functional programming',
        'test driven development', 'unit testing', 'integration testing',

        # Version Control & Collaboration
        'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence',

        # Mobile Development
        'android', 'ios', 'react native', 'flutter', 'xamarin',

        # Big Data & Streaming
        'hadoop', 'spark', 'kafka',

        # Security
        'cybersecurity', 'oauth', 'jwt', 'encryption',

        # Containers & Virtualization
        'docker', 'kubernetes', 'openshift',

        # Messaging and APIs
        'rest', 'soap', 'websockets',

        # Other Tools & Concepts
        'eslint', 'prettier', 'webpack', 'babel', 'chrome devtools'
    }

    
    found_skills = set()
    text_lower = text.lower()

    for skill in COMMON_SKILLS:
        pattern = r'\b' + re.escape(skill.lower()).replace(r'\ ', r'\s+') + r'\b'
        if re.search(pattern, text_lower):
            found_skills.add(skill.title())

    return sorted(found_skills)

@login_required
def delete_resume(request, resume_id):
    try:
        resume = Resume.objects.get(id=resume_id, user=request.user)
        resume.delete()
        messages.success(request, 'Resume deleted successfully!')
    except Resume.DoesNotExist:
        messages.error(request, 'Resume not found or you do not have permission to delete it.')
    return redirect('profile')



#AIIIIIIII

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .services.chatbot_service import ProgrammingChatbot
from .models import CodingProblem, ChatConversation
import json
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@login_required
def chatbot_ask(request):
    """Handle chatbot questions with Mistral-7B"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        problem_id = data.get('problem_id')
        question = data.get('question', '').strip()
        
        if not problem_id or not question:
            return JsonResponse({'error': 'Problem ID and question are required'}, status=400)
        
        if len(question) > 1000:
            return JsonResponse({'error': 'Question too long. Please keep it under 1000 characters.'}, status=400)
        
        try:
            problem = CodingProblem.objects.get(id=problem_id, is_active=True)
        except CodingProblem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found'}, status=404)
        
        # Get response from Mistral chatbot
        chatbot = ProgrammingChatbot()
        response = chatbot.get_programming_hint(request.user, problem, question)
        
        # Get conversation summary for frontend
        summary = chatbot.get_conversation_summary(request.user, problem)
        
        return JsonResponse({
            'response': response,
            'status': 'success',
            'summary': summary
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Chatbot endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def get_chat_history(request, problem_id):
    """Get chat history for a problem"""
    try:
        problem = get_object_or_404(CodingProblem, id=problem_id, is_active=True)
        conversation = ChatConversation.objects.filter(
            user=request.user, 
            problem=problem,
            is_active=True
        ).first()
        
        if not conversation:
            return JsonResponse({'messages': []})
        
        messages = []
        for msg in conversation.messages.exclude(role='system').order_by('timestamp'):
            messages.append({
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            })
        
        return JsonResponse({'messages': messages})
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@csrf_exempt
@login_required
def clear_chat_history(request, problem_id):
    """Clear chat history for a specific problem - Fixed version"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)
    
    try:
        # Get the problem
        try:
            problem = CodingProblem.objects.get(id=problem_id, is_active=True)
        except CodingProblem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found'}, status=404)
        
        # ✅ Use chatbot service to clear history properly
        chatbot = ProgrammingChatbot()
        success = chatbot.clear_chat_history(request.user, problem)
        
        if success:
            logger.info(f"Chat history cleared for user {request.user.id} and problem {problem_id}")
            return JsonResponse({
                'status': 'success',
                'message': 'Chat history cleared successfully'
            })
        else:
            logger.error(f"Failed to clear chat history for user {request.user.id} and problem {problem_id}")
            return JsonResponse({'error': 'Failed to clear chat history'}, status=500)
            
    except Exception as e:
        logger.error(f"Clear chat endpoint error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


# myapp/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from .models import (
    CustomUser, UserProfile, Module, ModuleContent,
    QuizAttemptLearningPath, QuizUserAnswer,
    AssignmentSubmission, ModuleCompletion, LearningPath, ProgressNode,
    Hackathon, HackathonTeam, HackathonRegistration, HackathonSubmission, HackathonEvaluation,
    Leaderboard, Assessment,
    Competency, Question, Answer, UserCompetency, QuizSettings, QuizAttempt, QuizResponse,
    QuizAssessment,
    CodingProblem, CodeSubmission,
    Certificate, TempUserRegistration, OTP, Resume
)

def is_staff_user(user):
    return user.is_active and user.is_staff

@user_passes_test(is_staff_user)
def admin_panel(request):
    context = {
        'counts': {
            'users': CustomUser.objects.count(),
            'profiles': UserProfile.objects.count(),
            'modules': Module.objects.count(),
            'module_contents': ModuleContent.objects.count(),
            'quiz_attempts_lp': QuizAttemptLearningPath.objects.count(),
            'quiz_user_answers': QuizUserAnswer.objects.count(),
            'assignment_submissions': AssignmentSubmission.objects.count(),
            'module_completions': ModuleCompletion.objects.count(),
            'learning_paths': LearningPath.objects.count(),
            'progress_nodes': ProgressNode.objects.count(),
            'hackathons': Hackathon.objects.count(),
            'hackathon_teams': HackathonTeam.objects.count(),
            'hackathon_regs': HackathonRegistration.objects.count(),
            'hackathon_submissions': HackathonSubmission.objects.count(),
            'hackathon_evaluations': HackathonEvaluation.objects.count(),
            'leaderboards': Leaderboard.objects.count(),
            'assessments': Assessment.objects.count(),
            'competencies': Competency.objects.count(),
            'questions': Question.objects.count(),
            'answers': Answer.objects.count(),
            'user_competencies': UserCompetency.objects.count(),
            'quiz_settings': QuizSettings.objects.count(),
            'quiz_attempts': QuizAttempt.objects.count(),
            'quiz_responses': QuizResponse.objects.count(),
            'quiz_assessments': QuizAssessment.objects.count(),
            'coding_problems': CodingProblem.objects.count(),
            'code_submissions': CodeSubmission.objects.count(),
            'certificates': Certificate.objects.count(),
            'temp_users': TempUserRegistration.objects.count(),
            'otps': OTP.objects.count(),
            'resumes': Resume.objects.count(),
        },
        # Example recent entries (could be customized further)
        'recent_users': CustomUser.objects.order_by('-date_joined')[:5],
        'recent_modules': Module.objects.order_by('-created_at')[:5],
        'recent_coding_problems': CodingProblem.objects.order_by('-created_at')[:5],
        'recent_hackathons': Hackathon.objects.order_by('-start_date')[:5],
        # Add more recent querysets as desired...
    }
    return render(request, 'admin1/admin_panel.html', context)



import json
import requests
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

OPENROUTER_API_KEY = '#ENTER YOUR API KEY'  # << Secure this key


@csrf_exempt
def generate_quiz(request):
    if request.method == 'POST':
        language = request.POST.get('language', 'Python')

        prompt = f"""
        Generate exactly 10 multiple-choice questions (MCQs) about {language} programming.
        Each question must follow this JSON format exactly:

        [
          {{
            "question": "What is Python?",
            "choices": ["A snake", "A programming language", "A movie", "A car"],
            "correct_answer": "A programming language"
          }},
          ...
        ]

        Output ONLY valid JSON. Do not include any explanation or formatting.
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:8000/",
            "X-Title": "AIQuizApp"
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={
                    "model": "mistralai/mistral-7b-instruct",
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(f"API HTTP {response.status_code}: {response.text}")

            data = response.json()

            raw_content = data['choices'][0]['message']['content'].strip()

            # Handle potential leading text before JSON
            json_start = raw_content.find('[')
            if json_start != -1:
                raw_content = raw_content[json_start:]

            questions = json.loads(raw_content)

            if not isinstance(questions, list):
                raise Exception("API returned an unexpected structure.")

            request.session['quiz_data'] = questions
            return redirect('quiz')

        except Exception as e:
            return render(request, 'test/quiz.html', {
                'error': f'API error: {str(e)}',
                'quiz_data': [],
                'selected_language': language if 'language' in locals() else None
            })


    return redirect('quiz')


@csrf_exempt
def quiz_view(request):
    quiz_data = request.session.get('quiz_data', [])

    if request.method == 'POST' and quiz_data:
        user_answers = {k.replace('q_', ''): v for k, v in request.POST.items() if k.startswith('q_')}
        results = []

        for i, q in enumerate(quiz_data):
            selected = user_answers.get(str(i), '')
            correct = q['correct_answer']
            results.append({
                'question': q['question'],
                'choices': q['choices'],
                'selected': selected,
                'correct_answer': correct,
                'is_correct': selected == correct
            })

        return render(request, 'test/quiz.html', {
            'results': results,
            'quiz_data': quiz_data
        })

    return render(request, 'test/quiz.html', {'quiz_data': quiz_data})
