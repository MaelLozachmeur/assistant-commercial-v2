"""Normalisation et comparaison de jeux d'offres fournis par des sources autorisées.

Les adaptateurs de source doivent convertir leurs données vers les champs canoniques
acceptés ici. Ce module ne collecte aucune annonce.
"""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import math
import re
import unicodedata


SOURCES = ("france_travail", "wttj", "adzuna")


def _texte(value):
    return " ".join(str(value or "").split())


def normaliser_offre(source, offre):
    """Conserve uniquement les champs nécessaires aux statistiques et au rapprochement."""
    if source not in SOURCES:
        raise ValueError(f"Source non prise en charge : {source}")
    offer_id = _texte(offre.get("id"))
    title = _texte(offre.get("title"))
    if not offer_id or not title:
        raise ValueError("Une offre normalisée doit avoir un identifiant et un intitulé.")

    salary_min = _salaire(offre.get("salary_min"))
    salary_max = _salaire(offre.get("salary_max"))
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        raise ValueError("Le salaire minimum ne peut pas dépasser le salaire maximum.")
    predicted = offre.get("salary_is_predicted")
    if predicted not in (None, True, False):
        raise ValueError("Le statut du salaire prédit doit être booléen ou absent.")
    return {
        "id": offer_id,
        "source": source,
        "title": title,
        "company": _texte(offre.get("company")),
        "location": _texte(offre.get("location")),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": _texte(offre.get("salary_currency")).upper() or None,
        "salary_period": _texte(offre.get("salary_period")).lower() or None,
        "salary_is_predicted": predicted,
        "skills": _liste_textes(offre.get("skills")),
        "tasks": _liste_textes(offre.get("tasks")),
    }


def _salaire(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Les salaires doivent être numériques.") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Les salaires doivent être des nombres positifs et finis.")
    return number


def _milieu_salaire(offre):
    bas = offre["salary_min"] if offre["salary_min"] is not None else offre["salary_max"]
    haut = offre["salary_max"] if offre["salary_max"] is not None else bas
    return (bas + haut) / 2


def _liste_textes(values):
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted({_texte(value) for value in values if _texte(value)})


def _cle_texte(value):
    normalise = unicodedata.normalize("NFKD", _texte(value).casefold())
    sans_accents = "".join(c for c in normalise if not unicodedata.combining(c))
    sans_genre = re.sub(r"\b(?:h|f)\s*/\s*(?:h|f)\b", " ", sans_accents)
    return " ".join(re.findall(r"[a-z0-9]+", sans_genre))


def _similarite(left, right):
    a, b = _cle_texte(left), _cle_texte(right)
    return SequenceMatcher(None, a, b).ratio() if a and b else None


def _score_candidat(left, right):
    title = _similarite(left["title"], right["title"])
    company = _similarite(left["company"], right["company"])
    location = _similarite(left["location"], right["location"])
    salary = None
    salaires_comparables = (
        left["salary_currency"] is not None
        and left["salary_currency"] == right["salary_currency"]
        and left["salary_period"] is not None
        and left["salary_period"] == right["salary_period"]
        and left["salary_is_predicted"] is False
        and right["salary_is_predicted"] is False
    )
    if (
        salaires_comparables
        and (left["salary_min"] is not None or left["salary_max"] is not None)
        and (right["salary_min"] is not None or right["salary_max"] is not None)
    ):
        left_low = left["salary_min"] if left["salary_min"] is not None else left["salary_max"]
        left_high = left["salary_max"] or left_low
        right_low = right["salary_min"] if right["salary_min"] is not None else right["salary_max"]
        right_high = right["salary_max"] or right_low
        if max(left_low, right_low) <= min(left_high, right_high):
            salary = 1.0
        else:
            ecart = abs((left_low + left_high) / 2 - (right_low + right_high) / 2)
            salary = max(0.0, 1.0 - ecart / max(left_high, right_high))

    # Un titre seul ne suffit jamais à suggérer un doublon.
    if title is None or title < 0.65 or not (
        (company is not None and company >= 0.8)
        or (location is not None and location >= 0.95)
    ):
        return None

    composantes = ((title, 0.55), (company, 0.20), (location, 0.15), (salary, 0.10))
    poids_present = sum(poids for valeur, poids in composantes if valeur is not None)
    score = sum(valeur * poids for valeur, poids in composantes if valeur is not None) / poids_present
    return round(score, 4)


def candidats_doublons(offres, seuil=0.75):
    """Signale des paires inter-sources à vérifier; ne fusionne jamais les annonces."""
    if not 0 <= seuil <= 1:
        raise ValueError("Le seuil de rapprochement doit être compris entre 0 et 1.")
    resultats = []
    for index, left in enumerate(offres):
        for right in offres[index + 1:]:
            if left["source"] == right["source"]:
                continue
            score = _score_candidat(left, right)
            if score is None or score < seuil:
                continue
            resultats.append({
                "source_a": left["source"],
                "id_a": left["id"],
                "source_b": right["source"],
                "id_b": right["id"],
                "score": score,
                "confiance": "élevée" if score >= 0.9 else "à vérifier",
                "decision": "revue_manuelle_requise",
            })
    return sorted(resultats, key=lambda candidate: (
        -candidate["score"], candidate["source_a"], candidate["id_a"],
        candidate["source_b"], candidate["id_b"],
    ))


def statistiques_comparatives(offres, statuts_sources, seuil=0.75):
    """Calcule les indicateurs source par source, sans additionner les annonces."""
    par_source = defaultdict(list)
    for offre in offres:
        if offre["source"] not in SOURCES:
            raise ValueError(f"Source non prise en charge : {offre['source']}")
        par_source[offre["source"]].append(offre)

    sources = {}
    for source in SOURCES:
        statut = statuts_sources.get(source, "non_connecte")
        disponibles = statut == "disponible"
        liste = par_source[source] if disponibles else []
        salaires = [
            _milieu_salaire(offre)
            for offre in liste
            if (offre["salary_min"] is not None or offre["salary_max"] is not None)
            and offre["salary_is_predicted"] is False
            and offre["salary_currency"] == "EUR"
            and offre["salary_period"] == "annual"
        ]
        salaires_declares = [
            offre for offre in liste
            if (offre["salary_min"] is not None or offre["salary_max"] is not None)
            and offre["salary_is_predicted"] is False
        ]
        salaires_predits = [
            offre for offre in liste
            if (offre["salary_min"] is not None or offre["salary_max"] is not None)
            and offre["salary_is_predicted"] is True
        ]
        salaires_non_qualifies = [
            offre for offre in liste
            if (offre["salary_min"] is not None or offre["salary_max"] is not None)
            and offre["salary_is_predicted"] is None
        ]
        competences = Counter(skill for offre in liste for skill in offre["skills"])
        taches = Counter(task for offre in liste for task in offre["tasks"])
        sources[source] = {
            "statut": statut,
            "nombre_offres": len(liste) if disponibles else None,
            "offres_avec_salaire": (
                len(salaires_declares) + len(salaires_predits) + len(salaires_non_qualifies)
                if disponibles else None
            ),
            "offres_avec_salaire_declare": len(salaires_declares) if disponibles else None,
            "offres_avec_salaire_estime": len(salaires_predits) if disponibles else None,
            "offres_avec_salaire_non_qualifie": len(salaires_non_qualifies) if disponibles else None,
            "salaire_moyen_annuel": round(sum(salaires) / len(salaires)) if salaires else None,
            "competences": [
                {"libelle": label, "nombre_offres": count}
                for label, count in competences.most_common(12)
            ],
            "taches": [
                {"libelle": label, "nombre_offres": count}
                for label, count in taches.most_common(12)
            ],
            "taches_disponibles": bool(taches),
        }

    sources_connectees = [source for source in SOURCES if sources[source]["statut"] == "disponible"]
    comparaison_possible = len(sources_connectees) >= 2
    candidats = candidats_doublons(
        [offre for offre in offres if offre["source"] in sources_connectees], seuil,
    ) if comparaison_possible else []
    return {
        "sources": sources,
        "doublons": {
            "statut": "calcule" if comparaison_possible else "non_calculable",
            "nombre_candidats": len(candidats) if comparaison_possible else None,
            "seuil": seuil,
            "candidats": candidats,
        },
    }
