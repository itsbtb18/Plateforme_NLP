import requests
import json
import time

s = requests.Session()

# Login
login_url = "http://localhost:8000/en/accounts/login/"
s.get(login_url)
csrftoken = s.cookies.get('csrftoken', '')
res = s.post(login_url, data={
    "login": "admin@example.com",
    "password": "1008",
    "csrfmiddlewaretoken": csrftoken
}, headers={"Referer": login_url})

print("Login status:", res.status_code)

ask_url = "http://localhost:8000/en/chatbot/ask/"

def test_query(mode, question):
    print(f"\n--- Testing mode: {mode} ---")
    print(f"Q: {question}")
    s.get("http://localhost:8000/en/chatbot/")
    csrf = s.cookies.get('csrftoken', '')
    
    payload = {
        "mode": mode,
        "question": question
    }
    
    resp = s.post(ask_url, json=payload, headers={
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
        "Referer": "http://localhost:8000/en/chatbot/"
    })
    
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
        print("Response Keys:", list(data.keys()))
        if 'answer' in data:
            print("Answer:", data['answer'][:200] + '...')
        if 'results' in data:
            print("Results:", len(data['results']), "items found.")
    except Exception as e:
        print("Error parsing response:", e)
        print("Response text:", resp.text[:200])

# 1. Platform Guide - Search tool
test_query("platform", "search for a summarization tool")

# 2. Platform Guide - Legal query
test_query("platform", "what is the law about elections")

# 3. Legal Advisor - Legal query
test_query("legal", "what is the law about elections")

