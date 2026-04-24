import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Plateforme'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from translate.views import api_translate
from django.test import RequestFactory
import json

rf = RequestFactory()
text = "1. Gateway & Orchestration (Le Cerveau Opérationnel)\nDjango UI & FastAPI Gateway: L'utilisateur interagit avec Django."
data = {"text": text, "source_language": "fr", "target_language": "ar"}
request = rf.post('/api/ts/translate/', data=json.dumps(data), content_type="application/json")

with open('test_django_view_out.txt', 'w', encoding='utf-8') as f:
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(username='testuser')
        request.user = user
        response = api_translate(request)
        f.write(f"STATUS {response.status_code}\n")
        f.write(f"CONTENT {response.content.decode('utf-8')}\n")
    except Exception as e:
        f.write(f"EXCEPTION {e}\n")
