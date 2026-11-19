"""
Générer la réponse.

Chaîne complète :
    question → search() → extraits numérotés → LLM → réponse + sources

"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from search import search

load_dotenv()

PROMPT_PATH = Path("prompts/answer.yaml")
LOG_PATH = Path("logs/llm_calls.jsonl")

# Message renvoyé quand la recherche ne trouve rien d'exploitable.
# Ecrit en dur : pas besoin d'appeler le LLM pour dire « je ne sais pas ».
PAS_DE_REPONSE = (
    "Je n'ai pas trouvé cette information dans mes documents. "
    "Le mieux est de poser la question directement à votre CPAS."
)


# 1. Format de sortie imposé au LLM

# Avec with_structured_output(), LangChain demande au modèle de répondre en
# JSON qui respecte ce schéma, puis le valide avec Pydantic. Si le JSON est
# invalide, on obtient une erreur au lieu d'un texte libre à parser à la main.

class ReponseLLM(BaseModel):
    reponse: str = Field(description="Réponse en français simple, 5 phrases maximum.")
    sources: list[int] = Field(
        default_factory=list,
        description="Numéros des extraits réellement utilisés pour répondre.",
    )

    trouve: bool = Field(
        description="true si les extraits contiennent la réponse, sinon false."
    )



# 2. Choix du modèle (API Mistral ou ollama si en local)
def get_llm():
    """
    Le fournisseur se choisit dans le fichier .env, sans toucher au code :
        LLM_PROVIDER=mistral   (par défaut)  → API Mistral, il faut MISTRAL_API_KEY
        LLM_PROVIDER=ollama                   → modèle local servi par Ollama
    Le nom du modèle se règle avec LLM_MODEL.
    temperature=0 : le modèle choisit toujours le mot le plus probable, donc
    les réponses sont stables d'une exécution à l'autre.
    """
    provider = os.getenv("LLM_PROVIDER", "mistral")
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("LLM_MODEL", "ministral-3:3b"), temperature=0)

    from langchain_mistralai import ChatMistralAI
    return ChatMistralAI(model=os.getenv("LLM_MODEL", "ministral-3b-latest"), temperature=0)


# 3. Prompt
def load_prompt(path=PROMPT_PATH):
    """Lit le prompt versionné (YAML) et en fait un ChatPromptTemplate."""
    with open(path, encoding="utf-8") as f:
        p = yaml.safe_load(f)
    template = ChatPromptTemplate.from_messages([("system", p["system"]), ("user", p["user"])])
    return template, p["version"]


def format_contexte(resultats):
    """
    Transforme les résultats de search() en texte pour le prompt.
    Chaque extrait reçoit un numéro (1, 2, 3...) que le LLM citera.
    Les balises <extrait> séparent clairement les documents des instructions,
    ce qui limite l'injection de prompt via un document.
    """
    blocs = []
    for i, (doc, _score) in enumerate(resultats, start=1):
        m = doc.metadata
        entete = f"{m['titre']}, p. {m['page']}, {m['date']}"
        blocs.append(f'<extrait numero="{i}" source="{entete}">\n{doc.page_content}\n</extrait>')
    return "\n\n".join(blocs)


# 4. Journalisation (pour mesurer coût, latence et impact environnemental)
def log_call(entree):
    """Ajoute une ligne JSON par appel au LLM dans logs/llm_calls.jsonl."""
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


# 5. Fonction principale
# Seuil calibré sur un premier test (test_rag.py, 6 questions) :
#   questions couvertes : meilleure distance entre 0.24 et 0.33
#   questions hors sujet : meilleure distance entre 0.49 et 0.53
# 0.45 sépare les deux groupes. À revérifier quand le benchmark sera plus grand.
MAX_DISTANCE = 0.45


def generate(question, k=4, public="général", commune=None, max_distance=MAX_DISTANCE, llm=None):
    """
    Répond à une question à partir des documents indexés.

    max_distance : Chroma renvoie une DISTANCE (plus petit = plus proche).
        Si le meilleur extrait est plus loin que ce seuil, on considère qu'on
        n'a rien trouvé et on n'appelle pas le LLM (économie d'un appel).
        None = pas de filtre. Par défaut MAX_DISTANCE (voir plus haut).
    llm : permet d'injecter un autre modèle (tests, ablation). Par défaut get_llm().

    Renvoie un dict :
        {"reponse": str, "trouve": bool,
         "sources":  [{"titre", "page", "date", "editeur", "extrait"}...],
         "extraits": [{"titre", "page", "distance"}...],
         "usage":    {"modele", "tokens_entree", "tokens_sortie", "latence_s"} ou None}
    """
    # 5.1 Recherche 
    resultats = search(question, k=k, public=public, commune=commune)

    # Extraits trouvés par search() (titre, page, distance), pour l'évaluation (hit@k)
    extraits = [{"titre": d.metadata["titre"], "page": d.metadata["page"],
                 "distance": round(s, 3)} for d, s in resultats]

    # Format de sortie commun à tous les cas
    def resultat(reponse, trouve, sources, usage=None):
        return {"reponse": reponse, "trouve": trouve, "sources": sources,
                "extraits": extraits, "usage": usage}

    # 5.2 Rien de pertinent → réponse fixe, sans appel au LLM
    if not resultats or (max_distance is not None and resultats[0][1] > max_distance):
        return resultat(PAS_DE_REPONSE, False, [])

    # 5.3 Construction de la chaîne : prompt → LLM qui renvoie du JSON validé.
    # include_raw=True : on récupère aussi le message brut, qui contient le
    # nombre de tokens consommés (pour les logs et EcoLogits).
    llm = llm or get_llm()
    template, version = load_prompt()
    chaine = template | llm.with_structured_output(ReponseLLM, include_raw=True)

    debut = time.perf_counter()
    sortie = chaine.invoke({"contexte": format_contexte(resultats), "question": question})
    latence = time.perf_counter() - debut

    brut, parsed = sortie["raw"], sortie["parsed"]
    usage = getattr(brut, "usage_metadata", None) or {}
    # Coût de l'appel, renvoyé avec la réponse (pour l'évaluation)
    infos_appel = {
        "modele": getattr(llm, "model", None) or getattr(llm, "model_name", None),
        "tokens_entree": usage.get("input_tokens"),
        "tokens_sortie": usage.get("output_tokens"),
        "latence_s": round(latence, 3),
    }
    log_call({
        "date": datetime.now(timezone.utc).isoformat(),
        "etape": "generate",
        "modele": getattr(llm, "model", None) or getattr(llm, "model_name", None),
        "prompt_version": version,
        "question": question,
        "tokens_entree": usage.get("input_tokens"),
        "tokens_sortie": usage.get("output_tokens"),
        "latence_s": round(latence, 3),
        "erreur_format": parsed is None,
    })

    # 5.4 Le modèle n'a pas respecté le schéma JSON → on ne devine pas,
    # on répond comme si on n'avait rien trouvé.
    if parsed is None:
        return resultat(PAS_DE_REPONSE, False, [], infos_appel)

    # 5.5 Citations construites par le code : on ne garde que les numéros
    # valides (entre 1 et k), sans doublons, dans l'ordre donné par le LLM.
    sources = []
    for n in dict.fromkeys(parsed.sources):
        if 1 <= n <= len(resultats):
            doc, _ = resultats[n - 1]
            m = doc.metadata
            sources.append({
                "titre": m["titre"],
                "page": m["page"],
                "date": m["date"],
                "editeur": m["editeur"],
                "extrait": doc.page_content[:200],
            })

    # 5.6 « trouvé » est décidé par le CODE, pas par le LLM.
    # Constat en test : Ministral 3B répond correctement avec des sources,
    # mais met souvent trouve=false dans son JSON. On ne s'appuie donc pas sur
    # ce champ : une réponse est « trouvée » si elle cite au moins une source
    # valide. Sans source, la réponse n'est pas vérifiable → réponse fixe.
    if not sources:
        return resultat(PAS_DE_REPONSE, False, [], infos_appel)

    return resultat(parsed.reponse, True, sources, infos_appel)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--public", default="général")
    parser.add_argument("--commune", default=None)
    parser.add_argument("-k", type=int, default=4)
    args = parser.parse_args()

    r = generate(args.question, k=args.k, public=args.public, commune=args.commune)
    print("\n" + r["reponse"])
    if r["sources"]:
        print("\nSources :")
        for s in r["sources"]:
            print(f"  - {s['titre']} ({s['editeur']}, {s['date']}), p. {s['page']}")