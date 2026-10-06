"""Collecte les offres WTTJ autorisées pour les statistiques comparatives."""
import json
import os
import re
from pathlib import Path

import requests

ENDPOINT = "https://www.welcomekit.co/api/v1/external/jobs/all"
PER_PAGE = 100
MAX_PAGES = 10000
TIMEOUT = 30
MOTIF_COMMERCIAL = re.compile(
    r"\b(?:account manager|business development|business developer|"
    r"customer success|key account|sales|commerciale?s?|vente|"
    r"vendeu(?:r|se)s?|technico[- ]commerciale?)\b",
    re.IGNORECASE,
)
MOTIF_TAXONOMIE = re.compile(
    r"(?:sales|commercial|account|business[_ -]?development|customer[_ -]?success)",
    re.IGNORECASE,
)


def _texte(value, field, index, required=False):
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Offre WTTJ {index}: champ {field!r} invalide.")
    return " ".join(value.split())


def _salaire_annuel(job, index):
    salaire = job.get("salary")
    if salaire is None:
        return None, None
    if not isinstance(salaire, dict):
        raise ValueError(f"Offre WTTJ {index}: champ 'salary' invalide.")
    if salaire.get("currency") != "EUR" or salaire.get("period") != "yearly":
        return None, None
    minimum, maximum = salaire.get("min"), salaire.get("max")
    if minimum is None or maximum is None:
        return None, None
    try:
        minimum, maximum = float(minimum), float(maximum)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Offre WTTJ {index}: bornes salariales non numériques.") from exc
    if minimum <= 0 or maximum <= 0 or minimum > maximum:
        raise ValueError(f"Offre WTTJ {index}: bornes salariales invalides.")
    return minimum, maximum


def normaliser_job(job, index):
    """Valide les champs documentés et ne conserve que les champs comparatifs nécessaires."""
    if not isinstance(job, dict):
        raise ValueError(f"Offre WTTJ {index}: l'élément JSON doit être un objet.")
    reference = _texte(job.get("reference"), "reference", index, required=True)
    title = _texte(job.get("name"), "name", index, required=True)
    status = _texte(job.get("status"), "status", index, required=True)
    if status != "published":
        return None
    profession = _texte(job.get("profession_reference"), "profession_reference", index)
    if not (MOTIF_COMMERCIAL.search(title)
            or MOTIF_TAXONOMIE.search(profession)):
        return None

    salary_min, salary_max = _salaire_annuel(job, index)
    return {
        "id": reference,
        "title": title,
        "company": "",
        "location": "",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "skills": [],
        "tasks": [],
    }


def _request_page(session, page):
    params = {"status": "published", "per_page": PER_PAGE}
    if page is not None:
        params["page"] = page
    try:
        response = session.get(
            ENDPOINT,
            params=params,
            headers={"Authorization": f"Bearer {os.environ['WTTJ_API_KEY']}"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Erreur réseau lors de l'appel à l'API WTTJ: {exc}") from exc

    if response.status_code == 401:
        raise RuntimeError("WTTJ a refusé l'authentification (HTTP 401); vérifier WTTJ_API_KEY.")
    if response.status_code == 403:
        raise RuntimeError(
            "WTTJ refuse l'accès (HTTP 403); /external/jobs/all exige un partenariat "
            "et le scope su_jobs_r."
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Erreur API WTTJ HTTP {response.status_code}.")
    try:
        jobs = response.json()
    except ValueError as exc:
        raise RuntimeError("La réponse WTTJ n'est pas un JSON valide.") from exc
    if not isinstance(jobs, list):
        raise RuntimeError("Schéma WTTJ invalide: la réponse attendue est un tableau JSON.")
    return jobs


def collecter(session=None):
    """Parcourt les pages documentées; la réponse d'une page est le tableau d'offres."""
    session = session or requests
    references = {}
    page = None
    pages = 0
    while True:
        if pages >= MAX_PAGES:
            raise RuntimeError(f"Pagination WTTJ interrompue après {MAX_PAGES} pages.")
        lot = _request_page(session, page)
        pages += 1
        for index, job in enumerate(lot):
            offre = normaliser_job(job, f"{pages}:{index}")
            if offre:
                references[offre["id"]] = offre
        if not lot:
            break
        page = 1 if page is None else page + 1
    return list(references.values()), pages


def _ecrire_sortie(path, payload):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporaire = destination.with_suffix(destination.suffix + ".tmp")
    temporaire.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporaire, destination)


def main():
    sortie = os.getenv("WTTJ_OUTPUT")
    if not sortie:
        raise SystemExit("WTTJ_OUTPUT doit désigner un fichier temporaire de sortie.")
    api_key = os.getenv("WTTJ_API_KEY")
    if not api_key:
        _ecrire_sortie(sortie, {"status": "non_configure", "offers": []})
        print("WTTJ_API_KEY absent : collecte WTTJ non configurée.")
        return

    os.environ["WTTJ_API_KEY"] = api_key
    try:
        offers, pages = collecter()
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    _ecrire_sortie(sortie, {
        "status": "disponible",
        "pages": pages,
        "offers": offers,
    })
    print(f"WTTJ: {len(offers)} offres commerciales retenues ({pages} page(s)).")


if __name__ == "__main__":
    main()
