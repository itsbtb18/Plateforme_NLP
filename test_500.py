import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from django.test import Client
import traceback

c = Client()
try:
    response = c.get("/en/publications/1")
    if response.status_code == 500:
        print("STATUS 500")
        print(response.content.decode('utf-8'))
    else:
        print("STATUS", response.status_code)
except Exception as e:
    traceback.print_exc()
