from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from typing import Any

class CustomUserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> Any:
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(
        self, 
        email: str, 
        password: str, 
        full_name_en: str | None = None,
        full_name_ar: str | None = None,
        **extra_fields: Any
    ) -> Any:
        # Validate required bilingual name fields
        if not full_name_en:
            raise ValueError(_('Superuser must have full_name_en set.'))
        if not full_name_ar:
            raise ValueError(_('Superuser must have full_name_ar set.'))
        
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)
        extra_fields.setdefault('status', 'active')
        
        # Set the bilingual name fields
        extra_fields['full_name_en'] = full_name_en
        extra_fields['full_name_ar'] = full_name_ar
        extra_fields['full_name'] = full_name_en  # Legacy field fallback

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)