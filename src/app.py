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
from langue import LANGUES, detecter_langue

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(title="Assistant CPAS")


# 1. Garde-fou : détection des situations d'urgence
# Contrôle par mots-clés, fait AVANT tout appel au LLM : en cas d'urgence,
# la personne doit recevoir immédiatement des contacts humains, pas un
# résumé de documents. Liste volontairement simple, à compléter.
# 1. Garde-fou : détection des situations d'urgence
# Contrôle par mots-clés, fait AVANT tout appel au LLM : en cas d'urgence,
# la personne doit recevoir immédiatement des contacts humains, pas un
# résumé de documents. Mêmes langues que langue.py. Liste volontairement
# simple, à compléter et à faire relire par des locuteurs de chaque langue.
URGENCES = {
    "vie": [
        "suicide", "me suicider", "en finir", "mettre fin a mes jours", "plus envie de vivre", "me tuer",
        "zelfmoord", "mezelf van kant maken", "wil niet meer leven", "er een einde aan maken",
        "kill myself", "end my life", "don't want to live", "dont want to live",
        "suicidio", "suicidarme", "quitarme la vida", "no quiero vivir",
        "me matar", "tirar a minha vida", "não quero viver",
        "انتحار", "أنتحر", "أقتل نفسي", "لا أريد أن أعيش",
        "intihar", "kendimi öldür", "yaşamak istemiyorum",
        "sinucid", "să mă omor", "nu mai vreau să trăiesc",
        "samobój", "zabić się", "nie chcę żyć",
    ],
    "danger": [
        "violence", "il me frappe", "elle me frappe", "on me frappe", "je suis en danger", "menace de mort",
        "geweld", "hij slaat me", "zij slaat me", "ik ben in gevaar",
        "he hits me", "she hits me", "beats me", "i am in danger", "i'm in danger",
        "violencia", "me pega", "estoy en peligro",
        "violência", "me bate", "estou em perigo",
        "عنف", "يضربني", "تضربني", "في خطر",
        "şiddet", "beni dövüyor", "tehlikedeyim",
        "violență", "mă bate", "sunt în pericol",
        "przemoc", "bije mnie", "jestem w niebezpieczeństwie",
    ],
    "rue": [
        "dors dehors", "dormir dehors", "dans la rue ce soir", "nulle part ou dormir", "pas ou dormir",
        "expulse aujourd'hui",
        "slaap op straat", "op straat slapen", "geen slaapplaats", "nergens om te slapen",
        "sleep on the street", "sleeping on the street", "sleeping outside", "nowhere to sleep",
        "duermo en la calle", "dormir en la calle", "no tengo donde dormir",
        "durmo na rua", "dormir na rua", "não tenho onde dormir",
        "أنام في الشارع", "ليس لدي مكان للنوم",
        "sokakta yatıyorum", "sokakta uyuyorum", "kalacak yerim yok", "yatacak yerim yok",
        "dorm pe stradă", "nu am unde să dorm",
        "śpię na ulicy", "nie mam gdzie spać",
    ],
}


def _normaliser(texte):
    texte = texte.lower().replace("’", "'")
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))

# Les mots-clés sont normalisés une fois, comme le seront les questions.
_URGENCES = {t: [_normaliser(m) for m in mots] for t, mots in URGENCES.items()}


def detecter_urgence(question):
    q = _normaliser(question)
    for type_urgence, mots in _URGENCES.items():
        if any(m in q for m in mots):
            return type_urgence
    return None


# 2. API
class Demande(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    public: str = "général"
    commune: str | None = None
    langue: str | None = None   # langue de la réponse précédente, si conversation


@app.post("/api/ask")
@app.post("/api/ask")
def ask(demande: Demande):
    question = demande.question.strip()

    # Langue de la conversation : sert seulement si la détection hésite.
    precedente = demande.langue if demande.langue in LANGUES else "fr"
    langue = detecter_langue(question, defaut=precedente)

    urgence = detecter_urgence(question)
    if urgence:
        return {"urgence": urgence, "reponse": None, "trouve": False,
                "sources": [], "extraits": [], "usage": None, "langue": langue}

    commune = demande.commune or None
    try:
        r = generate(question, public=demande.public, commune=commune, langue=langue)
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

    # Dernier résultat du benchmark principal (le plus récent par nom de
    # fichier). Les tests multilingues ou d'ablation ne sont pas affichés ici.
    benchmark = None
    for f in sorted((ROOT / "results").glob("*_resume.json"), reverse=True):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r.get("benchmark", "benchmark.json") == "benchmark.json":
            benchmark = r
            break

    # Version du prompt réellement utilisé par generate.py
    from generate import PROMPT_PATH
    with open(ROOT / PROMPT_PATH, encoding="utf-8") as f:
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
