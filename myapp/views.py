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
import json
import random
from .models import *
from .forms import *
from django.core.mail import send_mail

# ==========================
# General Views and Utilities
# ==========================
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

@login_required
def dashboard(request):
    user = request.user
    progress_nodes = ProgressNode.objects.filter(user=user).order_by('timestamp')
    learning_paths = LearningPath.objects.filter(user=user).order_by('-started_at')[:5]
    assessments = Assessment.objects.filter(user=user).order_by('-timestamp')[:3]
    hackathons = Hackathon.objects.filter(is_active=True).order_by('-start_date')[:3]
    # badges = Badge.objects.filter(user=user).order_by('-date_awarded')[:5]

    context = {
        'user': user,
        'progress_nodes': progress_nodes,
        'learning_paths': learning_paths,
        'assessments': assessments,
        'hackathons': hackathons,
        # 'badges': badges,
    }
    return render(request, 'user/dashboard.html', context)

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
    modules = Module.objects.all()
    return render(request, 'user/module_list.html', {'modules': modules})

@login_required
@login_required
def module_detail(request, module_id):
    module = get_object_or_404(Module.objects.prefetch_related('contents'), id=module_id)
    learning_path = LearningPath.objects.filter(user=request.user, module=module).first()
    
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
# ENHANCED HACKATHON VIEWS
# ============================================

@login_required
def hackathon_view(request):
    """Main hackathon listing page"""
    now = timezone.now()
    
    # Categorize hackathons
    upcoming_hackathons = Hackathon.objects.filter(
        is_active=True,
        registration_start__gt=now
    ).annotate(
        participant_count=Count('registrations', filter=Q(registrations__is_active=True))
    ).order_by('registration_start')
    
    open_hackathons = Hackathon.objects.filter(
        is_active=True,
        registration_start__lte=now,
        registration_end__gte=now,
        status='registration_open'
    ).annotate(
        participant_count=Count('registrations', filter=Q(registrations__is_active=True))
    ).order_by('registration_end')
    
    active_hackathons = Hackathon.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
        status='in_progress'
    ).annotate(
        participant_count=Count('registrations', filter=Q(registrations__is_active=True))
    ).order_by('end_date')
    
    completed_hackathons = Hackathon.objects.filter(
        status='completed'
    ).annotate(
        participant_count=Count('registrations', filter=Q(registrations__is_active=True))
    ).order_by('-end_date')[:5]
    
    # User's hackathon involvement
    my_registrations = HackathonRegistration.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('hackathon', 'team')
    
    my_teams = HackathonTeam.objects.filter(
        Q(leader=request.user) | Q(members=request.user)
    ).select_related('hackathon')
    
    my_submissions = HackathonSubmission.objects.filter(
        Q(individual_user=request.user) | Q(team__members=request.user)
    ).select_related('hackathon', 'team').order_by('-submitted_at')
    
    context = {
        'upcoming_hackathons': upcoming_hackathons,
        'open_hackathons': open_hackathons,
        'active_hackathons': active_hackathons,
        'completed_hackathons': completed_hackathons,
        'my_registrations': my_registrations,
        'my_teams': my_teams,
        'my_submissions': my_submissions,
    }
    
    return render(request, 'user/hackathon.html', context)

@login_required
def create_hackathon(request):
    """Create new hackathon (both students and admins)"""
    if request.method == 'POST':
        form = HackathonCreateForm(request.POST, request.FILES)
        if form.is_valid():
            hackathon = form.save(commit=False)
            hackathon.created_by = request.user
            
            # Set initial status based on registration dates
            now = timezone.now()
            if hackathon.registration_start <= now <= hackathon.registration_end:
                hackathon.status = 'registration_open'
            elif now < hackathon.registration_start:
                hackathon.status = 'upcoming'
            elif hackathon.start_date <= now <= hackathon.end_date:
                hackathon.status = 'in_progress'
            
            hackathon.save()
            messages.success(request, f'Hackathon "{hackathon.name}" created successfully!')
            return redirect('hackathon_detail', hackathon_id=hackathon.id)
    else:
        form = HackathonCreateForm()
    
    return render(request, 'user/create_hackathon.html', {'form': form})

@login_required
def hackathon_detail(request, hackathon_id):
    """Detailed hackathon view with creator-participant functionality"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    # Check if user is registered
    user_registration = None
    user_team = None
    user_submission = None
    
    if request.user.is_authenticated:
        user_registration = HackathonRegistration.objects.filter(
            user=request.user, 
            hackathon=hackathon,
            is_active=True
        ).first()
        
        if user_registration:
            user_team = user_registration.team
            
        # Check for user's submission
        user_submission = HackathonSubmission.objects.filter(
            hackathon=hackathon,
            individual_user=request.user  # For individual submissions
        ).first()
        
        if not user_submission and user_team:
            user_submission = HackathonSubmission.objects.filter(
                hackathon=hackathon,
                team=user_team
            ).first()
    
    # Determine what actions user can take
    can_register = (
        request.user.is_authenticated and 
        hackathon.is_registration_open and
        not user_registration and
        hackathon.current_participants < hackathon.max_participants
        # REMOVED creator restriction - now creators can register too!
    )
    
    can_submit = (
        user_registration and 
        hackathon.status == 'in_progress' and
        not user_submission
    )
    
    # Check if user is the creator
    is_creator = hackathon.is_user_creator(request.user) if request.user.is_authenticated else False
    
    # Get available teams to join (only if user is not in a team and registration is open)
    available_teams = None
    if hackathon.is_registration_open and user_registration and not user_team:
        available_teams = HackathonTeam.objects.filter(
            hackathon=hackathon,
            is_active=True
        ).annotate(
            member_count=Count('members')
        ).filter(
            member_count__lt=hackathon.team_size_max
        )
    
    # Get submissions for results (only if hackathon is completed)
    submissions = None
    if hackathon.status == 'completed':
        submissions = hackathon.submissions.filter(
            final_score__isnull=False
        ).order_by('-final_score')[:10]
    
    context = {
        'hackathon': hackathon,
        'user_registration': user_registration,
        'user_team': user_team,
        'user_submission': user_submission,
        'available_teams': available_teams,
        'submissions': submissions,
        'can_register': can_register,
        'can_submit': can_submit,
        'is_creator': is_creator,  # NEW: Pass creator status to template
        'criteria': hackathon.evaluation_criteria,
    }
    
    return render(request, 'user/hackathon_detail.html', context)

@login_required
def register_hackathon(request, hackathon_id):
    """Register for hackathon - now allows creators to participate"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    if not hackathon.is_registration_open:
        messages.error(request, "Registration is not open for this hackathon.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    if hackathon.spots_remaining <= 0:
        messages.error(request, "This hackathon is full.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Check if already registered
    if HackathonRegistration.objects.filter(hackathon=hackathon, user=request.user, is_active=True).exists():
        messages.info(request, "You're already registered for this hackathon.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Create registration (now works for creators too!)
    HackathonRegistration.objects.create(
        hackathon=hackathon,
        user=request.user
    )
    
    # Special message for creators
    if hackathon.is_user_creator(request.user):
        messages.success(request, f"Successfully registered as a participant for your hackathon '{hackathon.name}'!")
    else:
        messages.success(request, f"Successfully registered for {hackathon.name}!")
    
    return redirect('hackathon_detail', hackathon_id=hackathon.id)

@login_required
def manage_team(request, hackathon_id):
    """Team management page"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    # Check if user is registered
    user_registration = HackathonRegistration.objects.filter(
        hackathon=hackathon,
        user=request.user,
        is_active=True
    ).first()
    
    if not user_registration:
        messages.error(request, "You must be registered to manage teams.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    user_team = user_registration.team
    join_form = TeamJoinForm()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_team':
            if user_team:
                messages.error(request, "You're already in a team.")
            else:
                form = HackathonTeamForm(request.POST)
                if form.is_valid():
                    team = form.save(commit=False)
                    team.hackathon = hackathon
                    team.leader = request.user
                    team.save()
                    
                    # Update user's registration
                    user_registration.team = team
                    user_registration.save()
                    
                    messages.success(request, f'Team "{team.name}" created successfully!')
                    return redirect('manage_team', hackathon_id=hackathon.id)
        
        elif action == 'join_team':
            if user_team:
                messages.error(request, "You're already in a team.")
            else:
                join_form = TeamJoinForm(request.POST)
                if join_form.is_valid():
                    invite_code = join_form.cleaned_data['invite_code']
                    try:
                        team = HackathonTeam.objects.get(
                            hackathon=hackathon,
                            invite_code=invite_code,
                            is_active=True
                        )
                        
                        if team.can_add_members:
                            user_registration.team = team
                            user_registration.save()
                            messages.success(request, f'Successfully joined team "{team.name}"!')
                            return redirect('manage_team', hackathon_id=hackathon.id)
                        else:
                            messages.error(request, "This team is full.")
                    except HackathonTeam.DoesNotExist:
                        messages.error(request, "Invalid invite code.")
        
        elif action == 'leave_team':
            if user_team:
                if user_team.leader == request.user:
                    if user_team.member_count > 1:
                        messages.error(request, "Transfer leadership before leaving the team.")
                    else:
                        user_team.delete()
                        messages.success(request, "Team deleted successfully.")
                        return redirect('manage_team', hackathon_id=hackathon.id)
                else:
                    user_registration.team = None
                    user_registration.save()
                    messages.success(request, "Left the team successfully.")
                    return redirect('manage_team', hackathon_id=hackathon.id)
    
    # Get available teams to join
    available_teams = HackathonTeam.objects.filter(
        hackathon=hackathon,
        is_active=True
    ).annotate(
        member_count=Count('members')
    ).filter(
        member_count__lt=hackathon.team_size_max
    )
    
    context = {
        'hackathon': hackathon,
        'user_team': user_team,
        'team_form': HackathonTeamForm(),
        'join_form': join_form,
        'available_teams': available_teams,
        'is_leader': user_team and user_team.leader == request.user,
    }
    
    return render(request, 'user/manage_team.html', context)

@login_required
def submit_hackathon_project(request, hackathon_id):
    """Submit project for hackathon"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    if not hackathon.can_submit:
        messages.error(request, "Submission is not currently allowed for this hackathon.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Check if user is registered
    user_registration = HackathonRegistration.objects.filter(
        hackathon=hackathon,
        user=request.user,
        is_active=True
    ).first()
    
    if not user_registration:
        messages.error(request, "You must be registered to submit.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Check if already submitted
    existing_submission = HackathonSubmission.objects.filter(
        Q(hackathon=hackathon) & 
        (Q(individual_user=request.user) | Q(team__members=request.user))
    ).first()
    
    if existing_submission:
        messages.info(request, "You've already submitted to this hackathon.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Check team requirements
    user_team = user_registration.team
    if not hackathon.allow_individual and not user_team:
        messages.error(request, "This hackathon requires team participation.")
        return redirect('manage_team', hackathon_id=hackathon.id)
    
    if request.method == 'POST':
        form = HackathonSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.hackathon = hackathon
            
            if user_team:
                submission.team = user_team
            else:
                submission.individual_user = request.user
            
            submission.save()
            messages.success(request, 'Project submitted successfully!')
            return redirect('hackathon_detail', hackathon_id=hackathon.id)
    else:
        form = HackathonSubmissionForm()
    
    context = {
        'hackathon': hackathon,
        'form': form,
        'user_team': user_team,
    }
    
    return render(request, 'user/submit_project.html', context)

@login_required
def hackathon_results(request, hackathon_id):
    """Display hackathon results"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    
    if hackathon.status != 'completed':
        messages.info(request, "Results are not yet available.")
        return redirect('hackathon_detail', hackathon_id=hackathon.id)
    
    # Get ranked submissions
    submissions = hackathon.submissions.filter(
        final_score__isnull=False
    ).order_by('-final_score', '-submitted_at')
    
    # Update ranks
    for index, submission in enumerate(submissions, 1):
        if submission.rank != index:
            submission.rank = index
            submission.save(update_fields=['rank'])
    
    winners = submissions.filter(is_winner=True)
    
    context = {
        'hackathon': hackathon,
        'submissions': submissions,
        'winners': winners,
        'criteria': hackathon.evaluation_criteria,
    }
    
    return render(request, 'user/hackathon_results.html', context)

# ============================================
# ADMIN HACKATHON MANAGEMENT VIEWS
# ============================================

@login_required
@user_passes_test(is_admin)
def admin_hackathon_management(request):
    """Enhanced admin hackathon management"""
    if request.method == 'POST':
        form = HackathonCreateForm(request.POST, request.FILES)
        if form.is_valid():
            hackathon = form.save(commit=False)
            hackathon.created_by = request.user
            hackathon.save()
            messages.success(request, 'Hackathon created successfully!')
            return redirect('admin_hackathon_management')
    else:
        form = HackathonCreateForm()
    
    hackathons = Hackathon.objects.annotate(
        participant_count=Count('registrations', filter=Q(registrations__is_active=True)),
        submission_count=Count('submissions'),
        team_count=Count('teams', filter=Q(teams__is_active=True))
    ).order_by('-created_at')
    
    context = {
        'form': form,
        'hackathons': hackathons,
    }
    
    return render(request, 'admin/hackathon_management.html', context)

@login_required
@user_passes_test(is_admin)
def evaluate_submissions(request, hackathon_id):
    """Evaluate hackathon submissions"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    submissions = hackathon.submissions.all().order_by('-submitted_at')
    
    if request.method == 'POST':
        submission_id = request.POST.get('submission_id')
        submission = get_object_or_404(HackathonSubmission, id=submission_id)
        
        # Create evaluation form with hackathon criteria
        form = HackathonEvaluationForm(request.POST, criteria=hackathon.evaluation_criteria)
        
        if form.is_valid():
            # Extract scores
            scores = {}
            for criterion in hackathon.evaluation_criteria.keys():
                score = form.cleaned_data.get(f'score_{criterion}')
                if score is not None:
                    scores[criterion] = score
            
            # Create or update evaluation
            evaluation, created = HackathonEvaluation.objects.get_or_create(
                submission=submission,
                evaluator=request.user,
                defaults={
                    'scores': scores,
                    'comments': form.cleaned_data.get('comments', '')
                }
            )
            
            if not created:
                evaluation.scores = scores
                evaluation.comments = form.cleaned_data.get('comments', '')
                evaluation.save()
            
            # Calculate weighted final score
            total_weight = sum(hackathon.evaluation_criteria.values())
            final_score = sum(
                score * hackathon.evaluation_criteria[criterion] / hackathon.evaluation_criteria[criterion] * 100
                for criterion, score in scores.items()
            ) / len(scores) if scores else 0
            
            submission.scores = scores
            submission.final_score = final_score
            submission.save()
            
            messages.success(request, 'Evaluation saved successfully!')
            return redirect('evaluate_submissions', hackathon_id=hackathon.id)
    
    # Create forms for each submission
    submission_forms = []
    for submission in submissions:
        form = HackathonEvaluationForm(criteria=hackathon.evaluation_criteria)
        
        # Pre-populate if already evaluated by current user
        existing_eval = HackathonEvaluation.objects.filter(
            submission=submission,
            evaluator=request.user
        ).first()
        
        if existing_eval:
            initial_data = {'comments': existing_eval.comments}
            for criterion, score in existing_eval.scores.items():
                initial_data[f'score_{criterion}'] = score
            form = HackathonEvaluationForm(initial=initial_data, criteria=hackathon.evaluation_criteria)
        
        submission_forms.append({
            'submission': submission,
            'form': form,
            'evaluated': existing_eval is not None
        })
    
    context = {
        'hackathon': hackathon,
        'submission_forms': submission_forms,
    }
    
    return render(request, 'admin/evaluate_submissions.html', context)

@login_required
@user_passes_test(is_admin)
def select_winners(request, hackathon_id):
    """Select hackathon winners"""
    hackathon = get_object_or_404(Hackathon, id=hackathon_id)
    submissions = hackathon.submissions.filter(
        final_score__isnull=False
    ).order_by('-final_score')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'mark_winners':
            winner_ids = request.POST.getlist('winners')
            
            # Clear existing winners
            hackathon.submissions.update(is_winner=False, prize_category='')
            
            # Mark new winners
            for i, submission_id in enumerate(winner_ids):
                submission = get_object_or_404(HackathonSubmission, id=submission_id)
                submission.is_winner = True
                
                # Set prize category based on rank
                if i == 0:
                    submission.prize_category = '1st Place'
                elif i == 1:
                    submission.prize_category = '2nd Place'
                elif i == 2:
                    submission.prize_category = '3rd Place'
                else:
                    submission.prize_category = f'{i+1}th Place'
                
                submission.save()
            
            messages.success(request, f'{len(winner_ids)} winners selected successfully!')
        
        elif action == 'complete_hackathon':
            hackathon.status = 'completed'
            hackathon.save()
            messages.success(request, 'Hackathon marked as completed!')
    
    context = {
        'hackathon': hackathon,
        'submissions': submissions,
    }
    
    return render(request, 'admin/select_winners.html', context)

# ============================================
# ASSESSMENT AND QUIZ RELATED VIEWS (ORGANIZED)
# ============================================

@login_required
def assessment_view(request):
    """Main assessment view with competency progress tracking"""
    # Handle regular assessment submission
    if request.method == 'POST':
        form = AssessmentForm(request.POST, request.FILES)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.user = request.user
            assessment.save()
            messages.success(request, 'Assessment submitted successfully!')
            return redirect('assessment')
    else:
        form = AssessmentForm()

    user = request.user
    competencies = Competency.objects.filter(is_active=True).order_by('name')

    # Get user competency data
    user_comp_qs = UserCompetency.objects.filter(user=user)
    user_comp_map = {uc.competency_id: uc for uc in user_comp_qs}

    # Build comprehensive user competencies list
    user_competencies = []
    for comp in competencies:
        uc = user_comp_map.get(comp.id)
        
        # Check for in-progress attempts
        has_in_progress_attempt = QuizAttempt.objects.filter(
            user=user,
            competency=comp,
            status='in_progress'
        ).exists()
        
        # Get latest attempt for additional info
        latest_attempt = QuizAttempt.objects.filter(
            user=user,
            competency=comp
        ).order_by('-start_time').first()

        user_competencies.append({
            'competency': comp,
            'score': uc.score if uc else 0,  # Default to 0 instead of None
            'attempted': uc is not None,
            'has_in_progress_attempt': has_in_progress_attempt,
            'reached_max_attempts': False,  # Always False - unlimited attempts
            'attempts_count': uc.attempts_count if uc else 0,
            'best_score': uc.best_score if uc else 0,
            'latest_attempt': latest_attempt,
        })

    context = {
        'form': form,
        'assessments': Assessment.objects.filter(user=user).order_by('-timestamp'),
        'competencies': competencies,
        'user_competencies': user_competencies,
    }
    return render(request, 'user/assessment.html', context)

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



# -------------------
# CODING PROBLEMS - FIXED VERSION
# -------------------

import json
import subprocess
import tempfile
import os
import ast
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

def problem_list(request):
    """List all coding problems"""
    problems = CodingProblem.objects.filter(is_active=True)
    
    # Filter by difficulty if provided
    difficulty = request.GET.get('difficulty')
    if difficulty in ['easy', 'medium', 'hard']:
        problems = problems.filter(difficulty=difficulty)
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        problems = problems.filter(title__icontains=search)
    
    context = {
        'problems': problems,
        'current_difficulty': difficulty,
        'search_query': search,
    }
    return render(request, 'coding/problem_list.html', context)

def problem_detail(request, problem_id):
    """Individual problem page with compiler"""
    problem = get_object_or_404(CodingProblem, id=problem_id, is_active=True)
    
    # Get user's previous submissions for this problem
    user_submissions = []
    if request.user.is_authenticated:
        user_submissions = CodeSubmission.objects.filter(
            user=request.user, 
            problem=problem
        ).order_by('-submitted_at')[:10]
    
    # Split tags in the view
    problem_tags = [tag.strip() for tag in problem.tags.split(',') if tag.strip()]
    
    # **FIXED: Improved code templates with proper structure**
    code_templates = {
        'python': '''def two_sum(nums, target):
    """
    Your solution here
    Args:
        nums: List of integers
        target: Target sum
    Returns:
        List of two indices
    """
    # Write your algorithm here
    num_map = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in num_map:
            return [num_map[complement], i]
        num_map[num] = i
    return []

# Test execution (do not modify)
if __name__ == "__main__":
    result = two_sum(nums, target)
    print(result)''',
    
        'javascript': '''function twoSum(nums, target) {
    /**
     * Your solution here
     * @param {number[]} nums
     * @param {number} target
     * @return {number[]}
     */
    // Write your algorithm here
    const numMap = new Map();
    for (let i = 0; i < nums.length; i++) {
        const complement = target - nums[i];
        if (numMap.has(complement)) {
            return [numMap.get(complement), i];
        }
        numMap.set(nums[i], i);
    }
    return [];
}

// Test execution (do not modify)
const result = twoSum(nums, target);
console.log(JSON.stringify(result));''',
    
        'java': '''import java.util.HashMap;
import java.util.Map;

public class Solution {
    public int[] twoSum(int[] nums, int target) {
        /*
         * Your solution here
         */
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) {
                return new int[]{map.get(complement), i};
            }
            map.put(nums[i], i);
        }
        return new int[]{};
    }
    
    // Test execution (do not modify)
    public static void main(String[] args) {
        Solution sol = new Solution();
        int[] result = sol.twoSum(nums, target);
        System.out.print("[" + result[0] + "," + result[1] + "]");
    }
}'''
    }
    
    context = {
        'problem': problem,
        'problem_tags': problem_tags,
        'user_submissions': user_submissions,
        'code_templates': json.dumps(code_templates),
    }
    return render(request, 'coding/problem_detail.html', context)

@csrf_exempt
@require_POST
@login_required
def submit_code(request):
    """Handle code submission and execution"""
    try:
        data = json.loads(request.body)
        problem_id = data.get('problem_id')
        code = data.get('code')
        language = data.get('language')
        
        if not all([problem_id, code, language]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        problem = get_object_or_404(CodingProblem, id=problem_id)
        
        # Create submission record
        submission = CodeSubmission.objects.create(
            user=request.user,
            problem=problem,
            code=code,
            language=language,
            status='running'
        )
        
        # Execute code
        result = execute_code(submission)
        
        return JsonResponse({
            'submission_id': submission.id,
            'status': submission.status,
            'results': result
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def execute_code(submission):
    """Execute submitted code against test cases"""
    try:
        problem = submission.problem
        test_cases = problem.test_cases
        results = []
        all_passed = True
        
        for i, test_case in enumerate(test_cases):
            result = run_single_test(submission.code, submission.language, test_case)
            results.append(result)
            
            # If any test fails, mark as wrong answer
            if not result['passed']:
                all_passed = False
                submission.status = 'wrong_answer'
                break
        
        if all_passed:
            submission.status = 'accepted'
            problem.accepted_submissions += 1
        
        # Update statistics
        problem.total_submissions += 1
        problem.save()
        
        submission.test_results = results
        submission.save()
        
        return {
            'status': submission.status,
            'test_results': results,
            'execution_time': submission.execution_time,
            'memory_used': submission.memory_used
        }
        
    except Exception as e:
        submission.status = 'runtime_error'
        submission.error_message = str(e)
        submission.save()
        return {'status': 'runtime_error', 'error': str(e)}

def run_single_test(code, language, test_case):
    """Run code against a single test case"""
    try:
        if language == 'python':
            return run_python_code(code, test_case)
        elif language == 'javascript':
            return run_javascript_code(code, test_case)
        elif language == 'java':
            return run_java_code(code, test_case)
        else:
            return {'passed': False, 'error': 'Language not supported'}
            
    except Exception as e:
        return {'passed': False, 'error': str(e)}

def run_python_code(code, test_case):
    """**FIXED: Execute Python code with proper variable injection**"""
    try:
        # Parse the input string properly
        input_str = test_case['input']  # e.g., "[3,2,4], 6"
        
        # Extract nums array and target from input
        if ',' in input_str and '[' in input_str:
            last_comma = input_str.rfind(',')
            nums_str = input_str[:last_comma].strip()
            target_str = input_str[last_comma + 1:].strip()
            
            # **FIXED: Inject variables at the top level, outside functions**
            wrapper_code = f"""# Test case data injection
nums = {nums_str}
target = {target_str}

{code}
"""
        else:
            wrapper_code = code
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapper_code)
            temp_file = f.name
        
        # Execute with timeout
        result = subprocess.run(
            ['python3', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Clean up
        os.unlink(temp_file)
        
        if result.returncode != 0:
            return {
                'passed': False,
                'error': result.stderr,
                'output': result.stdout,
                'input': test_case['input']
            }
        
        # **FIXED: Proper result comparison**
        try:
            expected = ast.literal_eval(test_case['output'])
            actual_output = result.stdout.strip()
            
            # Handle different output formats
            if actual_output.startswith('[') and actual_output.endswith(']'):
                actual = ast.literal_eval(actual_output)
            else:
                # Try to extract list from output
                import re
                list_match = re.search(r'\[.*\]', actual_output)
                if list_match:
                    actual = ast.literal_eval(list_match.group())
                else:
                    actual = actual_output
            
            return {
                'passed': expected == actual,
                'expected': test_case['output'],
                'actual': str(actual),
                'input': test_case['input']
            }
            
        except (ValueError, SyntaxError) as e:
            return {
                'passed': False,
                'error': f'Output parsing failed: {e}',
                'expected': test_case['output'],
                'actual': result.stdout.strip(),
                'input': test_case['input']
            }
        
    except subprocess.TimeoutExpired:
        return {'passed': False, 'error': 'Time limit exceeded'}
    except Exception as e:
        return {'passed': False, 'error': str(e)}

def run_javascript_code(code, test_case):
    """**FIXED: Execute JavaScript code with proper input parsing**"""
    try:
        # Parse the input string properly
        input_str = test_case['input']
        
        if ',' in input_str and '[' in input_str:
            last_comma = input_str.rfind(',')
            nums_str = input_str[:last_comma].strip()
            target_str = input_str[last_comma + 1:].strip()
            
            # **FIXED: Proper JavaScript variable injection**
            wrapper_code = f"""// Test case data injection
const nums = {nums_str};
const target = {target_str};

{code}
"""
        else:
            wrapper_code = code
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(wrapper_code)
            temp_file = f.name
        
        # Execute with Node.js
        result = subprocess.run(
            ['node', temp_file],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Clean up
        os.unlink(temp_file)
        
        if result.returncode != 0:
            return {
                'passed': False,
                'error': result.stderr,
                'output': result.stdout
            }
        
        # **FIXED: Proper JavaScript result comparison**
        try:
            expected = ast.literal_eval(test_case['output'])
            actual_output = result.stdout.strip()
            
            # Parse JavaScript array output
            if actual_output.startswith('[') and actual_output.endswith(']'):
                actual = ast.literal_eval(actual_output)
            else:
                # Try JSON parsing
                import json
                actual = json.loads(actual_output)
            
            return {
                'passed': expected == actual,
                'expected': test_case['output'],
                'actual': str(actual),
                'input': test_case['input']
            }
            
        except (ValueError, SyntaxError, json.JSONDecodeError) as e:
            return {
                'passed': False,
                'error': f'Output parsing failed: {e}',
                'expected': test_case['output'],
                'actual': result.stdout.strip(),
                'input': test_case['input']
            }
        
    except subprocess.TimeoutExpired:
        return {'passed': False, 'error': 'Time limit exceeded'}
    except Exception as e:
        return {'passed': False, 'error': str(e)}

def run_java_code(code, test_case):
    """**NEW: Execute Java code**"""
    try:
        # Parse the input string properly
        input_str = test_case['input']
        
        if ',' in input_str and '[' in input_str:
            last_comma = input_str.rfind(',')
            nums_str = input_str[:last_comma].strip().replace('[', '{').replace(']', '}')
            target_str = input_str[last_comma + 1:].strip()
            
            # **NEW: Java variable injection**
            wrapper_code = f"""// Test case data injection
public class Solution {{
    public int[] twoSum(int[] nums, int target) {{
        // User code will be inserted here
    }}
    
    public static void main(String[] args) {{
        Solution sol = new Solution();
        int[] nums = {nums_str};
        int target = {target_str};
        int[] result = sol.twoSum(nums, target);
        System.out.print("[" + result[0] + "," + result[1] + "]");
    }}
}}
"""
            # Extract user's twoSum method
            import re
            method_match = re.search(r'public int\[\] twoSum\(.*?\{(.*)\}', code, re.DOTALL)
            if method_match:
                user_method = method_match.group(1)
                wrapper_code = wrapper_code.replace('// User code will be inserted here', user_method)
        else:
            wrapper_code = code
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
            f.write(wrapper_code)
            temp_file = f.name
        
        # Compile Java
        compile_result = subprocess.run(
            ['javac', temp_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if compile_result.returncode != 0:
            os.unlink(temp_file)
            return {
                'passed': False,
                'error': f'Compilation error: {compile_result.stderr}'
            }
        
        # Execute Java
        class_file = temp_file.replace('.java', '.class')
        execute_result = subprocess.run(
            ['java', '-cp', os.path.dirname(temp_file), 'Solution'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Clean up
        os.unlink(temp_file)
        if os.path.exists(class_file):
            os.unlink(class_file)
        
        if execute_result.returncode != 0:
            return {
                'passed': False,
                'error': execute_result.stderr
            }
        
        # Compare results
        try:
            expected = ast.literal_eval(test_case['output'])
            actual = ast.literal_eval(execute_result.stdout.strip())
            
            return {
                'passed': expected == actual,
                'expected': test_case['output'],
                'actual': str(actual),
                'input': test_case['input']
            }
            
        except (ValueError, SyntaxError) as e:
            return {
                'passed': False,
                'error': f'Output parsing failed: {e}',
                'expected': test_case['output'],
                'actual': execute_result.stdout.strip(),
                'input': test_case['input']
            }
        
    except subprocess.TimeoutExpired:
        return {'passed': False, 'error': 'Time limit exceeded'}
    except Exception as e:
        return {'passed': False, 'error': str(e)}







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

@login_required
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




import json
import requests
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

OPENROUTER_API_KEY = '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'  # << Secure this key


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
            "HTTP-Referer": "http://localhost:8000",
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
                'quiz_data': []
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








