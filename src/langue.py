"""
Détection de la langue d'une question, sans appel au LLM.

Bibliothèque Lingua : hors ligne, déterministe (même texte, même résultat),
fiable sur des phrases courtes. On la limite aux langues les plus parlées
par le public des CPAS bruxellois, ce qui la rend plus rapide et plus sûre.

Règle de prudence : si la détection n'est pas assez sûre (message très
court comme « bonjour », ou mélange de langues), on répond en français.
"""

from lingua import Language, LanguageDetectorBuilder
import re 

# code ISO → (langue Lingua, nom donné au LLM dans le prompt)
LANGUES = {
    "fr": (Language.FRENCH, "français"),
    "nl": (Language.DUTCH, "néerlandais"),
    "en": (Language.ENGLISH, "anglais"),
    "ar": (Language.ARABIC, "arabe"),
    "es": (Language.SPANISH, "espagnol"),
    "pt": (Language.PORTUGUESE, "portugais"),
    "tr": (Language.TURKISH, "turc"),
    "ro": (Language.ROMANIAN, "roumain"),
    "pl": (Language.POLISH, "polonais"),
}

# Salutations et remerciements courants. Sur un ou deux mots, Lingua n'est
# pas fiable (« hallo » → anglais, « hello » → espagnol) : une table l'est.
SALUTATIONS = {
    "bonjour": "fr", "bonsoir": "fr", "salut": "fr", "merci": "fr",
    "hallo": "nl", "dag": "nl", "goedemorgen": "nl", "goedendag": "nl", "dank": "nl", "bedankt": "nl",
    "hello": "en", "hi": "en", "hey": "en", "thanks": "en", "thank": "en",
    "hola": "es", "gracias": "es", "buenos": "es",
    "olá": "pt", "ola": "pt", "obrigado": "pt", "obrigada": "pt",
    "merhaba": "tr", "selam": "tr", "teşekkürler": "tr",
    "bună": "ro", "salutare": "ro", "mulțumesc": "ro",
    "cześć": "pl", "dzień": "pl", "dziękuję": "pl",
    "مرحبا": "ar", "السلام": "ar", "سلام": "ar", "شكرا": "ar",
}

PAR_DEFAUT = "fr"
CONFIANCE_MIN = 0.4   # en dessous, on garde le français
ECART_MIN = 2.0 # elle doit être au moins 2 fois plus probable que la suivante

_CODES = {lingua: code for code, (lingua, _) in LANGUES.items()}
_detecteur = (LanguageDetectorBuilder
              .from_languages(*(l for l, _ in LANGUES.values()))
              .build())


def detecter_langue(texte):
    """Renvoie le code de la langue du texte ("fr", "nl", "ar"...)."""
    mots = re.findall(r"\w+", (texte or "").lower())
    if not mots:
        return PAR_DEFAUT

    # 1. Le message commence par une salutation connue ?
    salutation = SALUTATIONS.get(mots[0])
    if salutation and len(mots) <= 3:
        return salutation              # « hallo », « Hello! », « Dag mevrouw »
    if len(mots) < 2:
        return PAR_DEFAUT              # un seul mot inconnu : trop peu pour décider

    # 2. Sinon, Lingua
    scores = _detecteur.compute_language_confidence_values(texte)
    premiere, deuxieme = scores[0], scores[1]
    if premiere.value >= CONFIANCE_MIN and premiere.value >= ECART_MIN * deuxieme.value:
        return _CODES[premiere.language]

    # 3. Lingua hésite : la salutation du début tranche, sinon le français
    return salutation or PAR_DEFAUT


def nom_langue(code):
    """Nom de la langue en français, pour le prompt : "nl" → "néerlandais"."""
    return LANGUES.get(code, LANGUES[PAR_DEFAUT])[1]


# Message fixe renvoyé sans appel au LLM quand l'agent ne trouve rien.
# Traduit à l'avance : pas besoin d'un appel au modèle pour dire « je ne sais pas ».
PAS_DE_REPONSE = {
    "fr": "Je n'ai pas trouvé cette information dans mes documents. "
          "Le mieux est de poser la question directement à votre CPAS.",
    "nl": "Ik heb deze informatie niet gevonden in mijn documenten. "
          "Stel uw vraag het best rechtstreeks aan uw OCMW.",
    "en": "I could not find this information in my documents. "
          "The best option is to ask your CPAS directly.",
    "ar": "لم أجد هذه المعلومة في وثائقي. "
          "من الأفضل أن تطرح سؤالك مباشرة على مركز العمل الاجتماعي (CPAS) في بلديتك.",
    "es": "No he encontrado esta información en mis documentos. "
          "Lo mejor es que haga la pregunta directamente a su CPAS.",
    "pt": "Não encontrei esta informação nos meus documentos. "
          "O melhor é colocar a pergunta diretamente ao seu CPAS.",
    "tr": "Bu bilgiyi belgelerimde bulamadım. "
          "En iyisi sorunuzu doğrudan CPAS'ınıza sormanızdır.",
    "ro": "Nu am găsit această informație în documentele mele. "
          "Cel mai bine este să puneți întrebarea direct la CPAS-ul dumneavoastră.",
    "pl": "Nie znalazłem tej informacji w moich dokumentach. "
          "Najlepiej zadać to pytanie bezpośrednio w swoim CPAS.",
}


def pas_de_reponse(code):
    return PAS_DE_REPONSE.get(code, PAS_DE_REPONSE[PAR_DEFAUT])


if __name__ == "__main__":
    exemples = [
        "Quelles sont les conditions pour avoir le revenu d'intégration ?",
        "Wat zijn de voorwaarden om een leefloon te krijgen?",
        "Will I have to pay back the integration income?",
        "ما هي الشروط للحصول على دخل الإدماج؟",
        "¿Tendré que devolver el ingreso de integración?",
        "Entegrasyon geliri almak için şartlar nelerdir?",
        "bonjour",
        "hallo",
        "hello",
        "Nice to meet you!"
    ]
    for q in exemples:
        code = detecter_langue(q)
        print(f"{code}  {nom_langue(code):12} {q}")