from django.urls import path
from .views import (
    SignUp, LoginView, ProfileView, ProfileEditView,
    InviteToProjectView, RespondToProjectInviteView,
    awaiting_verification_view, delete_account, custom_logout,
    NetworkInvitationsView, friendship_action, blocked_users_api, invitations_count_api,
    set_online_visibility_api, follow_user, unfollow_user, follow_list_api, remove_follower,
    TrashBinView, trash_restore_item, trash_delete_item,
    ExperienceCreateView, ExperienceUpdateView, ExperienceDeleteView,
)
<<<<<<< HEAD
=======
from .cv_extraction_proxy import extract_cv_signup, transliterate_name_ar
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
from .two_factor_views import (
    OTPVerificationView,
    ResendOTPView,
    CancelTwoFactorView,
    TwoFactorSettingsView,
    backup_codes_regenerate,
)


app_name = 'accounts'
urlpatterns = [
    path('signup/', SignUp.as_view(), name='signup'),
<<<<<<< HEAD
=======
    path('extract-cv/', extract_cv_signup, name='extract_cv_signup'),  # CV extraction proxy
    path('transliterate-name-ar/', transliterate_name_ar, name='transliterate_name_ar'),
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
    path('login/', LoginView.as_view(), name='account_login'),
    path('profile/<uuid:pk>/', ProfileView.as_view(), name='profile'),
    path('profile/<uuid:pk>/edit/', ProfileEditView.as_view(), name='profile-edit'),
    path('profile/experience/add/', ExperienceCreateView.as_view(), name='experience_add'),
    path('profile/experience/<int:pk>/edit/', ExperienceUpdateView.as_view(), name='experience_edit'),
    path('profile/experience/<int:pk>/delete/', ExperienceDeleteView.as_view(), name='experience_delete'),
    path('network/invitations/', NetworkInvitationsView.as_view(), name='network_invitations'),
    path('network/invitations/count/', invitations_count_api, name='invitations_count_api'),
    path('network/online-visibility/', set_online_visibility_api, name='set_online_visibility_api'),
    path('network/blocked/', blocked_users_api, name='blocked_users_api'),
    path('network/<uuid:user_id>/<str:action>/', friendship_action, name='friendship_action'),
    path('network/follow/<uuid:user_id>/', follow_user, name='follow_user'),
    path('network/unfollow/<uuid:user_id>/', unfollow_user, name='unfollow_user'),
    path('network/follow-list/<uuid:user_id>/', follow_list_api, name='follow_list_api'),
    path('network/remove-follower/<uuid:user_id>/', remove_follower, name='remove_follower'),
    path('profile/<uuid:pk>/invite/', InviteToProjectView.as_view(), name='invite_to_project'),
    path('trash/', TrashBinView.as_view(), name='trash'),
    path('trash/<str:content_type>/<uuid:pk>/restore/', trash_restore_item, name='trash_restore'),
    path('trash/<str:content_type>/<uuid:pk>/delete/', trash_delete_item, name='trash_delete'),
    path('project/<uuid:project_id>/respond-invite/', RespondToProjectInviteView.as_view(), name='respond_project_invite'),
    # path('my-content/', my_content_view, name='my_content'),  # TODO: Fix import issue
    path('awaiting-verification/', awaiting_verification_view, name='awaiting_verification'),
    path('delete-account/', delete_account, name='delete_account'),
    path('logout/', custom_logout, name='account_logout'),

    # Two-Factor Authentication
    path('verify-2fa/', OTPVerificationView.as_view(), name='verify_2fa'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('cancel-2fa/', CancelTwoFactorView.as_view(), name='cancel_2fa'),
    path('2fa-settings/', TwoFactorSettingsView.as_view(), name='two_factor_settings'),
    path('2fa-settings/backup-codes/regenerate/', backup_codes_regenerate, name='backup_codes_regenerate'),
]
