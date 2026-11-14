from pathlib import Path
from pypdf import PdfReader

RAW = Path("data/raw")

def extract_pages(pdf_path):
    """Renvoie une liste : un dictionnaire par page."""
    reader = PdfReader(pdf_path)
    pages = []
    for num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"source": pdf_path.name, "page": num, "text": text})
    return pages

if __name__ == "__main__":
    import json
    from clean import clean_pages
    from metadata import load_sources, add_metadata
    from chunk import chunk_pages

    sources = load_sources()
    tous = []
    for pdf in sorted(RAW.glob("*.pdf")):
        pages = add_metadata(clean_pages(extract_pages(pdf)), sources)
        chunks = chunk_pages(pages)
        tous.extend(chunks)
        print(f"{pages[0]['titre'][:45]:45} {len(chunks):4} morceaux")

    for i, c in enumerate(tous):
        c["id"] = i
    with open("data/chunks.jsonl", "w", encoding="utf-8") as f:
        for c in tous:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    tailles = [len(c["text"]) for c in tous]
    print(f"\nTotal : {len(tous)} morceaux, taille moyenne {sum(tailles)//len(tailles)} car.")
    print("\n--- Exemple ---")
    print(json.dumps(tous[len(tous)//2], ensure_ascii=False, indent=2))