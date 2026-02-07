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
    2FA is DISABLED for login - only used for signup.
    This ensures users can log in normally without 2FA verification.
    """
    logger.info(f"📝 user_logged_in signal fired for: {user.email}")
    # Simply ensure user has a TwoFactorAuth record (for future use)
    TwoFactorAuth.objects.get_or_create(user=user)


@receiver(user_signed_up)
def check_2fa_on_signup(sender, request, user, **kwargs):
    """
    Signal handler called after successful signup (user account created).
    New users have 2FA ENABLED by default for security.
    They will need to verify 2FA code immediately after signup.
    """
    logger.info(f"🚨 user_signed_up signal FIRED FOR SIGNUP: {user.email}")
    
    # Create 2FA record with is_enabled=True by default
    two_fa, created = TwoFactorAuth.objects.get_or_create(
        user=user,
        defaults={'is_enabled': True}  # 2FA ENABLED for all new signups
    )
    
    if created:
        # Trigger 2FA flow for new signup
        logger.info(f"🔐 Triggering 2FA flow for new user: {user.email}")
        trigger_2fa_flow(request, user)
        logger.info(f"✅ New user signed up with 2FA: {user.email}")
    else:
        logger.info(f"⚠️ User already exists: {user.email}")


class TwoFactorAuthenticationMiddleware:
    """
    Middleware to redirect users to 2FA verification if needed.
    This intercepts requests from users with pending 2FA.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that should not be blocked for 2FA verification
        self.exempt_paths = [
            '/',
            '/accounts/verify-2fa/',
            '/accounts/resend-otp/',
            '/accounts/logout/',
            '/api/',
            '/admin/',
            '/static/',
            '/media/',
        ]
    
    def __call__(self, request):
        # Check if user has pending 2FA verification
        pending_user_id = request.session.get('pending_2fa_user_id')
        
        # Only redirect to 2FA if:
        # 1. User has pending_2fa_user_id in session AND
        # 2. Current path is not exempt
        if pending_user_id:
            # Check if current path is exempt from 2FA check
            is_exempt = False
            
            for path in self.exempt_paths:
                if path == '/':
                    # Only match exact root path, not all paths starting with /
                    is_exempt = request.path == '/'
                else:
                    # For other paths, use startswith
                    is_exempt = request.path.startswith(path)
                
                if is_exempt:
                    break
            
            if not is_exempt:
                # Redirect to 2FA verification
                return redirect('accounts:verify_2fa')
        
        response = self.get_response(request)
        return response
