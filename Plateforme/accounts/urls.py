from django.urls import path
from .views import (
    SignUp, LoginView, ProfileView, ProfileEditView,
    InviteToProjectView, RespondToProjectInviteView,
    awaiting_verification_view, delete_account, custom_logout
)
from .two_factor_views import OTPVerificationView, ResendOTPView, TwoFactorSettingsView


app_name = 'accounts'
urlpatterns = [
    path('signup/', SignUp.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='account_login'),
    path('profile/<uuid:pk>/', ProfileView.as_view(), name='profile'),
    path('profile/<uuid:pk>/edit/', ProfileEditView.as_view(), name='profile-edit'),
    path('profile/<uuid:pk>/invite/', InviteToProjectView.as_view(), name='invite_to_project'),
    path('project/<uuid:project_id>/respond-invite/', RespondToProjectInviteView.as_view(), name='respond_project_invite'),
    path('awaiting-verification/', awaiting_verification_view, name='awaiting_verification'),
    path('delete-account/', delete_account, name='delete_account'),
    path('logout/', custom_logout, name='account_logout'),

    # Two-Factor Authentication
    path('verify-2fa/', OTPVerificationView.as_view(), name='verify_2fa'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('2fa-settings/', TwoFactorSettingsView.as_view(), name='two_factor_settings'),
]
