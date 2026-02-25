"""
Core application URL configuration.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Pending Content Dashboard (Staff only)
    path('pending-content/', views.pending_content_dashboard, name='pending_content_dashboard'),
    
    # Bulk Actions (AJAX endpoints)
    path('bulk-approve/', views.bulk_approve_content, name='bulk_approve_content'),
    path('bulk-reject/', views.bulk_reject_content, name='bulk_reject_content'),
]
