import requests, urllib.parse
text = "The quick brown fox jumps over the lazy dog."
url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q={urllib.parse.quote(text)}"
r = requests.get(url)
print("".join(x[0] for x in r.json()[0]))
