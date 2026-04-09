import asyncio
from pathlib import Path
from sqlalchemy import select, func

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.ingestion.ingest_nlp_resources import ingest_single_document, _detect_file_kind

TARGETS = {
    "From LLM Reasoning to Autonomous AI Agents_.pdf",
    "Speech and Language Processing (Jurafsky & Martin).pdf",
    "journal laws 2022-1.pdf",
    "journal laws-1.pdf",
    "journal officiel 2025-1.pdf",
    "lois rechercheur supperrior -1.pdf",
    "research-ethics-in-light-of-algerian-legislation-1.pdf",
    "the-legal-framework-for-the-inspection-of-information-systems-in-algerian-legislation-2.pdf",
}


async def main() -> None:
    paths = [
        p
        for p in Path("data").rglob("*")
        if p.is_file() and p.name in TARGETS and _detect_file_kind(p) in ("pdf", "xml")
    ]
    print("RETRY_FILES", len(paths))

    for p in sorted(paths, key=lambda x: x.name.lower()):
        try:
            print("RETRY_INGEST", p.as_posix())
            n = await ingest_single_document(p, difficulty="intermediate", dry_run=False)
            print("RETRY_OK", p.name, n)
        except Exception as exc:
            print("RETRY_FAIL", p.name, type(exc).__name__, str(exc)[:300])

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(NLPKnowledge.source_file, func.count(NLPKnowledge.id)).group_by(
                    NLPKnowledge.source_file
                )
            )
        ).all()

    counts = {row[0]: int(row[1]) for row in rows if row[0]}
    remaining = [name for name in sorted(TARGETS) if name not in counts]
    print("REMAINING_AFTER_RETRY", len(remaining))
    for name in remaining:
        print("REMAINING", name)


if __name__ == "__main__":
    asyncio.run(main())
