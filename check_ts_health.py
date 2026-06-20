import requests
try:
    # Try localhost first (since I'm on host)
    r = requests.get("http://localhost:8010/health", timeout=5)
    print("LOCALHOST HEALTH:", r.status_code, r.json())
except Exception as e:
    print("LOCALHOST HEALTH ERROR:", e)
