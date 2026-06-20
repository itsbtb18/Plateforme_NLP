import os

import requests

key = os.environ.get("GEMINI_SCRAPING_API_KEY", "").strip()
if not key:
    raise SystemExit("Missing GEMINI_SCRAPING_API_KEY in environment")

model = "gemini-1.5-flash"
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

payload = {"contents": [{"role": "user", "parts": [{"text": "Hello"}]}]}
print(f"Testing URL: {url}")
try:
    resp = requests.post(
        url, json=payload, headers={"Content-Type": "application/json"}
    )
    print("Status:", resp.status_code)
    print("Response:", resp.text)
except Exception as e:
    print(e)
