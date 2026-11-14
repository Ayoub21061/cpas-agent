import json
import time
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()
INDEX_DIR = "data/index"

def load_chunks(path="data/chunks.jsonl"):
    docs = []
    with open(path, encoding="utf-8") as f:
        for ligne in f:
            c = json.loads(ligne)
            texte = c.pop("text")
            docs.append(Document(page_content=texte, metadata=c))
    return docs

def get_store():
    embeddings = MistralAIEmbeddings(model="mistral-embed")
    return Chroma(
        collection_name="cpas",
        embedding_function=embeddings,
        persist_directory=INDEX_DIR,
    )

if __name__ == "__main__":
    docs = load_chunks()
    store = get_store()
    LOT = 50
    for i in range(0, len(docs), LOT):
        lot = docs[i:i + LOT]
        store.add_documents(lot, ids=[str(d.metadata["id"]) for d in lot])
        print(f"{min(i + LOT, len(docs))}/{len(docs)} morceaux indexés")
        time.sleep(1)
    print("Index enregistré dans", INDEX_DIR)