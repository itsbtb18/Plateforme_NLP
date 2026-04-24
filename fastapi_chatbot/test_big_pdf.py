"""Test the large textbook PDF parsing."""

import sys


def main() -> None:
    sys.path.insert(0, ".")
    from app.ingestion.pdf_loader import load_and_chunk_pdf

    result = load_and_chunk_pdf(
        "data/Speech and Language Processing (Jurafsky & Martin).pdf",
        max_tokens=1000,
        overlap_tokens=100,
    )

    print("Title:", result["title"])
    print("Language:", result["language"])
    print("Total chunks:", len(result["chunks"]))

    for c in result["chunks"][:3]:
        print(
            f"  Chunk {c['index']}: heading={c['heading']!r}, tokens~{c['token_est']}"
        )
    print("  ...")
    last = result["chunks"][-1]
    print(
        f"  Chunk {last['index']}: heading={last['heading']!r}, tokens~{last['token_est']}"
    )


if __name__ == "__main__":
    main()
