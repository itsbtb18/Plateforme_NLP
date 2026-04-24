import os, sys, django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Plateforme'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from translate.views import api_translate
from django.test import RequestFactory
import json
import traceback

rf = RequestFactory()
text = "Bonjour le monde"
data = {"text": text, "source_language": "fr", "target_language": "ar"}
request = rf.post('/api/ts/translate/', data=json.dumps(data), content_type="application/json")

from django.contrib.auth import get_user_model
User = get_user_model()
user, _ = User.objects.get_or_create(username='testuser')
request.user = user

try:
    response = api_translate(request)
    print("STATUS", response.status_code)
    print("CONTENT", response.content.decode('utf-8'))
except Exception:
    traceback.print_exc()
