"""
Two-Factor Authentication Models
"""
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class TwoFactorAuth(models.Model):
    """
    Stores 2FA settings for each user
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='two_factor_auth')
    is_enabled = models.BooleanField(default=False)
    METHOD_EMAIL_OTP = "email_otp"
    METHOD_TOTP = "totp"
    METHOD_CHOICES = (
        (METHOD_EMAIL_OTP, "Email OTP"),
        (METHOD_TOTP, "TOTP Authenticator"),
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_EMAIL_OTP)
    totp_secret = models.CharField(max_length=64, blank=True)
    
    # For future use: store backup codes
    backup_codes = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Two Factor Authentication"
        verbose_name_plural = "Two Factor Authentications"
    
    def __str__(self):
        return f"2FA for {self.user.full_name}"
