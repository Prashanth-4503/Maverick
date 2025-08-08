from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, UserProfile, Module, ModuleContent,
    QuizAttemptLearningPath, QuizUserAnswer,
    AssignmentSubmission, ModuleCompletion, LearningPath, ProgressNode,
    Hackathon, HackathonTeam, HackathonRegistration, HackathonSubmission, HackathonEvaluation,
    Leaderboard, Assessment,
    Competency, Question, Answer, UserCompetency, QuizSettings, QuizAttempt, QuizResponse,
    QuizAssessment,
    CodingProblem, CodeSubmission,
)



import json
def json_prettify(json_data):
    """Pretty print JSON data with proper formatting"""
    if not json_data:
        return "No data"
    try:
        formatted = json.dumps(json_data, indent=2, sort_keys=True)
        return mark_safe(f'<pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; overflow-x: auto; color: #000;">{formatted}</pre>')
    except:
        return str(json_data)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_admin', 'is_superuser', 'total_xp')
    list_filter = ('is_staff', 'is_admin', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('username',)
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('profile_picture', 'bio', 'total_xp', 'is_admin')}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience_level', 'created_at', 'updated_at')
    search_fields = ('user__username', 'skills', 'experience_level')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'difficulty', 'estimated_time', 'xp_reward', 'created_at')
    list_filter = ('difficulty',)
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(ModuleContent)
class ModuleContentAdmin(admin.ModelAdmin):
    list_display = ('module', 'title', 'content_type', 'duration_minutes', 'order', 'is_required')
    list_filter = ('content_type', 'is_required')
    search_fields = ('module__name', 'title')
    ordering = ('module', 'order')


@admin.register(QuizAttemptLearningPath)
class QuizAttemptLearningPathAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'score', 'total', 'completed_at')
    list_filter = ('completed_at',)
    search_fields = ('user__username', 'content__title')
    readonly_fields = ('completed_at',)


@admin.register(QuizUserAnswer)
class QuizUserAnswerAdmin(admin.ModelAdmin):
    list_display = ('quiz_attempt', 'question_index', 'selected_answer')
    search_fields = ('quiz_attempt__user__username', 'selected_answer')


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'assignment', 'submitted_at')
    search_fields = ('user__username', 'assignment__title')
    readonly_fields = ('submitted_at',)


@admin.register(ModuleCompletion)
class ModuleCompletionAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'completed_at', 'is_completed')
    list_filter = ('is_completed',)
    search_fields = ('user__username', 'content__title')
    readonly_fields = ('completed_at',)


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'status', 'progress', 'started_at', 'completed_at')
    list_filter = ('status', 'progress')
    search_fields = ('user__username', 'module__name')
    readonly_fields = ('created_at', 'started_at', 'completed_at')


@admin.register(ProgressNode)
class ProgressNodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'step', 'timestamp', 'is_completed', 'detail')
    list_filter = ('is_completed',)
    search_fields = ('user__username', 'step', 'detail')
    readonly_fields = ('timestamp',)


@admin.register(Hackathon)
class HackathonAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'start_date', 'end_date', 'max_participants', 'is_active', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(HackathonTeam)
class HackathonTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'hackathon', 'leader', 'member_count', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'leader__username', 'hackathon__name')
    readonly_fields = ('created_at', 'invite_code')


@admin.register(HackathonRegistration)
class HackathonRegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'hackathon', 'team', 'registered_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'hackathon__name', 'team__name')
    readonly_fields = ('registered_at',)


@admin.register(HackathonSubmission)
class HackathonSubmissionAdmin(admin.ModelAdmin):
    list_display = ('project_title', 'hackathon', 'submitter_name', 'final_score', 'rank', 'is_winner', 'submitted_at')
    list_filter = ('is_winner', 'submitted_at')
    search_fields = ('project_title', 'hackathon__name')
    readonly_fields = ('submitted_at', 'updated_at')


@admin.register(HackathonEvaluation)
class HackathonEvaluationAdmin(admin.ModelAdmin):
    list_display = ('submission', 'evaluator', 'evaluated_at')
    list_filter = ('evaluated_at',)
    search_fields = ('submission__project_title', 'evaluator__username')
    readonly_fields = ('evaluated_at',)


@admin.register(Leaderboard)
class LeaderboardAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'rank', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('user__username',)
    readonly_fields = ('last_updated',)
    ordering = ('-score',)

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'assessment_type', 'score', 'completed', 'timestamp')
    list_filter = ('assessment_type', 'completed')
    search_fields = ('user__username', 'name')
    readonly_fields = ('timestamp',)

@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)

# (And so on for all your remaining admin classes...)
# (QuestionAdmin, AnswerAdmin, etc., ... CodeSubmissionAdmin, CertificateAdmin, ChatConversationAdmin, ...)
# --- The remaining code you provided is included below without changes ---

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('competency', 'difficulty', 'points', 'is_active', 'created_at')
    list_filter = ('competency', 'difficulty', 'is_active')
    search_fields = ('text', 'competency__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'text', 'is_correct', 'order')
    list_filter = ('is_correct',)
    search_fields = ('text', 'question__text')
    ordering = ('question', 'order')

@admin.register(UserCompetency)
class UserCompetencyAdmin(admin.ModelAdmin):
    list_display = ('user', 'competency', 'score', 'best_score', 'attempts_count', 'last_updated')
    list_filter = ('competency',)
    search_fields = ('user__username', 'competency__name')
    readonly_fields = ('last_updated', 'created_at')

@admin.register(QuizSettings)
class QuizSettingsAdmin(admin.ModelAdmin):
    list_display = ('competency', 'time_limit', 'passing_score', 'max_attempts', 'question_count', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('competency__name',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'competency', 'status', 'score', 'start_time', 'end_time')
    list_filter = ('status',)
    search_fields = ('user__username', 'competency__name')
    readonly_fields = ('start_time', 'end_time')

@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ('quiz_attempt', 'question', 'answer', 'is_correct', 'response_time', 'points_earned', 'created_at')
    list_filter = ('is_correct',)
    search_fields = ('quiz_attempt__user__username', 'question__text', 'answer__text')
    readonly_fields = ('created_at',)

@admin.register(QuizAssessment)
class QuizAssessmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'competency', 'current_difficulty', 'score', 'completed', 'created_at', 'completed_at')
    list_filter = ('completed', 'current_difficulty')
    search_fields = ('user__username', 'competency__name')
    readonly_fields = ('created_at', 'completed_at')

@admin.register(CodingProblem)
class CodingProblemAdmin(admin.ModelAdmin):
    list_display = ['id', 'title_display', 'difficulty_display', 'test_cases_count', 'submissions_display', 'acceptance_display', 'is_active']
    list_filter = ['difficulty', 'is_active', 'created_at']
    search_fields = ['title', 'tags', 'description']
    list_editable = ['is_active']
    ordering = ['id']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    def title_display(self, obj):
        url = f"/admin/myapp/codingproblem/{obj.pk}/change/"
        return format_html('<a href="{}" style="color: #0066cc; text-decoration: none; font-weight: bold;">{}</a>', url, obj.title)
    title_display.short_description = 'Title'
    
    def difficulty_display(self, obj):
        colors = {'easy': 'green', 'medium': 'orange', 'hard': 'red'}
        color = colors.get(obj.difficulty, 'gray')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.get_difficulty_display())
    difficulty_display.short_description = 'Difficulty'
    
    def test_cases_count(self, obj):
        count = len(obj.test_cases) if obj.test_cases else 0
        color = 'green' if count > 0 else 'red'
        return format_html('<span style="color: {};">{} cases</span>', color, count)
    test_cases_count.short_description = 'Test Cases'
    
    def submissions_display(self, obj):
        return f"{obj.total_submissions} total"
    submissions_display.short_description = 'Submissions'
    
    def acceptance_display(self, obj):
        try:
            rate = float(obj.acceptance_percentage) if obj.acceptance_percentage is not None else 0.0
            color = 'green' if rate >= 50 else 'orange' if rate >= 25 else 'red'
            return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)
        except (ValueError, TypeError):
            return format_html('<span style="color: gray;">N/A</span>')
    acceptance_display.short_description = 'Acceptance'
    
    fieldsets = (
        ('📋 Basic Information', {'fields': ('title', 'slug', 'difficulty', 'tags', 'is_active')}),
        ('📝 Problem Description', {'fields': ('description', 'constraints')}),
        ('💡 Example', {'fields': ('example_input', 'example_output', 'explanation')}),
        ('⚙️ Function Signature', {'fields': ('function_name', 'function_params_display', 'function_params', 'return_type'), 'classes': ('collapse',)}),
        ('🧪 Test Cases', {'fields': ('test_cases_display', 'test_cases')}),
        ('📊 Statistics', {'fields': ('total_submissions', 'accepted_submissions'), 'classes': ('collapse',)}),
        ('🕒 Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)})
    )
    readonly_fields = ['created_at', 'updated_at', 'test_cases_display', 'function_params_display']
    
    def test_cases_display(self, obj):
        return json_prettify(obj.test_cases)
    test_cases_display.short_description = 'Test Cases (Formatted View)'
    
    def function_params_display(self, obj):
        return json_prettify(obj.function_params)
    function_params_display.short_description = 'Function Parameters (Formatted View)'



from django.contrib import admin
from .models import CodeSubmission

@admin.register(CodeSubmission)
class CodeSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'problem', 'language', 'status', 'execution_time',
        'memory_used', 'submitted_at'
    )
    list_filter = (
        'status', 'language', 'submitted_at', 'problem'
    )
    search_fields = (
        'user__username', 'problem__title', 'code', 'error_message'
    )
    readonly_fields = (
        'submitted_at', 'execution_time', 'memory_used', 'test_results'
    )
    date_hierarchy = 'submitted_at'
    ordering = ('-submitted_at',)
    raw_id_fields = ('user', 'problem')

    # Optionally, you can show (truncated) code in the list. Be careful with long text fields.
    def short_code(self, obj):
        return (obj.code[:75] + '...') if len(obj.code) > 75 else obj.code
    short_code.short_description = 'Code'

    # Similarly, optionally show truncated error message
    def short_error(self, obj):
        return (obj.error_message[:50] + '...') if obj.error_message and len(obj.error_message) > 50 else obj.error_message
    short_error.short_description = 'Error Message'

    # If you want to display these short fields, add 'short_code', 'short_error' to list_display

# If not using @admin.register, you can use:
# admin.site.register(CodeSubmission, CodeSubmissionAdmin)


from django.contrib import admin
from .models import Certificate

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_id', 'user', 'module', 'date_issued', 'is_verified')
    list_filter = ('is_verified', 'date_issued', 'module')
    search_fields = ('certificate_id', 'user__username', 'module__name')
    readonly_fields = ('date_issued', 'certificate_id')
    fieldsets = (
        (None, {
            'fields': ('user', 'module', 'certificate_id', 'is_verified')
        }),
        ('Dates', {
            'fields': ('date_issued',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'module')


from django.contrib import admin
from .models import TempUserRegistration, OTP

@admin.register(TempUserRegistration)
class TempUserRegistrationAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'created_at')
    search_fields = ('email', 'username')

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'code', 'created_at', 'expires_at', 'is_expired_status')
    search_fields = ('email', 'code')

    def is_expired_status(self, obj):
        return obj.is_expired()
    is_expired_status.boolean = True
    is_expired_status.short_description = 'Expired?'




from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile, Resume

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'is_admin', 'is_verified', 'total_xp')
    list_filter = ('is_admin', 'is_verified')
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'profile_picture', 'bio')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_admin', 'is_verified', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('XP System', {'fields': ('total_xp',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'experience_level', 'created_at')
    search_fields = ('user__email', 'user__username')
    raw_id_fields = ('user',)

class ResumeAdmin(admin.ModelAdmin):
    list_display = ('user', 'uploaded_at', 'file_name', 'skills_short')
    list_filter = ('user', 'uploaded_at')
    search_fields = ('user__username', 'extracted_skills')
    readonly_fields = ('uploaded_at', 'updated_at')
    date_hierarchy = 'uploaded_at'
    
    def file_name(self, obj):
        return obj.resume_file.name.split('/')[-1]
    file_name.short_description = 'File Name'
    
    def skills_short(self, obj):
        return obj.extracted_skills[:50] + '...' if obj.extracted_skills and len(obj.extracted_skills) > 50 else obj.extracted_skills
    skills_short.short_description = 'Extracted Skills'

# admin.site.register(CustomUser, CustomUserAdmin)
# admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Resume, ResumeAdmin)