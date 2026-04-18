import os
import time

import requests

keys = [
    ("GEMINI_SCRAPING_API_KEY", os.environ.get("GEMINI_SCRAPING_API_KEY", "").strip()),
    ("GEMINI_INTERNAL_API_KEY", os.environ.get("GEMINI_INTERNAL_API_KEY", "").strip()),
    ("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "").strip()),
]

models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-8b"]

for name, key in keys:
    if not key:
        print(f"\n{'=' * 50}")
        print(f"Skipping {name}: missing environment variable")
        continue

    print(f"\n{'=' * 50}")
    print(f"Testing {name} ({key[:12]}...):")
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            status = resp.status_code
            if status == 200:
                print(f"  {model}: ✅ OK")
            elif status == 429:
                print(f"  {model}: ❌ 429 Quota exceeded")
            elif status == 400:
                print(f"  {model}: ❌ 400 Bad Request")
            else:
                print(f"  {model}: ❌ {status}")
        except Exception as e:
            print(f"  {model}: ❌ {e}")
        time.sleep(0.5)
