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
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _
from .two_factor_utils import (
    OTPLockedOut,
    generate_backup_codes,
    generate_otp,
    get_otp_expiry,
    setup_totp,
    store_otp,
    verify_totp,
    verify_otp,
)
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

        two_fa = TwoFactorAuth.objects.filter(user=user).first()
        method = two_fa.method if two_fa else TwoFactorAuth.METHOD_EMAIL_OTP
        expiry_info = get_otp_expiry(user_id) if method == TwoFactorAuth.METHOD_EMAIL_OTP else {"remaining_seconds": 0}

        context = {
            'user_email': user.email,
            'user_name': user.full_name,
            'remaining_seconds': expiry_info.get('remaining_seconds', 0),
            'is_signup_verification': is_signup,
            'two_factor_method': method,
            'is_totp_method': method == TwoFactorAuth.METHOD_TOTP,
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

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': _('User not found.')})

        two_fa = TwoFactorAuth.objects.filter(user=user).first()
        method = two_fa.method if two_fa else TwoFactorAuth.METHOD_EMAIL_OTP

        try:
            if method == TwoFactorAuth.METHOD_TOTP:
                is_valid = verify_totp(user, otp_code)
                result = {
                    "valid": is_valid,
                    "message": _("Two-factor authentication successful!") if is_valid else _("Invalid authenticator code. Please try again."),
                }
            else:
                result = verify_otp(user_id, otp_code)
        except OTPLockedOut as exc:
            return JsonResponse({'success': False, 'message': str(exc)})

        if result['valid']:
            # Activate account if this is signup verification
            if is_signup:
                user.is_active = True
                if hasattr(user, 'is_verified'):
                    user.is_verified = True
                if hasattr(user, 'status'):
                    user.status = 'active'
                user.save()

            remember = request.session.get('pending_2fa_remember', False)

            # Log user in
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Clear 2FA session keys after successful login
            for key in ['pending_2fa_user_id', 'pending_2fa_remember', 'pending_2fa_is_signup']:
                request.session.pop(key, None)
            request.session.save()

            if remember:
                request.session.set_expiry(None)
            else:
                request.session.set_expiry(0)

            if is_signup:
                messages.success(request, _("Account verified successfully! Welcome!"))
            else:
                messages.success(request, _("Two-factor authentication successful!"))
            return JsonResponse({'success': True, 'redirect_url': '/'})
        else:
            return JsonResponse({'success': False, 'message': result['message']})


class CancelTwoFactorView(View):
    """
    Cancel 2FA verification flow — clears pending session data
    and redirects to signup or login.
    """
    def get(self, request):
        for key in ['pending_2fa_user_id', 'pending_2fa_is_signup', 'pending_2fa_remember']:
            request.session.pop(key, None)
        request.session.save()
        dest = request.GET.get('next', '')
        if dest == 'signup':
            return redirect('account_signup')
        if dest == 'home':
            return redirect('pages:home')
        return redirect('account_login')


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
            two_fa = TwoFactorAuth.objects.filter(user=user).first()
            if two_fa and two_fa.method == TwoFactorAuth.METHOD_TOTP:
                return JsonResponse({
                    'success': False,
                    'message': _('Authenticator app is enabled. Use the code from your app.')
                })
            
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
        
        two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)
        
        backup_codes = []
        if two_fa.backup_codes:
            try:
                backup_codes = (
                    json.loads(two_fa.backup_codes)
                    if isinstance(two_fa.backup_codes, str)
                    else two_fa.backup_codes
                )
            except (json.JSONDecodeError, TypeError):
                backup_codes = []

        masked_backup_codes = ["****-****" for _ in backup_codes]
        newly_generated_backup_codes = request.session.pop("new_backup_codes", None)
        if request.session.modified:
            request.session.save()

        context = {
            'is_2fa_enabled': two_fa.is_enabled,
            'current_method': two_fa.method,
            'email_otp_method': TwoFactorAuth.METHOD_EMAIL_OTP,
            'totp_method': TwoFactorAuth.METHOD_TOTP,
            'totp_qr_code': request.session.pop("totp_qr_code", None),
            'totp_secret': request.session.pop("totp_secret", None),
            'backup_codes': backup_codes,
            'masked_backup_codes': masked_backup_codes,
            'new_backup_codes': newly_generated_backup_codes or [],
        }
        if request.session.modified:
            request.session.save()
        return render(request, self.template_name, context)
    
    def post(self, request):
        user = request.user
        
        two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)
        action = (request.POST.get("action") or "").strip()

        if action == "switch_totp":
            totp_payload = setup_totp(user)
            two_fa.is_enabled = True
            two_fa.save(update_fields=["is_enabled", "updated_at"])

            request.session["totp_qr_code"] = totp_payload["qr_code_base64"]
            request.session["totp_secret"] = totp_payload["secret"]
            request.session.modified = True

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': _("TOTP method enabled. Scan the QR code with your authenticator app."),
                    'is_enabled': True,
                    'method': TwoFactorAuth.METHOD_TOTP,
                    'totp_qr_code': totp_payload["qr_code_base64"],
                    'totp_secret': totp_payload["secret"],
                    'provisioning_uri': totp_payload["provisioning_uri"],
                })
            return redirect('accounts:two_factor_settings')

        if action == "switch_email":
            two_fa.method = TwoFactorAuth.METHOD_EMAIL_OTP
            two_fa.totp_secret = ""
            two_fa.is_enabled = True
            two_fa.save(update_fields=["method", "totp_secret", "is_enabled", "updated_at"])

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': _("Email OTP method enabled."),
                    'is_enabled': True,
                    'method': TwoFactorAuth.METHOD_EMAIL_OTP,
                })
            messages.success(request, _("Email OTP method enabled."))
            return redirect('accounts:two_factor_settings')
        
        was_enabled = bool(two_fa.is_enabled)

        # Get the toggle value from form
        two_factor_enabled = request.POST.get('two_factor_enabled') == 'on'
        
        # Update the setting
        two_fa.is_enabled = two_factor_enabled
        two_fa.save(update_fields=["is_enabled", "updated_at"])

        generated_codes = []
        if two_factor_enabled and not was_enabled:
            generated_codes = generate_backup_codes(user)
        
        # Return JSON response for AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if two_factor_enabled:
                message = "✅ Two-factor authentication has been enabled!"
            else:
                message = "✅ Two-factor authentication has been disabled!"
            
            return JsonResponse({
                'success': True,
                'message': message,
                'is_enabled': two_fa.is_enabled,
                'backup_codes': generated_codes,
            })
        
        # Fallback redirect for non-AJAX requests
        if two_factor_enabled:
            if generated_codes:
                request.session["new_backup_codes"] = generated_codes
                request.session.modified = True
            messages.success(request, "✅ Two-factor authentication enabled!")
        else:
            messages.success(request, "✅ Two-factor authentication disabled!")
        
        return redirect('accounts:two_factor_settings')


@login_required
@require_POST
def backup_codes_regenerate(request):
    """
    Regenerate all backup codes and return plaintext codes once.
    """
    user = request.user
    two_fa, _ = TwoFactorAuth.objects.get_or_create(user=user)

    if not two_fa.is_enabled:
        return JsonResponse(
            {'success': False, 'message': _('Enable 2FA before regenerating backup codes.')},
            status=400,
        )

    codes = generate_backup_codes(user)
    return JsonResponse({'success': True, 'backup_codes': codes})
