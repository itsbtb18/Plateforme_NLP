import os
import requests
import json

keys = os.environ.get("GROQ_API_KEYS", "").split(",")
for i, key in enumerate(keys):
    key = key.strip()
    if not key: continue
    print(f"Testing key {i} ({key[:10]}...): ", end="")
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "hi"}]},
            timeout=10
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("  OK")
        else:
            print(f"  Error: {resp.text}")
    except Exception as e:
        print(f"  Exception: {e}")
