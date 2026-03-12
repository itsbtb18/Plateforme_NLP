#!/usr/bin/env python
"""
Initialize settings app - run migrations and create default settings
Usage: python manage.py shell < settings/initialize.py
OR: python initialize_settings.py
"""
import os
import django

# Setup Django if running standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from django.core.management import call_command
from settings.models import GlobalSettings

print("=" * 60)
print("Initializing Settings App")
print("=" * 60)

# Run migrations
print("\n[1/2] Running migrations...")
try:
    call_command('migrate', 'settings')
    print("✓ Migrations completed successfully")
except Exception as e:
    print(f"✗ Migration failed: {e}")
    exit(1)

# Create default settings if they don't exist
print("\n[2/2] Creating default Global Settings...")
try:
    settings, created = GlobalSettings.objects.get_or_create(pk=1)
    if created:
        settings.save()
        print("✓ Default Global Settings created successfully")
        print(f"   Site Name: {settings.site_name}")
        print(f"   Site URL: {settings.site_url}")
    else:
        print("✓ Global Settings already exist")
        print(f"   Site Name: {settings.site_name}")
        print(f"   Site URL: {settings.site_url}")
except Exception as e:
    print(f"✗ Failed to create settings: {e}")
    exit(1)

print("\n" + "=" * 60)
print("✓ Settings app initialization complete!")
print("=" * 60)
print("\nYou can now access the Global Settings in the Django admin.")
print("Built-in features:")
print("  - Platform configuration (name, URL, branding)")
print("  - Email settings")
print("  - Notification controls")
print("  - Feature flags")
print("  - Maintenance mode")
print("\nNext: Run 'python manage.py runserver' and visit /admin/")
