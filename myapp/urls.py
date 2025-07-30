
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
     path('register/', views.register_view, name='register'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
#     path('', views.home, name='home'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    # User Views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('assessment/', views.assessment_view, name='assessment'),
    
    # Learning Path
    path('learning-path/', views.learning_path_view, name='learning_path'),
    path('learning-path/add/<int:module_id>/', views.add_to_path, name='add_to_path'),
    
    path('module/<int:module_id>/continue/', views.continue_module, name='continue_module'),
    path('module/<int:module_id>/review/', views.review_module, name='review_module'),
    path('module/<int:module_id>/remove/', views.remove_from_path, name='remove_from_path'),
    path('module/<int:module_id>/', views.module_detail, name='module_detail'),
    path('content/<int:content_id>/', views.content_detail, name='content_detail'),
    path('modules/', views.module_list, name='module_list'),
    path('start-module/<int:module_id>/', views.start_module, name='start_module'),


    path('modules/', views.module_list_view, name='module_list'),
    path('refresh-recommendations/', views.refresh_recommendations, name='refresh_recommendations'),
    path('module/<int:module_id>/', views.module_detail, name='module_detail'),
    path('module/<int:module_id>/continue/', views.continue_module_view, name='continue_module'),
    path('module/<int:module_id>/start/', views.module_start, name='module_start'),
    path('module/<int:module_id>/review/', views.module_review, name='module_review'),
    path('module/<int:module_id>/content/', views.module_content, name='module_content'),
    path('content/<int:content_id>/toggle/', views.toggle_content_completion, name='toggle_content_completion'),
    
    # Quiz URLs (ASSESSMENT AND QUIZ SYSTEM)
    path('quiz/start/<int:competency_id>/', views.start_quiz, name='start_quiz'),
    path('quiz/attempt/<int:attempt_id>/', views.take_quiz, name='take_quiz'),
    path('quiz/attempt/<int:attempt_id>/submit/', views.submit_answer, name='submit_answer'),
    path('quiz/attempt/<int:attempt_id>/results/', views.quiz_results, name='quiz_results'),
    
   # Enhanced Hackathon URLs
    path('hackathon/', views.hackathon_view, name='hackathon'),
    path('hackathon/create/', views.create_hackathon, name='create_hackathon'),
    path('hackathon/<int:hackathon_id>/', views.hackathon_detail, name='hackathon_detail'),
    path('hackathon/<int:hackathon_id>/register/', views.register_hackathon, name='register_hackathon'),
    path('hackathon/<int:hackathon_id>/team/', views.manage_team, name='manage_team'),
    path('hackathon/<int:hackathon_id>/submit/', views.submit_hackathon_project, name='submit_hackathon_project'),
    path('hackathon/<int:hackathon_id>/results/', views.hackathon_results, name='hackathon_results'),

    # Admin hackathon URLs
    path('admin/hackathon/', views.admin_hackathon_management, name='admin_hackathon_management'),
    path('admin/hackathon/<int:hackathon_id>/evaluate/', views.evaluate_submissions, name='evaluate_submissions'),
    path('admin/hackathon/<int:hackathon_id>/winners/', views.select_winners, name='select_winners'),

    
    # Admin
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/hackathon/', views.admin_hackathon_management, name='admin_hackathon_management'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),


           # Coding problems
    path('problems/', views.problem_list, name='problem_list'),
    path('problems/<int:problem_id>/', views.problem_detail, name='problem_detail'),
    path('api/submit-code/', views.submit_code, name='submit_code'),






     path('content/<int:content_id>/mark_as_read/', views.mark_content_as_read, name='mark_content_as_read'),

 path('module/<int:module_id>/complete/', views.complete_module, name='complete_module'),







        path('content/<int:content_id>/submit_quiz/', views.submit_quiz, name='submit_quiz'),
        path('content/<int:content_id>/submit_quiz_form/', views.submit_quiz_form, name='submit_quiz_form'),
        path('content/<int:content_id>/submit_assignment/', views.submit_assignment, name='submit_assignment'),




         # ... existing URLs ...
path('module/<int:module_id>/certificate/generate/', 
         views.generate_certificate, 
         name='generate_certificate'),
    path('module/<int:module_id>/certificate/', 
         views.view_certificate, 
         name='view_certificate'),
    path('certificates/verify/<str:certificate_id>/', 
         views.verify_certificate, 
         name='verify_certificate'),

    path('quiz/', views.quiz_view, name='quiz'),
    path('quiz/generate/', views.generate_quiz, name='generate_quiz'),
    
]



