import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = 'admin'
email = 'admin@example.com'
password = 'Admin@123456'

try:
    if User.objects.filter(username=username).exists():
        User.objects.filter(username=username).delete()
    
    # Try creating with username, email, password
    try:
        user = User.objects.create_superuser(username=username, email=email, password=password)
        print("Success: Superuser created")
    except TypeError as e:
        # If it fails, maybe username is not accepted, try email only
        print(f"Failed with username, trying email only. Error: {e}")
        user = User.objects.create_superuser(email=email, password=password)
        print("Success: Superuser created with email")
except Exception as e:
    print(f"Error: {e}")
