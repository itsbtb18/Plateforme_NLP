#!/usr/bin/env python
"""Run human-eval queries against chatbot with rate limiting and retries.

Input:  evaluation/human_eval/human_eval_queries.json
Output: evaluation/human_eval/human_eval_qa.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://nlp_admin@db:5432/nlp_platform")

CRITERIA = [
    "legal_correctness",
    "completeness",
    "clarity",
    "source_citation",
    "safe_fallback",
]

LANG_HINT = {
    "ar": "ar",
    "fr": "fr",
    "en": "en",
    "mix": None,
}

FALLBACK_MARKERS = (
    "لم أتمكن من إكمال",
    "pas pu compléter la réponse",
    "wasn't able to complete my answer",
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_llm_fallback(answer: str) -> bool:
    txt = (answer or "").strip().lower()
    if not txt:
        return True
    return any(marker.lower() in txt for marker in FALLBACK_MARKERS)


def _extractive_snippet(content: str, max_chars: int = 900) -> str:
    clean = re.sub(r"\s+", " ", (content or "")).strip()
    if len(clean) <= max_chars:
        return clean
    # Prefer sentence boundary near max_chars
    cut = clean.rfind(". ", 0, max_chars)
    if cut >= int(max_chars * 0.55):
        return clean[: cut + 1]
    return clean[: max_chars - 3].rstrip() + "..."


def _missing_chunk_message(lang: str, domain: str, doc_id: Any) -> str:
    if lang == "ar":
        return (
            f"تعذر العثور على المقطع المطلوب (id={doc_id}) في جدول {domain}. "
            "السبب: السجل غير موجود أو تم حذفه، لذلك لا يمكن توليد إجابة معتمدة على قاعدة البيانات."
        )
    if lang == "fr":
        return (
            f"Chunk introuvable (id={doc_id}) dans la table {domain}. "
            "Raison: enregistrement absent ou supprime; impossible de produire une reponse fondee sur la base."
        )
    return (
        f"Requested chunk not found (id={doc_id}) in table {domain}. "
        "Reason: record is missing or deleted, so a database-grounded answer cannot be produced."
    )


async def answer_from_db(
    conn,
    q: dict[str, Any],
) -> dict[str, Any]:
    domain = str(q.get("domain") or "").strip().lower()
    doc_id = q.get("source_document_id")
    lang = str(q.get("query_language") or "en")
    if lang not in {"ar", "fr", "en", "mix"}:
        lang = "en"
    if lang == "mix":
        lang = "en"

    if domain == "legal":
        tbl = "legal_documents"
        title_col = "title"
        source_name = "db_legal"
    else:
        tbl = "nlp_knowledge"
        title_col = "topic"
        source_name = "db_nlp"

    if doc_id is None:
        return {
            "answer": _missing_chunk_message(lang, tbl, "unknown"),
            "source": source_name,
            "lang": lang,
            "session_id": "human_eval_db",
            "retrieved_docs": [],
            "error": None,
        }

    rs = await conn.execute(
        text(
            f"SELECT id, {title_col} AS title, content, language FROM {tbl} WHERE id = :id LIMIT 1"
        ),
        {"id": int(doc_id)},
    )
    row = rs.mappings().first()
    if not row:
        return {
            "answer": _missing_chunk_message(lang, tbl, doc_id),
            "source": source_name,
            "lang": lang,
            "session_id": "human_eval_db",
            "retrieved_docs": [],
            "error": None,
        }

    title = str(row.get("title") or q.get("source_title") or "Untitled")
    content = str(row.get("content") or "")
    snippet = _extractive_snippet(content)

    if lang == "ar":
        prefix = "إجابة مبنية مباشرة على مقطع من قاعدة البيانات"
        body = f"{prefix} ({title}):\n{snippet}"
    elif lang == "fr":
        prefix = "Reponse construite directement depuis un chunk de la base"
        body = f"{prefix} ({title}) :\n{snippet}"
    else:
        prefix = "Answer built directly from a database chunk"
        body = f"{prefix} ({title}):\n{snippet}"

    retrieved = [
        {
            "id": int(row.get("id")),
            "title": title,
            "content": snippet,
            "source": source_name,
            "similarity": 1.0,
        }
    ]
    return {
        "answer": body,
        "source": source_name,
        "lang": lang,
        "session_id": "human_eval_db",
        "retrieved_docs": retrieved,
        "error": None,
    }


async def ask_chatbot_with_retry(
    client: httpx.AsyncClient,
    endpoint: str,
    payload: dict[str, Any],
    max_retries: int,
) -> dict[str, Any]:
    delay = 1.5
    for attempt in range(max_retries + 1):
        try:
            res = await client.post(endpoint, json=payload)
            if res.status_code in (429, 500, 502, 503, 504):
                if attempt >= max_retries:
                    return {
                        "error": f"HTTP {res.status_code}",
                        "raw_response": res.text[:800],
                    }
                await asyncio.sleep(delay + random.uniform(0, 0.7))
                delay = min(delay * 2.0, 20.0)
                continue

            if res.status_code >= 400:
                return {
                    "error": f"HTTP {res.status_code}",
                    "raw_response": res.text[:800],
                }

            data = res.json()
            answer = str(data.get("answer", "") or "")
            if is_llm_fallback(answer):
                if attempt >= max_retries:
                    return {
                        "error": "llm_fallback_response",
                        "answer": answer,
                        "source": data.get("source", "unknown"),
                        "lang": data.get("lang"),
                        "session_id": data.get("session_id"),
                        "retrieved_docs": data.get("retrieved_docs") or [],
                    }
                await asyncio.sleep(delay + random.uniform(0, 0.7))
                delay = min(delay * 2.0, 20.0)
                continue

            return {
                "answer": answer,
                "source": data.get("source", "unknown"),
                "lang": data.get("lang"),
                "session_id": data.get("session_id"),
                "retrieved_docs": data.get("retrieved_docs") or [],
            }
        except Exception as exc:  # noqa: BLE001
            if attempt >= max_retries:
                return {"error": str(exc)}
            await asyncio.sleep(delay + random.uniform(0, 0.7))
            delay = min(delay * 2.0, 20.0)

    return {"error": "unexpected retry exit"}


async def main_async(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)

    queries: list[dict[str, Any]] = load_json(input_path, default=[])
    if not queries:
        raise ValueError(f"No queries found in {input_path}")

    existing: list[dict[str, Any]] = load_json(output_path, default=[])
    by_id = {row.get("id"): row for row in existing if row.get("id")}

    timeout = httpx.Timeout(connect=15.0, read=args.request_timeout, write=15.0, pool=30.0)
    db_url = args.db_url or os.getenv("DATABASE_URL") or DEFAULT_DB_URL
    engine = None
    db_conn = None
    if args.answer_from_db:
        engine = create_async_engine(db_url, future=True)
        db_conn = await engine.connect()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            completed = 0
            for i, q in enumerate(queries, 1):
                qid = q["id"]
                if (not args.force) and qid in by_id and by_id[qid].get("chatbot_answer"):
                    completed += 1
                    continue

                started_at = time.time()
                if args.answer_from_db:
                    response = await answer_from_db(db_conn, q)
                else:
                    lang_hint = LANG_HINT.get(q.get("query_language"), None)
                    if q.get("domain") == "legal":
                        endpoint = args.chatbot_legal_endpoint
                    else:
                        endpoint = args.chatbot_query_endpoint

                    payload = {"question": q["query"]}
                    if lang_hint:
                        payload["language"] = lang_hint

                    response = await ask_chatbot_with_retry(
                        client=client,
                        endpoint=endpoint,
                        payload=payload,
                        max_retries=args.max_retries,
                    )
                elapsed_ms = int((time.time() - started_at) * 1000)

                record = {
                    "id": qid,
                    "domain": q.get("domain"),
                    "intent": q.get("intent"),
                    "query_language": q.get("query_language"),
                    "query": q.get("query"),
                    "source_document_id": q.get("source_document_id"),
                    "source_title": q.get("source_title"),
                    "chatbot_answer": response.get("answer", ""),
                    "chatbot_source": response.get("source", "unknown"),
                    "chatbot_lang": response.get("lang"),
                    "chatbot_session_id": response.get("session_id"),
                    "retrieved_docs": response.get("retrieved_docs", []),
                    "request_error": response.get("error"),
                    "latency_ms": elapsed_ms,
                    "human_eval": {
                        "criteria": {k: None for k in CRITERIA},
                        "overall_score": None,
                        "notes": "",
                    },
                }
                by_id[qid] = record

                if i % 5 == 0:
                    checkpoint_rows = [by_id[q["id"]] for q in queries if q["id"] in by_id]
                    save_json(output_path, checkpoint_rows)
                    print(f"Progress: {i}/{len(queries)} queries processed")

                await asyncio.sleep(args.min_interval_seconds)
        finally:
            if db_conn is not None:
                await db_conn.close()
            if engine is not None:
                await engine.dispose()

    final_rows = [by_id[q["id"]] for q in queries]
    save_json(output_path, final_rows)

    ok = sum(1 for r in final_rows if not r.get("request_error"))
    failed = len(final_rows) - ok
    print(f"Saved {len(final_rows)} records to {output_path}")
    print(f"Answered successfully: {ok} | failed: {failed} | resumed-existing: {completed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run chatbot answers for human-eval dataset")
    parser.add_argument("--input", default="evaluation/human_eval/human_eval_queries.json")
    parser.add_argument("--output", default="evaluation/human_eval/human_eval_qa.json")
    parser.add_argument("--chatbot-query-endpoint", default="http://localhost:8000/query")
    parser.add_argument("--chatbot-legal-endpoint", default="http://localhost:8000/legal_search")
    parser.add_argument("--answer-from-db", action="store_true", help="Build answers directly from DB chunks by source_document_id (no Exa/web).")
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--min-interval-seconds", type=float, default=1.2)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--request-timeout", type=float, default=120.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
