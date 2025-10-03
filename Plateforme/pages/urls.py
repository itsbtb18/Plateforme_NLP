from django.urls import path
from .views import HomePageView
from . import views

app_name = "pages"
urlpatterns = [
  path('', HomePageView.as_view(), name='home'),
# Main admin views
    path('admin/contact', views.contact_view, name='contact'),
    path('admin/', views.admin_contact_list, name='admin_contact_list'),
    path('admin/<int:pk>/', views.admin_contact_detail, name='admin_contact_detail'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/publications/', views.admin_publications, name='admin_publications'),
    path('admin/corpora/', views.admin_corpora, name='admin_corpora'),
    path('admin/tools/', views.admin_tools, name='admin_tools'),
    path('admin/projects/', views.admin_projects, name='admin_projects'),
    path('admin/courses/', views.admin_courses, name='admin_courses'),
    path('admin/forum/', views.admin_forum, name='admin_forum'),
    path('admin/institutions/', views.admin_institutions, name='admin_institutions'),
    path('admin/calls/', views.admin_calls, name='admin_calls'),
    path('admin/statistics/', views.admin_statistics, name='admin_statistics'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
    path('admin/security/', views.admin_security, name='admin_security'),
    
    # User management
     path('admin/users/<uuid:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
     path('admin/users/new/', views.admin_users_new, name='admin_users_new'),
     path('admin/users/<uuid:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),
      path('admin/users/<uuid:user_id>/activate/', views.admin_user_activate, name='admin_user_activate'),
      path('admin/users/<uuid:user_id>/block/', views.admin_user_block, name='admin_user_block'),
     path('admin/users/<uuid:user_id>/history/', views.admin_user_history, name='admin_user_history'),
    path('admin/users/<uuid:user_id>/status/<str:status>/', views.admin_user_status, name='admin_user_status'),
    
    # API endpoints
    path('admin/api/stats/', views.admin_api_stats, name='admin_api_stats'),
    path('admin/api/recent_users/', views.admin_api_recent_users, name='admin_api_recent_users'),
    path('admin/api/recent_content/', views.admin_api_recent_content, name='admin_api_recent_content'),
]
