from django.urls import path
from . import views

urlpatterns = [
    # Public landing & auth
    path('', views.index, name='index'),
    path('register/', views.user_register, name='user_register'),
    path('login/user/', views.user_login, name='user_login'),
    path('login/admin/', views.admin_login, name='admin_login'),
    path('login/police/', views.police_login, name='police_login'),
    path('logout/', views.logout_view, name='logout'),

    # =========== ADMIN ===========
    path('admin/home/', views.admin_home, name='admin_home'),
    path('admin/police/add/', views.admin_add_police, name='admin_add_police'),
    path('admin/police/view/', views.admin_view_police, name='admin_view_police'),
    path('admin/police/edit/<int:pk>/', views.admin_edit_police, name='admin_edit_police'),
    path('admin/police/delete/<int:pk>/', views.admin_delete_police, name='admin_delete_police'),
    path('admin/requests/', views.admin_requests, name='admin_requests'),
    path('admin/requests/analyze/<int:pk>/', views.admin_analyze_request, name='admin_analyze_request'),
    path('admin/complaints/', views.admin_complaints, name='admin_complaints'),
    path('admin/complaints/reply/<int:pk>/', views.admin_complaint_reply, name='admin_complaint_reply'),
    path('admin/verify-id/', views.admin_verify_id, name='admin_verify_id'),

    # =========== POLICE ===========
    path('police/home/', views.police_home, name='police_home'),
    path('police/verify-id/', views.police_verify_id, name='police_verify_id'),
    path('police/pending/', views.police_pending, name='police_pending'),
    path('police/analyze/<int:pk>/', views.police_analyze, name='police_analyze'),
    path('police/report/<int:pk>/', views.police_report_pdf, name='police_report_pdf'),

    # =========== USER ===========
    path('user/home/', views.user_home, name='user_home'),
    path('user/post-id/', views.user_post_id, name='user_post_id'),
    path('user/my-requests/', views.user_my_requests, name='user_my_requests'),
    path('user/download/<int:pk>/', views.user_download_result, name='user_download_result'),
    path('user/complaint/', views.user_complaint, name='user_complaint'),
    path('user/my-complaints/', views.user_my_complaints, name='user_my_complaints'),
]
