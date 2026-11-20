"""
Site web de démonstration de l'agent CPAS.

Lancement, depuis la racine du dépôt :
    uvicorn app:app --app-dir src --reload
puis ouvrir http://127.0.0.1:8000

Le site a deux parties :
  - /api/ask  : pose une question à l'agent (recherche + génération)
  - /api/info : informations sur le projet (corpus, résultats du benchmark)
La page web elle-même est dans web/index.html.
"""

import csv
import json
import os
import unicodedata
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from generate import generate

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Assistant CPAS")


# 1. Garde-fou : détection des situations d'urgence
# Contrôle par mots-clés, fait AVANT tout appel au LLM : en cas d'urgence,
# la personne doit recevoir immédiatement des contacts humains, pas un
# résumé de documents. Liste volontairement simple, à compléter.
URGENCES = {
    "vie": ["suicide", "me suicider", "en finir", "mettre fin a mes jours",
            "plus envie de vivre", "me tuer"],
    "danger": ["violence", "il me frappe", "elle me frappe", "on me frappe",
               "je suis en danger", "menace de mort"],
    "rue": ["dors dehors", "dormir dehors", "dans la rue ce soir",
            "nulle part ou dormir", "pas ou dormir", "expulse aujourd'hui"],
}


def _normaliser(texte):
    texte = texte.lower().replace("’", "'")
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


def detecter_urgence(question):
    q = _normaliser(question)
    for type_urgence, mots in URGENCES.items():
        if any(m in q for m in mots):
            return type_urgence
    return None


# 2. API
class Demande(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    public: str = "général"
    commune: str | None = None


@app.post("/api/ask")
def ask(demande: Demande):
    question = demande.question.strip()

    urgence = detecter_urgence(question)
    if urgence:
        return {"urgence": urgence, "reponse": None, "trouve": False,
                "sources": [], "extraits": [], "usage": None}

    commune = demande.commune or None
    try:
        r = generate(question, public=demande.public, commune=commune)
    except Exception as e:  # clé API absente, index manquant, réseau...
        return JSONResponse(status_code=503, content={
            "erreur": "L'agent ne répond pas pour le moment.",
            "detail": f"{type(e).__name__} : {e}",
        })
    return {"urgence": None, **r}


@app.get("/api/info")
def info():
    # Corpus : une ligne par document de sources.csv
    with open(ROOT / "data/sources.csv", encoding="utf-8") as f:
        sources = [{k: v for k, v in s.items() if k != "cle"}
                   for s in csv.DictReader(f, delimiter=";")]

    # Nombre de morceaux indexés
    chunks = ROOT / "data/chunks.jsonl"
    nb_chunks = sum(1 for _ in open(chunks, encoding="utf-8")) if chunks.exists() else None

    # Dernier résultat du benchmark (le plus récent par nom de fichier)
    resumes = sorted((ROOT / "results").glob("*_resume.json"))
    benchmark = json.loads(resumes[-1].read_text(encoding="utf-8")) if resumes else None

    # Version du prompt
    with open(ROOT / "prompts/answer.yaml", encoding="utf-8") as f:
        prompt_version = yaml.safe_load(f).get("version")

    return {
        "sources": sources,
        "nb_chunks": nb_chunks,
        "benchmark": benchmark,
        "prompt_version": prompt_version,
        "fournisseur": os.getenv("LLM_PROVIDER", "mistral"),
        "modele": os.getenv("LLM_MODEL", "ministral-3b-latest"),
    }


# 3. La page web (doit être monté en dernier, après les routes /api)
app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
