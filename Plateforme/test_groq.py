import os
import time

import requests

keys = [
    ("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", "").strip()),
    ("GROQ_INTERNAL_API_KEY", os.environ.get("GROQ_INTERNAL_API_KEY", "").strip()),
    ("GROQ_SCRAPING_API_KEY", os.environ.get("GROQ_SCRAPING_API_KEY", "").strip()),
]

for name, key in keys:
    if not key:
        print(f"Skipping {name}: missing environment variable")
        continue

    print(f"Testing {name}...")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10,
    }

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 429:
        try:
            print(f"Rate limit error: {resp.json()}")
        except:
            print("Could not parse json")

    time.sleep(0.5)
