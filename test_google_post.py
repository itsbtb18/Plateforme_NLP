import requests
text = "1. Gateway & Orchestration (Le Cerveau Opérationnel)\nDjango UI & FastAPI Gateway: L'utilisateur interagit avec Django."
url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=fr&tl=ar&dt=t"
try:
    r = requests.post(url, data={"q": text}, timeout=10)
    print("STATUS", r.status_code)
    if r.ok:
        print("".join(str(x[0]) for x in r.json()[0] if x[0]))
    else:
        print("FAILED", r.text)
except Exception as e:
    print("EXCEPTION", e)
