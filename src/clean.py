import re
from collections import Counter

def _motif(ligne):
    """Remplace les chiffres par # pour comparer 'Page 3' et 'Page 4'."""
    return re.sub(r"\d+", "#", ligne.strip())

PREFIXES = {"sans", "non", "demi", "mi", "sous", "socio", "médico",
            "psycho", "rendez", "peut", "est", "vis", "celui", "celle"}
ENTETE_GUIDE = (r"Besoin d.une aide du CPAS \? Guide de l.aide sociale pour les "
                r"étudiantes et les étudiants\s*\|\s*\d+\s*\|\s*Street Law Clinic en droit social")

# Règle qui permet de lever l'exception : des mots composés avec un trait d'union doivent rester collés, les autres sont recollés.
def _recoller(m):
    """Garde le trait d'union des mots composés, recolle les autres."""
    avant, apres = m.group(1), m.group(2)
    if avant.lower() in PREFIXES:
        return f"{avant}-{apres}"
    return avant + apres

def clean_pages(pages):
    # 1. Repérer les en-têtes et pieds de page : lignes qui reviennent
    #    en haut ou en bas d'au moins 40 % des pages.
    compte = Counter()
    for p in pages:
        lignes = [l for l in p["text"].splitlines() if l.strip()]
        for l in set(lignes[:2] + lignes[-2:]):
            compte[_motif(l)] += 1
    seuil = max(4, 0.4 * len(pages))
    repetes = {m for m, c in compte.items() if c >= seuil and len(m) < 80}

    propres = []
    for p in pages:
        lignes = [l.strip() for l in p["text"].splitlines()]
        pleines = [l for l in lignes if l]
        bords = set(pleines[:2] + pleines[-2:])
        gardees = []
        for l in lignes:
            if l in bords and _motif(l) in repetes:
                continue                      # en-tête ou pied de page
            if re.fullmatch(r"\d{1,3}", l):
                continue                      # numéro de page seul
            gardees.append(l)
        t = "\n".join(gardees)
        t = re.sub(r"(\w+) ?-\n(\w+)", _recoller, t)     # 2. mots coupés
        t = re.sub(ENTETE_GUIDE, "", t)                  # en-tête du guide étudiant
        t = re.sub(r"Début de la fiche \d+ \|.*?Table des matières", "", t, flags=re.S)
        t = re.sub(r"[ \t]+", " ", t)                    # 3. espaces multiples
        t = re.sub(r"(?<![.:;!?\n])\n(?!\n)", " ", t)    # 4. lignes coupées en pleine phrase
        t = re.sub(r"\n{3,}", "\n\n", t).strip()         # 5. lignes vides en trop
        propres.append({**p, "text": t})
    return propres