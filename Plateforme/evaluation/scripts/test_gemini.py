import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

import requests
from scraping.extractors.core.llm_validation import GEMINI_CHAT_URL_TEMPLATE
from urllib.parse import quote_plus
from scraping.api_key_manager import api_key_manager

key = api_key_manager.get_current_key("gemini")
print("Gemini key:", key[:5] + "..." + key[-5:] if key else None)
url = GEMINI_CHAT_URL_TEMPLATE.format(
    model=quote_plus("gemini-2.0-flash"),
    api_key=quote_plus(key),
)
print("URL:", url)

payload = {
    "contents": [{"role": "user", "parts": [{"text": "Say OK"}]}],
    "generationConfig": {"temperature": 0.15, "maxOutputTokens": 1200},
}

resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
print("Status:", resp.status_code)
print("Response:", resp.text)
