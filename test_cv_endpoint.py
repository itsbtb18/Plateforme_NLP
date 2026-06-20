import requests

url = "http://localhost:8003/extract-cv-sync/"
files = {'file': ('resume.pdf', b'%PDF-1.4\n1 0 obj <</Type/Catalog/Pages 2 0 R>> endobj 2 0 obj <</Type/Pages/Kids [3 0 R]/Count 1>> endobj 3 0 obj <</Type/Page/Parent 2 0 R/MediaBox [0 0 612 792]/Contents 4 0 R/Resources <<>>>> endobj 4 0 obj <</Length 41>> stream\nBT /F1 12 Tf 100 700 Td (John Doe CV NLP Engineer) Tj ET\nendstream endobj xref 0 5 0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000109 00000 n\n0000000216 00000 n\ntrailer <</Size 5/Root 1 0 R>> startxref 309 %%EOF', 'application/pdf')}

try:
    response = requests.post(url, files=files)
    print("Status:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error:", e)
