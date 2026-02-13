#!/usr/bin/env python
import os
import django
from pathlib import Path

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')

# Add the Plateforme directory to the path
project_root = Path(__file__).parent / 'Plateforme'
import sys
sys.path.insert(0, str(project_root.parent))

django.setup()

from django.contrib.auth.models import User

# Check if admin user already exists
if User.objects.filter(username='admin').exists():
    print("✓ Superuser 'admin' already exists")
else:
    # Create superuser
    user = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='Admin@123456'
    )
    print("✓ Superuser 'admin' created successfully!")
    print("\n" + "="*50)
    print("LOGIN CREDENTIALS")
    print("="*50)
    print(f"Username: admin")
    print(f"Password: Admin@123456")
    print(f"Email:    admin@example.com")
    print("="*50)
    print("\nAccess admin panel at: http://localhost:8000/admin/")
