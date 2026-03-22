import json
import uuid

import requests

BASE = "http://localhost:8001"


def new_session():
    uid = str(uuid.uuid4())
    r = requests.post(
        f"{BASE}/sessions",
        params={"user_id": uid, "user_country": "DZ", "user_city": "Algiers"},
        timeout=30,
    )
    r.raise_for_status()
    return uid, r.json()["session_id"]


def run_case(label, question):
    uid, sid = new_session()
    payload = {
        "question": question,
        "session_id": sid,
        "user_id": uid,
        "user_country": "DZ",
        "user_city": "Algiers",
        "max_history": 20,
        "max_tokens": 1024,
    }
    r = requests.post(f"{BASE}/conversation", json=payload, timeout=75)
    out = {"label": label, "status": r.status_code}
    if not r.ok:
        out["error"] = r.text[:400]
        return out

    d = r.json()
    docs = d.get("retrieved_docs") or []
    out.update(
        {
            "source": d.get("source"),
            "answer_lang": d.get("lang"),
            "retrieved_count": len(docs),
            "platform_results_count": len(d.get("platform_results") or []),
            "answer_preview": (d.get("answer") or "").replace("\n", " ")[:180],
        }
    )
    if docs:
        fd = docs[0]
        out["first_doc_source"] = fd.get("source")
        out["first_doc_language"] = fd.get("language")
        out["first_doc_title"] = (fd.get("title") or "")[:120]

    return out


cases = [
    ("platform_tool_query", "Is there any summarization tool in the platform?"),
    (
        "platform_resources_query",
        "Suggest any resources from the platform for NLP beginners.",
    ),
    ("legal_ar_query", "ما هي الشروط القانونية لمناقشة الدكتوراه حسب التنظيم الجامعي؟"),
    ("nlp_ar_query", "اشرح بنية Transformer في معالجة اللغة الطبيعية."),
    ("cross_lang_legal_ar", "ما هي إجراءات تغيير مشرف الأطروحة إذا توفي المشرف؟"),
]

results = [run_case(*c) for c in cases]

legal_payload = {
    "question": "ما هي شروط مناقشة الدكتوراه؟",
    "language": "ar",
    "jurisdiction": None,
    "category": None,
}
rl = requests.post(f"{BASE}/legal_search", json=legal_payload, timeout=75)
legal = {"label": "legal_search_ar", "status": rl.status_code}
if rl.ok:
    d = rl.json()
    docs = d.get("retrieved_docs") or []
    legal["source"] = d.get("source")
    legal["answer_lang"] = d.get("lang")
    legal["retrieved_count"] = len(docs)
    legal["answer_preview"] = (d.get("answer") or "").replace("\n", " ")[:180]
    if docs:
        fd = docs[0]
        legal["first_doc_source"] = fd.get("source")
        legal["first_doc_language"] = fd.get("language")
        legal["first_doc_title"] = (fd.get("title") or "")[:120]
else:
    legal["error"] = rl.text[:400]

print(json.dumps({"conversation_tests": results, "legal_search_test": legal}, ensure_ascii=False, indent=2))
