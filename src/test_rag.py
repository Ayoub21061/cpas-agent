"""
Test rapide de toute la chaîne RAG (search + generate) sur quelques questions.

À lancer depuis la racine du repo, une fois l'index construit :
    python src/test_rag.py

Pour chaque question, le script affiche :
  - les distances des extraits trouvés par search() (pour régler max_distance)
  - la réponse générée et ses sources
  - si le résultat correspond à ce qu'on attendait (trouvé / pas trouvé)
"""

from search import search
from generate import generate

# Chaque cas : (question, filtres pour la recherche, réponse attendue ?)
#   True  = les documents couvrent la question, on attend une réponse sourcée
#   False = hors sujet, on attend « je ne sais pas »
CAS = [
    ("Quelles sont les conditions pour avoir le revenu d'intégration ?", {}, True),
    ("Qu'est-ce qu'une adresse de référence pour un sans-abri ?", {"public": "sans-abri"}, True),
    ("Est-ce qu'un étudiant peut demander de l'aide au CPAS ?", {"public": "étudiant"}, True),
    ("Quelles aides pour l'énergie à Anderlecht ?", {"commune": "Anderlecht"}, True),
    ("Comment faire une pâte à crêpes ?", {}, False),
    ("Qui a gagné la Coupe du monde 2022 ?", {}, False),
]

reussis = 0
for question, filtres, attendu in CAS:
    print("=" * 80)
    print("Question :", question, filtres or "")

    # 1. Recherche seule : on affiche les distances (plus petit = plus proche)
    distances = [round(score, 3) for _doc, score in search(question, **filtres)]
    print("Distances des extraits :", distances)

    # 2. Chaîne complète : recherche + génération
    r = generate(question, **filtres)
    print("\nRéponse :", r["reponse"])
    for s in r["sources"]:
        print(f"  - {s['titre']}, p. {s['page']} ({s['date']})")

    # 3. Comparaison avec ce qu'on attendait
    ok = r["trouve"] == attendu
    reussis += ok
    print("\nAttendu :", "réponse" if attendu else "je ne sais pas",
          "→", "OK" if ok else "À VÉRIFIER")

print("=" * 80)
print(f"{reussis}/{len(CAS)} cas conformes. Détail des appels dans logs/llm_calls.jsonl")