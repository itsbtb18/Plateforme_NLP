from google import genai
import os


key = os.environ.get("GENAI_API_KEY", "")
if not key:
    raise RuntimeError("GENAI_API_KEY is required")

client = genai.Client(api_key=key)

try:
    res = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="hello",
    )
    print("1.5-flash SUCCESS:", res.text)
except Exception as e:
    print("1.5-flash FAILED:", str(e))

try:
    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="hello",
    )
    print("2.5-flash SUCCESS:", res.text)
except Exception as e:
    print("2.5-flash FAILED:", str(e))
