"""Quick validation of the Docling PDF loader."""
import sys
sys.path.insert(0, ".")
from app.ingestion.pdf_loader import load_and_chunk_pdf, extract_keywords

result = load_and_chunk_pdf("data/AraBERT.pdf", max_tokens=1000, overlap_tokens=100)
print("Title:", result["title"])
print("Language:", result["language"])
print("Total chunks:", len(result["chunks"]))

for c in result["chunks"][:3]:
    print(
        f"  Chunk {c['index']}: heading={c['heading']!r}, "
        f"tokens~{c['token_est']}, "
        f"text={c['content'][:80]!r}..."
    )

kw = extract_keywords(result["chunks"][0]["content"])
print("Keywords:", kw[:10])
