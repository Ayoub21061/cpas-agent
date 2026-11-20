"""
Évaluation de la chaîne RAG (search + generate) sur data/benchmark.json.

Métriques calculées
    1. Décision (toutes les questions)
       - exactitude : l'agent répond quand il faut, refuse quand il faut
       - fausses réponses : il répond à une question hors corpus (le plus grave)
       - refus à tort : il dit « je ne sais pas » alors que la réponse existe
    2. Recherche (questions répondables)
       - hit@k : au moins une page attendue fait partie des k extraits trouvés
    3. Citations (questions répondables où l'agent a répondu)
       - précision des citations : part des sources citées qui sont attendues
    4. Contenu (questions répondables où l'agent a répondu)
       - couverture des faits : part des éléments attendus présents dans la
         réponse (recherche de mots-clés, donc approximatif → relire à la main)
    5. Coût : latence et tokens moyens par appel au LLM

Résultats : un fichier par question dans results/<date>_<modele>_<split>.jsonl
            et un résumé dans results/<date>_<modele>_<split>_resume.json
"""

import argparse
import json
import os
import unicodedata
from datetime import datetime
from pathlib import Path
from statistics import mean
from langue import detecter_langue
import re 

from generate import generate
from metadata import load_sources

BENCHMARK = Path("data/benchmark.json")
RESULTS = Path("results")


# Outils de comparaison
def normaliser(texte):
    """
    Met un texte sous une forme comparable : minuscules, sans accents,
    apostrophes typographiques (’) remplacées par des apostrophes simples (').
    Ainsi « Accusé de réception » et « accuse de reception » sont égaux.
    """
    texte = texte.lower().replace("’", "'")
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


def est_attendue(titre, page, sources_attendues):
    """
    Vrai si (titre, page) fait partie des sources attendues.
    "pages": null dans le benchmark veut dire « n'importe quelle page ».
    """
    for s in sources_attendues:
        if s["titre"] == titre and (s["pages"] is None or page in s["pages"]):
            return True
    return False


def faits_couverts(reponse, faits_attendus):
    """
    Chaque fait attendu est une liste de variantes, ex. ["30 jours", "trente jours"].
    Un fait est couvert si AU MOINS UNE variante apparaît dans la réponse.
    Renvoie (nombre couvert, liste des faits manquants).
    """
    r = normaliser(reponse)
    manquants = [f for f in faits_attendus if not any(normaliser(v) in r for v in f)]
    return len(faits_attendus) - len(manquants), manquants


def verifier_titres(cas):
    """Signale les titres du benchmark qui n'existent pas dans sources.csv (faute de frappe)."""
    titres = {s["titre"] for s in load_sources()}
    for c in cas:
        for s in c["sources_attendues"]:
            if s["titre"] not in titres:
                print(f"ATTENTION {c['id']} : titre inconnu dans sources.csv → {s['titre']}")


# Évaluation d'une question
def evaluer_cas(cas, k):
    r = generate(cas["question"], k=k, public=cas["public"], commune=cas["commune"])

    ligne = {
        "id": cas["id"],
        "question": cas["question"],
        "repondable": cas["repondable"],
        "trouve": r["trouve"],
        "decision_ok": r["trouve"] == cas["repondable"],
        "reponse": r["reponse"],
        "sources_citees": [f"{s['titre']} p.{s['page']}" for s in r["sources"]],
        "extraits": r["extraits"],
        "usage": r["usage"],
    }

    ligne["question_recherche"] = r.get("question_recherche")

    if "langue" in cas:
        # La réponse est-elle dans la langue de la question ?
        # On retire les parenthèses : la règle 8 du prompt y garde les termes
        # officiels en français, ce qui fausserait la détection.
        ligne["langue"] = cas["langue"]
        ligne["langue_reponse"] = detecter_langue(re.sub(r"\([^)]*\)", " ", r["reponse"]))
        ligne["langue_ok"] = ligne["langue_reponse"] == cas["langue"]

    if cas["repondable"]:
        # Recherche : une des pages attendues est-elle dans les k extraits ?
        ligne["hit"] = any(est_attendue(e["titre"], e["page"], cas["sources_attendues"])
                           for e in r["extraits"])

        if r["trouve"]:
            # Citations : quelle part des sources citées est attendue ?
            bonnes = [s for s in r["sources"]
                      if est_attendue(s["titre"], s["page"], cas["sources_attendues"])]
            ligne["precision_citations"] = len(bonnes) / len(r["sources"])

            # Contenu : quels éléments attendus apparaissent dans la réponse ?
            n, manquants = faits_couverts(r["reponse"], cas["faits_attendus"])
            ligne["couverture_faits"] = n / len(cas["faits_attendus"]) if cas["faits_attendus"] else None
            ligne["faits_manquants"] = manquants
    return ligne


# Résumé
def moyenne(valeurs):
    """Moyenne des valeurs non nulles, ou None s'il n'y en a pas."""
    v = [x for x in valeurs if x is not None]
    return round(mean(v), 3) if v else None


def resumer(lignes):
    rep = [l for l in lignes if l["repondable"]]
    hors = [l for l in lignes if not l["repondable"]]
    repondues = [l for l in rep if l["trouve"]]
    appels = [l["usage"] for l in lignes if l["usage"]]

    return {
        "nb_questions": len(lignes),
        "exactitude_decision": moyenne([l["decision_ok"] for l in lignes]),
        "fausses_reponses": f"{sum(l['trouve'] for l in hors)}/{len(hors)}",
        "refus_a_tort": f"{sum(not l['trouve'] for l in rep)}/{len(rep)}",
        "hit_at_k": moyenne([l["hit"] for l in rep]),
        "precision_citations": moyenne([l.get("precision_citations") for l in repondues]),
        "couverture_faits": moyenne([l.get("couverture_faits") for l in repondues]),
        "nb_appels_llm": len(appels),
        "latence_moyenne_s": moyenne([a["latence_s"] for a in appels]),
        "tokens_entree_moyens": moyenne([a["tokens_entree"] for a in appels]),
        "tokens_sortie_moyens": moyenne([a["tokens_sortie"] for a in appels]),
        "langue_correcte": moyenne([l.get("langue_ok") for l in lignes]),
    }


# Programme principal
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("-k", type=int, default=4, help="nombre d'extraits récupérés")
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK,
                        help="fichier de questions (par défaut data/benchmark.json)")
    args = parser.parse_args()

    with open(args.benchmark, encoding="utf-8") as f:
        cas = json.load(f)
    verifier_titres(cas)
    if args.split != "all":
        cas = [c for c in cas if c["split"] == args.split]

    lignes = []
    for c in cas:
        l = evaluer_cas(c, args.k)
        lignes.append(l)
        # Affichage court au fil de l'eau
        etat = "OK " if l["decision_ok"] else "ERR"
        extra = ""
        if l.get("hit") is False:
            extra += "  [recherche ratée]"
        if l.get("langue_ok") is False:
            extra += f"  [réponse en {l['langue_reponse']}]"
        if l.get("faits_manquants"):
            extra += f"  [manque : {', '.join(f[0] for f in l['faits_manquants'])}]"
        print(f"{etat} {l['id']}  {l['question'][:60]:60}{extra}")

    resume = resumer(lignes)
    # Résumé par langue, seulement si les questions ont un champ "langue"
    langues = [l["langue"] for l in lignes if "langue" in l]
    if langues:
        par_langue = {}
        for code in dict.fromkeys(langues):
            r = resumer([l for l in lignes if l.get("langue") == code])
            par_langue[code] = {c: r[c] for c in ("hit_at_k", "exactitude_decision",
                                                  "refus_a_tort", "langue_correcte")}
        resume["par_langue"] = par_langue
    resume.update({"benchmark": args.benchmark.name,
                   "split": args.split, "k": args.k,
                   # nom réel du modèle (renvoyé par generate), sinon celui du .env
                   "modele": next((l["usage"]["modele"] for l in lignes if l["usage"]),
                                  os.getenv("LLM_MODEL", "ministral-3b-latest")),
                   "date": datetime.now().isoformat(timespec="minutes"
                   "modele_traduction": os.getenv("TRADUCTION_MODEL") or "même modèle",)})

    print("\n--- Résumé ---")
    for cle, val in resume.items():
        if cle == "par_langue":
            print("par langue :")
            for code, m in val.items():
                print(f"  {code}  " + "  ".join(f"{c}={v}" for c, v in m.items()))
        else:
            print(f"{cle:24} {val}")

    # Sauvegarde : détail par question + résumé (pour le rapport et l'ablation)
    RESULTS.mkdir(exist_ok=True)
    suffixe = "" if args.benchmark.name == BENCHMARK.name else f"_{args.benchmark.stem}"
    nom = f"{datetime.now():%Y%m%d-%H%M}_{resume['modele']}{suffixe}_{args.split}_k{args.k}"
    with open(RESULTS / f"{nom}.jsonl", "w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    with open(RESULTS / f"{nom}_resume.json", "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats enregistrés dans {RESULTS / nom}.jsonl")