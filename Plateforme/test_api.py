import os

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_SCRAPING_API_KEY", "").strip()
if not GEMINI_API_KEY:
    raise SystemExit("Missing GEMINI_SCRAPING_API_KEY in environment")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

payload = {
    "contents": [{"role": "user", "parts": [{"text": "Hello, world"}]}],
    "generationConfig": {
        "temperature": 0.15,
        "maxOutputTokens": 1200,
    },
}

resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
print(resp.status_code)
print(resp.text)
