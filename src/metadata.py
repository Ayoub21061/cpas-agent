import csv

def load_sources(path="data/sources.csv"):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))

def add_metadata(pages, sources):
    nom = pages[0]["source"]
    fiche = next((s for s in sources if s["cle"] in nom), None)
    if fiche is None:
        raise ValueError(f"Aucune ligne de sources.csv pour : {nom}")
    meta = {k: v for k, v in fiche.items() if k != "cle"}
    return [{**p, **meta} for p in pages]