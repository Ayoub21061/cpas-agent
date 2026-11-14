from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_pages(pages, chunk_size=1200, chunk_overlap=150, min_chars=100):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for p in pages:
        for morceau in splitter.split_text(p["text"]):
            if len(morceau) < min_chars:
                continue                     # trop court : page de titre, etc.
            meta = {k: v for k, v in p.items() if k != "text"}
            chunks.append({**meta, "text": morceau})
    return chunks