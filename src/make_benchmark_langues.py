"""
Construit data/benchmark_langues.json : 6 questions du benchmark (5 couvertes,
1 hors sujet) dans 6 langues. Les pages attendues sont reprises de la question
française d'origine. Les faits attendus (mots-clés en français) ne sont gardés
que pour le français : les autres réponses sont à relire à la main.
"""
import json

TRADUCTIONS = {
    "q01": {"en": "What are the conditions to receive the integration income?",
            "nl": "Wat zijn de voorwaarden om een leefloon te krijgen?",
            "ar": "ما هي الشروط للحصول على دخل الإدماج؟",
            "es": "¿Cuáles son las condiciones para recibir el ingreso de integración?",
            "tr": "Entegrasyon geliri almak için şartlar nelerdir?"},
    "q02": {"en": "How long does the CPAS have to make a decision after my application?",
            "nl": "Binnen hoeveel tijd moet het OCMW een beslissing nemen na mijn aanvraag?",
            "ar": "في غضون كم من الوقت يجب على CPAS أن يتخذ قراره بعد طلبي؟",
            "es": "¿En cuánto tiempo debe el CPAS tomar su decisión después de mi solicitud?",
            "tr": "CPAS başvurumdan sonra ne kadar sürede karar vermek zorunda?"},
    "q07": {"en": "Does the CPAS have to give me proof that I submitted my application?",
            "nl": "Moet het OCMW mij een bewijs geven dat ik mijn aanvraag heb ingediend?",
            "ar": "هل يجب على CPAS أن يعطيني إثباتًا بأنني قدمت طلبي؟",
            "es": "¿El CPAS tiene que darme un comprobante de que presenté mi solicitud?",
            "tr": "CPAS başvurumu yaptığıma dair bana bir belge vermek zorunda mı?"},
    "q11": {"en": "How does the CPAS social investigation work?",
            "nl": "Hoe verloopt het sociaal onderzoek van het OCMW?",
            "ar": "كيف يجري البحث الاجتماعي الذي يقوم به CPAS؟",
            "es": "¿Cómo se desarrolla la investigación social del CPAS?",
            "tr": "CPAS'ın sosyal incelemesi nasıl yapılıyor?"},
    "q16": {"en": "Will I have to pay back the integration income?",
            "nl": "Zal ik het leefloon moeten terugbetalen?",
            "ar": "هل سيتعين علي إرجاع دخل الإدماج؟",
            "es": "¿Tendré que devolver el ingreso de integración?",
            "tr": "Entegrasyon gelirini geri ödemem gerekecek mi?"},
    "q17": {"en": "How do I make pancake batter?",
            "nl": "Hoe maak ik pannenkoekenbeslag?",
            "ar": "كيف أحضّر عجينة الكريب؟",
            "es": "¿Cómo se hace la masa de crepes?",
            "tr": "Krep hamuru nasıl yapılır?"},
}

if __name__ == "__main__":
    base = {q["id"]: q for q in json.load(open("data/benchmark.json", encoding="utf-8"))}
    sortie = []
    for ref, trads in TRADUCTIONS.items():
        q = base[ref]
        for langue, texte in [("fr", q["question"])] + list(trads.items()):
            sortie.append({
                "id": f"{ref}-{langue}", "ref": ref, "langue": langue, "split": "dev",
                "question": texte, "public": q["public"], "commune": q["commune"],
                "repondable": q["repondable"], "sources_attendues": q["sources_attendues"],
                "faits_attendus": q["faits_attendus"] if langue == "fr" else [],
            })
    with open("data/benchmark_langues.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)
    print(len(sortie), "questions écrites dans data/benchmark_langues.json")