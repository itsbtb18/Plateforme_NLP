#!/usr/bin/env python3
"""
Create or update a Django superuser non-interactively.

Run from the repository root:
    python Plateforme/create_admin.py

The script prints the created admin credentials.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
import django

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Configuration (can be overridden via env vars)
EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable must be set")
FULL_NAME_EN = os.environ.get("ADMIN_FULL_NAME_EN", "Administrator")
FULL_NAME_AR = os.environ.get("ADMIN_FULL_NAME_AR", "مدير")


def ensure_superuser():
    try:
        user = User.objects.filter(email=EMAIL).first()
        if not user:
            # Use manager.create_superuser to satisfy required fields
            User.objects.create_superuser(
                email=EMAIL,
                password=PASSWORD,
                full_name_en=FULL_NAME_EN,
                full_name_ar=FULL_NAME_AR,
            )
            print("Superuser created:")
        else:
            # Update existing user to ensure superuser flags and password
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.is_email_verified = True
            # Ensure bilingual names exist
            if not getattr(user, "full_name_en", None):
                user.full_name_en = FULL_NAME_EN
            if not getattr(user, "full_name_ar", None):
                user.full_name_ar = FULL_NAME_AR
            user.set_password(PASSWORD)
            user.save()
            print("Superuser updated:")

        print(f"email: {EMAIL}")
        print(f"password: {PASSWORD}")
    except Exception as e:
        print("Failed to create/update superuser:", e)
        raise


if __name__ == "__main__":
    ensure_superuser()
