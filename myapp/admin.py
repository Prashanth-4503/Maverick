from django.contrib import admin
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
    list_display = ('id', 'title', 'difficulty', 'acceptance_percentage', 'total_submissions', 'accepted_submissions', 'is_active', 'created_at')
    list_filter = ('difficulty', 'is_active')
    search_fields = ('title', 'tags')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CodeSubmission)
class CodeSubmissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'problem', 'language', 'status', 'execution_time', 'memory_used', 'submitted_at')
    list_filter = ('status', 'language')
    search_fields = ('user__username', 'problem__title')
    readonly_fields = ('submitted_at',)


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