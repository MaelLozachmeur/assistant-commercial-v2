"""Collecte limitée de résultats de recherche depuis l'API officielle Adzuna."""
import json
import math
import os
from datetime import date
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")

API_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
PAYS = "fr"
RESULTATS_PAR_PAGE = 50
PAGES_MAX = 2
PAUSE_API = 0.25
REQUETES = (
    ("D1213", "commercial matériel B2B"),
    ("D1401", "assistant commercial"),
    ("D1402", "commercial grands comptes"),
    ("D1403", "commercial vente"),
    ("D1404", "commercial automobile"),
    ("D1406", "manager commercial"),
    ("D1407", "technico-commercial"),
    ("D1408", "télévendeur"),
    ("M1701", "administration des ventes"),
    ("M1704", "responsable relation client"),
    ("M1707", "stratégie commerciale"),
)


class AdzunaError(RuntimeError):
    """Erreur API sans URL ni identifiant d'accès dans le message."""


def _nombre_salaire(valeur):
    if valeur is None:
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError) as exc:
        raise AdzunaError("L'API a renvoyé un salaire non numérique.") from exc
    if not math.isfinite(nombre) or nombre <= 0:
        raise AdzunaError("L'API a renvoyé un salaire invalide.")
    return nombre


def _salaire_est_predit(valeur):
    if valeur in (0, "0", False):
        return False
    if valeur in (1, "1", True):
        return True
    return None


def parser_offre(offre, rome):
    """Ne conserve que les champs nécessaires à l'affichage et à la comparaison."""
    if not isinstance(offre, dict):
        raise AdzunaError("L'API a renvoyé une annonce au format inattendu.")
    identifiant = offre.get("id")
    titre = " ".join(str(offre.get("title") or "").split())
    lien = offre.get("redirect_url")
    if identifiant in (None, "") or not titre:
        raise AdzunaError("Une annonce Adzuna ne contient pas d'identifiant ou de titre.")
    if not isinstance(lien, str) or urlparse(lien).scheme not in ("http", "https") or not urlparse(lien).netloc:
        raise AdzunaError("Une annonce Adzuna ne contient pas de lien source HTTP valide.")

    bas, haut = _nombre_salaire(offre.get("salary_min")), _nombre_salaire(offre.get("salary_max"))
    if bas is not None and haut is not None and bas > haut:
        raise AdzunaError("L'API a renvoyé une fourchette de salaire inversée.")
    company = offre.get("company") or {}
    location = offre.get("location") or {}
    if not isinstance(company, dict) or not isinstance(location, dict):
        raise AdzunaError("L'API a renvoyé un employeur ou un lieu au format inattendu.")
    return {
        "id": str(identifiant),
        "rome": rome,
        "title": titre,
        "company": " ".join(str(company.get("display_name") or "").split()),
        "location": " ".join(str(location.get("display_name") or "").split()),
        "created": str(offre.get("created") or "")[:10],
        "redirect_url": lien,
        "salary_min": bas,
        "salary_max": haut,
        "salary_is_predicted": _salaire_est_predit(offre.get("salary_is_predicted")),
        "salary_currency": "EUR",
        "salary_period": None,
    }


def collecter(app_id, app_key, pays=PAYS, requetes=REQUETES, pages_max=PAGES_MAX,
              results_per_page=RESULTATS_PAR_PAGE, get=None, pause=None):
    """Recherche les annonces françaises en plafonnant le volume d'appels quotidien."""
    if not app_id or not app_key:
        raise ValueError("Les identifiants Adzuna sont obligatoires pour collecter.")
    get = get or requests.get
    pause = pause or time.sleep
    offres, requetes_effectuees = {}, []
    for rome, termes in requetes:
        nombre_requete = 0
        total_annonce = None
        plafonnee = True
        pages_recues = 0
        for page in range(1, pages_max + 1):
            pause(PAUSE_API)
            try:
                response = get(
                    API_URL.format(country=pays, page=page),
                    params={
                        "app_id": app_id,
                        "app_key": app_key,
                        "results_per_page": results_per_page,
                        "what": termes,
                        "content-type": "application/json",
                    },
                    headers={"Accept": "application/json"},
                    timeout=30,
                )
            except requests.RequestException as exc:
                raise AdzunaError(f"Échec réseau Adzuna ({type(exc).__name__}).") from None
            if response.status_code != 200:
                raise AdzunaError(f"Échec API Adzuna : HTTP {response.status_code}.")
            try:
                payload = response.json()
            except (ValueError, json.JSONDecodeError):
                raise AdzunaError("L'API Adzuna a renvoyé un JSON invalide.") from None
            results = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(results, list):
                raise AdzunaError("La réponse Adzuna ne contient pas de liste results.")
            pages_recues += 1
            nombre_requete += len(results)
            if isinstance(payload.get("count"), int):
                total_annonce = payload["count"]
            for raw in results:
                offre = parser_offre(raw, rome)
                existante = offres.get(offre["id"])
                if existante:
                    if rome not in existante["romes"]:
                        existante["romes"].append(rome)
                else:
                    offre["romes"] = [rome]
                    offres[offre["id"]] = offre
            if len(results) < results_per_page:
                plafonnee = False
                break
        requetes_effectuees.append({
            "rome": rome,
            "termes": termes,
            "resultats_recus": nombre_requete,
            "pages_recues": pages_recues,
            "total_annonce": total_annonce,
            "plafonnee": plafonnee and (
                total_annonce is None or total_annonce > pages_max * results_per_page
                or pages_recues == pages_max
            ),
        })
    return {
        "date": date.today().isoformat(),
        "source": "Adzuna API",
        "status": "disponible",
        "requete": {
            "pays": pays,
            "pages_max_par_requete": pages_max,
            "resultats_max_par_requete": pages_max * results_per_page,
        },
        "requetes": requetes_effectuees,
        "offres": list(offres.values()),
    }


def ecrire_resultats(donnees):
    (RACINE / "data").mkdir(exist_ok=True)
    (RACINE / "data" / "adzuna.json").write_text(
        json.dumps(donnees, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main():
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        ecrire_resultats({
            "date": date.today().isoformat(),
            "source": "Adzuna API",
            "status": "non_configure",
            "message": "Secrets ADZUNA_APP_ID et/ou ADZUNA_APP_KEY absents.",
            "offres": [],
        })
        print("Adzuna non configuré : ajoutez ADZUNA_APP_ID et ADZUNA_APP_KEY dans les secrets Actions.")
        return 0

    try:
        donnees = collecter(app_id, app_key)
    except AdzunaError as exc:
        ecrire_resultats({
            "date": date.today().isoformat(),
            "source": "Adzuna API",
            "status": "erreur",
            "message": str(exc),
            "offres": [],
        })
        print(f"Adzuna : {exc}", file=sys.stderr)
        return 1
    ecrire_resultats(donnees)
    print(f"Adzuna : {len(donnees['offres'])} annonces uniques enregistrées dans data/adzuna.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
