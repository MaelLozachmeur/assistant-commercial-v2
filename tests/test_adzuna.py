import unittest
from unittest.mock import patch

from scripts.adzuna import AdzunaError, collecter, main, parser_offre
from scripts.comparer import normaliser_offre, statistiques_comparatives


class AdzunaTest(unittest.TestCase):
    def test_parser_preserve_source_salary_flag_and_minimal_fields(self):
        offre = parser_offre({
            "id": 123,
            "title": "  Commercial   B2B ",
            "company": {"display_name": "Acme"},
            "location": {"display_name": "Paris"},
            "created": "2026-11-03T10:00:00Z",
            "redirect_url": "https://www.adzuna.fr/annonce/123",
            "salary_min": 35000,
            "salary_max": 45000,
            "salary_is_predicted": 1,
            "description": "ne doit pas être conservée",
        }, "D1402")

        self.assertEqual(offre["id"], "123")
        self.assertEqual(offre["title"], "Commercial B2B")
        self.assertTrue(offre["salary_is_predicted"])
        self.assertEqual(offre["salary_currency"], "EUR")
        self.assertIsNone(offre["salary_period"])
        self.assertNotIn("description", offre)
        self.assertEqual(offre["redirect_url"], "https://www.adzuna.fr/annonce/123")

    def test_collecter_paginate_and_deduplicate_job_ids_from_fixture_pages(self):
        pages = [
            [{"id": "a", "title": "Commercial", "redirect_url": "https://adzuna.fr/a"},
             {"id": "b", "title": "Assistant commercial", "redirect_url": "https://adzuna.fr/b"}],
            [{"id": "b", "title": "Assistant commercial actualisé", "redirect_url": "https://adzuna.fr/b"},
             {"id": "c", "title": "Technico-commercial", "redirect_url": "https://adzuna.fr/c"}],
        ]
        appels = []

        def fake_get(url, **kwargs):
            appels.append((url, kwargs))
            page = int(url.rsplit("/", 1)[1])
            return type("Response", (), {
                "status_code": 200,
                "json": lambda self: {"results": pages[page - 1]},
            })()

        donnees = collecter(
            "id-test", "key-test", requetes=[("D1402", "commercial")],
            results_per_page=2, pages_max=2, get=fake_get, pause=lambda _delay: None,
        )

        self.assertEqual(len(appels), 2)
        self.assertEqual([int(appel[0].rsplit("/", 1)[1]) for appel in appels], [1, 2])
        self.assertEqual(len(donnees["offres"]), 3)
        self.assertEqual(donnees["offres"][1]["title"], "Assistant commercial")
        self.assertEqual(donnees["offres"][1]["romes"], ["D1402"])
        self.assertEqual(appels[0][1]["params"]["what"], "commercial")
        self.assertEqual(appels[0][1]["params"]["content-type"], "application/json")
        self.assertTrue(donnees["requetes"][0]["plafonnee"])

    def test_missing_credentials_writes_nonconfigured_status_without_api_call(self):
        for credentials in ((None, "key-test"), ("id-test", None)):
            with self.subTest(credentials=credentials), \
                 patch("scripts.adzuna.os.getenv", side_effect=credentials), \
                 patch("scripts.adzuna.ecrire_resultats") as ecrire, \
                 patch("scripts.adzuna.collecter") as collecter_mock:
                result = main()

            self.assertEqual(result, 0)
            self.assertEqual(ecrire.call_args.args[0]["status"], "non_configure")
            self.assertEqual(ecrire.call_args.args[0]["offres"], [])
            collecter_mock.assert_not_called()

    def test_api_auth_error_is_persisted_as_an_error_status(self):
        with patch("scripts.adzuna.os.getenv", side_effect=["id-test", "key-test"]), \
             patch("scripts.adzuna.collecter", side_effect=AdzunaError("Échec API Adzuna : HTTP 401.")), \
             patch("scripts.adzuna.ecrire_resultats") as ecrire:
            result = main()

        self.assertEqual(result, 1)
        self.assertEqual(ecrire.call_args.args[0]["status"], "erreur")
        self.assertIn("HTTP 401", ecrire.call_args.args[0]["message"])
        self.assertEqual(ecrire.call_args.args[0]["offres"], [])

    def test_auth_failure_does_not_include_credentials_in_error(self):
        def fake_get(_url, **_kwargs):
            return type("Response", (), {"status_code": 401})()

        with self.assertRaisesRegex(AdzunaError, "HTTP 401") as context:
            collecter(
                "secret-id", "secret-key", requetes=[("D1402", "commercial")],
                get=fake_get, pause=lambda _delay: None,
            )
        self.assertNotIn("secret-id", str(context.exception))
        self.assertNotIn("secret-key", str(context.exception))

    def test_duplicate_across_queries_keeps_one_offer_and_all_matching_roles(self):
        def fake_get(_url, **kwargs):
            term = kwargs["params"]["what"]
            offers = ([{"id": "shared", "title": "Commercial", "redirect_url": "https://adzuna.fr/shared"}]
                      if term == "first" else [
                          {"id": "shared", "title": "Commercial mis à jour", "redirect_url": "https://adzuna.fr/shared"},
                          {"id": "other", "title": "Autre", "redirect_url": "https://adzuna.fr/other"},
                      ])
            return type("Response", (), {
                "status_code": 200,
                "json": lambda self: {"results": offers},
            })()

        donnees = collecter(
            "id-test", "key-test", requetes=[("D1401", "first"), ("D1402", "second")],
            results_per_page=10, get=fake_get, pause=lambda _delay: None,
        )

        self.assertEqual(len(donnees["offres"]), 2)
        partagee = next(offre for offre in donnees["offres"] if offre["id"] == "shared")
        self.assertEqual(partagee["romes"], ["D1401", "D1402"])
        self.assertEqual(partagee["title"], "Commercial")

    def test_adzuna_salary_means_exclude_predicted_or_unconfirmed_periods(self):
        offers = [
            normaliser_offre("adzuna", {
                "id": "declared-unknown-period", "title": "Commercial",
                "salary_min": 40000, "salary_max": 50000, "salary_currency": "EUR",
                "salary_period": None, "salary_is_predicted": False,
            }),
            normaliser_offre("adzuna", {
                "id": "declared-annual", "title": "Commercial",
                "salary_min": 40000, "salary_max": 50000, "salary_currency": "EUR",
                "salary_period": "annual", "salary_is_predicted": False,
            }),
            normaliser_offre("adzuna", {
                "id": "predicted", "title": "Commercial", "salary_min": 60000,
                "salary_max": 60000, "salary_currency": "EUR",
                "salary_period": "annual", "salary_is_predicted": True,
            }),
        ]
        stats = statistiques_comparatives(
            offers,
            {"france_travail": "disponible", "wttj": "non_connecte", "adzuna": "disponible"},
        )["sources"]["adzuna"]

        self.assertEqual(stats["offres_avec_salaire_declare"], 2)
        self.assertEqual(stats["offres_avec_salaire_estime"], 1)
        self.assertEqual(stats["salaire_moyen_annuel"], 45000)


if __name__ == "__main__":
    unittest.main()
