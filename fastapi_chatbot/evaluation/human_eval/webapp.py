#!/usr/bin/env python
"""Human evaluation web app for legal/NLP chatbot answers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "human_eval_qa.json"
RATINGS_PATH = BASE_DIR / "human_eval_ratings.json"
WEB_DIR = BASE_DIR / "web"

CRITERIA = [
    "legal_correctness",
    "completeness",
    "clarity",
    "source_citation",
    "safe_fallback",
]

app = FastAPI(title="Human Evaluation - Chatbot RAG", version="1.0.0")


class RatingPayload(BaseModel):
    rater_id: str = Field(..., min_length=2, max_length=80)
    item_id: str = Field(..., min_length=1)
    legal_correctness: int = Field(..., ge=1, le=5)
    completeness: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    source_citation: int = Field(..., ge=1, le=5)
    safe_fallback: int = Field(..., ge=1, le=5)
    notes: str = Field(default="", max_length=4000)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_overall(item: dict[str, Any]) -> float:
    vals = [float(item.get(k, 0)) for k in CRITERIA]
    return round(sum(vals) / len(vals), 2)


@app.get("/api/dataset")
def api_dataset() -> list[dict[str, Any]]:
    rows = load_json(DATASET_PATH, default=[])
    if not rows:
        raise HTTPException(status_code=404, detail=f"Dataset not found at {DATASET_PATH}")
    return rows


@app.get("/api/ratings")
def api_ratings() -> list[dict[str, Any]]:
    return load_json(RATINGS_PATH, default=[])


@app.post("/api/ratings")
def api_save_rating(payload: RatingPayload) -> dict[str, Any]:
    ratings = load_json(RATINGS_PATH, default=[])
    row = payload.model_dump()
    row["overall_score"] = compute_overall(row)

    replaced = False
    for i, existing in enumerate(ratings):
        if (
            existing.get("rater_id") == row["rater_id"]
            and existing.get("item_id") == row["item_id"]
        ):
            ratings[i] = row
            replaced = True
            break

    if not replaced:
        ratings.append(row)

    save_json(RATINGS_PATH, ratings)
    return {"ok": True, "updated": replaced, "overall_score": row["overall_score"]}


@app.get("/api/summary")
def api_summary() -> dict[str, Any]:
    ratings = load_json(RATINGS_PATH, default=[])
    if not ratings:
        return {"total_ratings": 0, "overall_average": None, "criteria_average": {}, "by_domain": {}}

    dataset = {item["id"]: item for item in load_json(DATASET_PATH, default=[])}

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 3) if values else 0.0

    criteria_average = {k: avg([float(r[k]) for r in ratings]) for k in CRITERIA}
    overall_average = avg([float(r.get("overall_score", 0.0)) for r in ratings])

    by_domain_raw: dict[str, list[dict[str, Any]]] = {}
    for r in ratings:
        domain = dataset.get(r.get("item_id"), {}).get("domain", "unknown")
        by_domain_raw.setdefault(domain, []).append(r)

    by_domain = {}
    for domain, rows in by_domain_raw.items():
        by_domain[domain] = {
            "count": len(rows),
            "overall_average": avg([float(x.get("overall_score", 0.0)) for x in rows]),
            "criteria_average": {k: avg([float(x[k]) for x in rows]) for k in CRITERIA},
        }

    return {
        "total_ratings": len(ratings),
        "overall_average": overall_average,
        "criteria_average": criteria_average,
        "by_domain": by_domain,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")
