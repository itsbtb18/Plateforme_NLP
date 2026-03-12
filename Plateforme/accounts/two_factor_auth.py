"""
Two-Factor Authentication Integration with Django-Allauth
Provides post-login AND post-signup signals to enable 2FA flow
"""
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.shortcuts import redirect
from allauth.account.signals import user_signed_up
from .two_factor_models import TwoFactorAuth
from .two_factor_utils import generate_otp, store_otp
from .two_factor_email import send_otp_email
import logging

logger = logging.getLogger(__name__)


def trigger_2fa_flow(request, user):
    """
    Common function to trigger 2FA verification flow.
    Used by both login and signup signals.
    """
    try:
        two_fa = TwoFactorAuth.objects.get(user=user)
        
        # If 2FA not enabled, still create the record but with enabled=True for security
        if not two_fa.is_enabled:
            two_fa.is_enabled = True
            two_fa.save()
        
        if two_fa.is_enabled:
            # Generate OTP and store in Redis
            otp_code = generate_otp()
            store_otp(str(user.id), otp_code)
            
            # Send OTP email
            send_otp_email(user.email, user.get_full_name(), otp_code)
            
            # Mark user as pending 2FA verification
            request.session['pending_2fa_user_id'] = str(user.id)
            request.session.modified = True
    
    except TwoFactorAuth.DoesNotExist:
        # Create TwoFactorAuth record if it doesn't exist (ENABLED by default for security)
        two_fa = TwoFactorAuth.objects.create(user=user, is_enabled=True)
        
        # Generate OTP and store in Redis
        otp_code = generate_otp()
        store_otp(str(user.id), otp_code)
        
        # Send OTP email
        send_otp_email(user.email, user.get_full_name(), otp_code)
        
        # Mark user as pending 2FA verification
        request.session['pending_2fa_user_id'] = str(user.id)
        request.session.modified = True
    
    except Exception as e:
        logger.error(f"Error in 2FA trigger: {str(e)}")


@receiver(user_logged_in)
def check_2fa_on_login(sender, request, user, **kwargs):
    """
    Signal handler called after successful login.
    Ensures user has a TwoFactorAuth record.
    No 2FA challenge on login — verification is only required during signup.
    """
    TwoFactorAuth.objects.get_or_create(user=user, defaults={'is_enabled': True})


@receiver(user_signed_up)
def check_2fa_on_signup(sender, request, user, **kwargs):
    """
    Signal handler for allauth's user_signed_up signal.
    Note: Our SignUp view uses Django's CreateView (not allauth), so this signal
    does not fire from normal registration. The 2FA flow is handled directly
    in SignUp.form_valid(). This handler is kept as a safety net only.
    """
    TwoFactorAuth.objects.get_or_create(
        user=user,
        defaults={'is_enabled': True}
    )


class TwoFactorAuthenticationMiddleware:
    """
    Middleware to redirect users to 2FA verification if needed.
    This intercepts requests from users with pending 2FA.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that should not be blocked for 2FA verification
        self.exempt_paths = [
            '/accounts/verify-2fa/',
            '/accounts/resend-otp/',
            '/accounts/cancel-2fa/',
            '/accounts/logout/',
            '/accounts/login/',
            '/accounts/signup/',
            '/api/',
            '/admin/',
            '/static/',
            '/media/',
        ]
    
    def _clear_2fa_session(self, request):
        request.session.pop('pending_2fa_user_id', None)
        request.session.pop('pending_2fa_is_signup', None)
        request.session.pop('pending_2fa_remember', None)
        request.session.modified = True

    def __call__(self, request):
        # Check if user has pending 2FA verification
        pending_user_id = request.session.get('pending_2fa_user_id')
        
        if pending_user_id:
            # Verify the referenced user still exists; clear stale session if not
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(id=pending_user_id).exists():
                self._clear_2fa_session(request)
                pending_user_id = None
        
        if pending_user_id:
            # Strip language prefix (e.g., /en/, /ar/) for path matching
            path = request.path
            import re
            path_no_lang = re.sub(r'^/[a-z]{2}(-[a-z]{2})?/', '/', path)
            
            is_exempt = path == '/' or path_no_lang == '/'
            if not is_exempt:
                for exempt in self.exempt_paths:
                    if path_no_lang.startswith(exempt) or path.startswith(exempt):
                        is_exempt = True
                        break
            
            # If user navigates to login, signup, or home — they're abandoning 2FA
            abandon_paths = ['/accounts/login/', '/accounts/signup/', '/accounts/cancel-2fa/']
            is_abandoning = path == '/' or path_no_lang == '/'
            if not is_abandoning:
                for ap in abandon_paths:
                    if path_no_lang.startswith(ap) or path.startswith(ap):
                        is_abandoning = True
                        break
            if is_abandoning:
                self._clear_2fa_session(request)
            
            if not is_exempt:
                return redirect('accounts:verify_2fa')
        
        response = self.get_response(request)
        return response
