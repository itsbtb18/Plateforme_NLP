import os
import django
import sys

# Set up Django
sys.path.append('/home/dahmane/dev/Plateforme_NLP/Plateforme')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from django.test import Client
from accounts.models import CustomUser
import json

c = Client()
# Get the user
user = CustomUser.objects.get(email='admin@example.com')
c.force_login(user)

print("Logged in as:", user.email)

def test_query(mode, question):
    print(f"\n--- Testing mode: {mode} ---")
    print(f"Q: {question}")
    
    payload = {
        "mode": mode,
        "question": question
    }
    
    resp = c.post('/en/chatbot/ask/', data=json.dumps(payload), content_type='application/json', HTTP_HOST='localhost')
    
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        print("Response Keys:", list(data.keys()))
        if 'answer' in data:
            print("Answer:", data['answer'][:200] + '...')
        if 'results' in data:
            print("Results:", len(data['results']), "items found.")
        if 'error' in data:
            print("Error:", data['error'])
    except Exception as e:
        print("Error parsing response:", e)
        print("Response text:", resp.content.decode()[:200])

# 1. Platform Guide - Search tool
test_query("platform", "search for a summarization tool")

# 2. Platform Guide - Legal query
test_query("platform", "what is the law about elections")

# 3. Legal Advisor - Legal query
test_query("legal", "what is the law about elections")
