import requests
text = "The quick brown fox jumps over the lazy dog."
source_language = "en"
target_language = "fr"
url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_language}&tl={target_language}&dt=t"
r = requests.post(url, data={"q": text}, timeout=10)
print("STATUS", r.status_code)
if r.ok:
    print(r.json())
else:
    print(r.text)
