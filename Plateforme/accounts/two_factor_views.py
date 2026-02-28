"""
Two-Factor Authentication Views
"""
from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.utils.translation import gettext as _
from .two_factor_utils import generate_otp, store_otp, verify_otp, clear_otp, get_otp_expiry
from .two_factor_email import send_otp_email
from .two_factor_models import TwoFactorAuth
import json

User = get_user_model()

class OTPVerificationView(View):
    """
    OTP Verification for signup (account activation).
    User is redirected here after registration to verify their email.
    """
    template_name = 'account/two_factor_verify.html'

    def get(self, request):
        user_id = request.session.get('pending_2fa_user_id')
        is_signup = request.session.get('pending_2fa_is_signup', False)

        if not user_id:
            if is_signup:
                messages.error(request, _("Session expired. Please sign up again."))
                return redirect('account_signup')
            messages.error(request, _("Invalid request. Please try logging in again."))
            return redirect('account_login')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            messages.error(request, _("User not found. Please try again."))
            return redirect('account_signup' if is_signup else 'account_login')

        expiry_info = get_otp_expiry(user_id)

        context = {
            'user_email': user.email,
            'user_name': user.full_name,
            'remaining_seconds': expiry_info.get('remaining_seconds', 0),
            'is_signup_verification': is_signup,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        user_id = request.session.get('pending_2fa_user_id')
        is_signup = request.session.get('pending_2fa_is_signup', False)

        if not user_id:
            return JsonResponse({'success': False, 'message': _('Session expired. Please try again.')})

        otp_code = request.POST.get('otp_code', '').strip()

        if not otp_code:
            return JsonResponse({'success': False, 'message': _('Please enter the verification code.')})

        result = verify_otp(user_id, otp_code)

        if result['valid']:
            try:
                user = User.objects.get(id=user_id)

                # Activate account if this is signup verification
                if is_signup:
                    user.is_active = True
                    if hasattr(user, 'is_verified'):
                        user.is_verified = True
                    if hasattr(user, 'status'):
                        user.status = 'active'
                    user.save()

                remember = request.session.get('pending_2fa_remember', False)

                # Clear all 2FA session keys before login
                for key in ['pending_2fa_user_id', 'pending_2fa_remember', 'pending_2fa_is_signup']:
                    request.session.pop(key, None)
                request.session.save()

                # Log user in
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                if remember:
                    request.session.set_expiry(None)
                else:
                    request.session.set_expiry(0)

                if is_signup:
                    messages.success(request, _("Account verified successfully! Welcome!"))
                else:
                    messages.success(request, _("Two-factor authentication successful!"))
                return JsonResponse({'success': True, 'redirect_url': '/'})

            except User.DoesNotExist:
                return JsonResponse({'success': False, 'message': _('User not found.')})
        else:
            return JsonResponse({'success': False, 'message': result['message']})


class ResendOTPView(View):
    """
    Resend OTP if user didn't receive it or it expired
    """
    def post(self, request):
        user_id = request.session.get('pending_2fa_user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'message': 'Session expired.'})
        
        try:
            user = User.objects.get(id=user_id)
            
            # Generate new OTP
            otp_code = generate_otp()
            
            # Store in Redis
            store_otp(user_id, otp_code)
            
            # Send email
            email_sent = send_otp_email(user.email, user.full_name, otp_code)
            
            if email_sent:
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Security code resent to {user.email}'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Failed to send email. Please try again.'
                })
        
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'User not found.'})


@method_decorator(login_required, name='dispatch')
class TwoFactorSettingsView(View):
    """
    Allow user to enable/disable 2FA
    """
    template_name = 'account/two_factor_settings.html'
    
    def get(self, request):
        user = request.user
        
        try:
            two_fa = TwoFactorAuth.objects.get(user=user)
        except TwoFactorAuth.DoesNotExist:
            two_fa = TwoFactorAuth.objects.create(user=user)
        
        backup_codes = []
        if two_fa.backup_codes:
            try:
                backup_codes = json.loads(two_fa.backup_codes) if isinstance(two_fa.backup_codes, str) else two_fa.backup_codes
            except (json.JSONDecodeError, TypeError):
                backup_codes = []
        
        context = {
            'is_2fa_enabled': two_fa.is_enabled,
            'backup_codes': backup_codes,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        user = request.user
        
        try:
            two_fa = TwoFactorAuth.objects.get(user=user)
        except TwoFactorAuth.DoesNotExist:
            two_fa = TwoFactorAuth.objects.create(user=user)
        
        # Get the toggle value from form
        two_factor_enabled = request.POST.get('two_factor_enabled') == 'on'
        
        # Update the setting
        two_fa.is_enabled = two_factor_enabled
        two_fa.save()
        
        # Return JSON response for AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if two_factor_enabled:
                message = "✅ Two-factor authentication has been enabled!"
            else:
                message = "✅ Two-factor authentication has been disabled!"
            
            return JsonResponse({
                'success': True,
                'message': message,
                'is_enabled': two_fa.is_enabled
            })
        
        # Fallback redirect for non-AJAX requests
        if two_factor_enabled:
            messages.success(request, "✅ Two-factor authentication enabled!")
        else:
            messages.success(request, "✅ Two-factor authentication disabled!")
        
        return redirect('accounts:two_factor_settings')
