# import sys
# from index import get_store

# def search(question, k=4, filtre=None):
#     store = get_store()
#     return store.similarity_search_with_score(question, k=k, filter=filtre)

# if __name__ == "__main__":
#     question = " ".join(sys.argv[1:]) or "Quelles sont les conditions pour avoir le revenu d'intégration ?"
#     print("Question :", question)
#     for doc, score in search(question):
#         m = doc.metadata
#         print(f"\n[{score:.3f}] {m['titre']} (p. {m['page']}, {m['date']})")
#         print(doc.page_content[:300].replace("\n", " "), "...")

import argparse
from index import get_store

def build_filter(public="général", commune=None):
    publics = ["général"] if public == "général" else ["général", public]
    communes = ["toutes"] + ([commune] if commune else [])
    return {"$and": [{"public": {"$in": publics}},
                     {"commune": {"$in": communes}}]}

def search(question, k=4, public="général", commune=None):
    store = get_store()
    filtre = build_filter(public, commune)
    return store.similarity_search_with_score(question, k=k, filter=filtre)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--public", default="général")
    parser.add_argument("--commune", default=None)
    args = parser.parse_args()
    for doc, score in search(args.question, public=args.public, commune=args.commune):
        m = doc.metadata
        print(f"\n[{score:.3f}] {m['titre']} (p. {m['page']}, {m['date']})")
        print(doc.page_content[:300].replace("\n", " "), "...")