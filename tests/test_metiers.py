import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.comparer import candidats_doublons, normaliser_offre, statistiques_comparatives
from scripts.extraire import MAX_PAR_REQUETE, METIERS, code_rome, chercher, fusionner_actives
from scripts.resumer import REGEX_OUTILS, contrat_libelle, contrats_resume, metiers_resume


class MetiersTest(unittest.TestCase):
    def test_taxonomie_couvre_les_codes_commerciaux_retenus_avec_libelles_officiels(self):
        attendus = {
            "D1213": ("Vente en gros de matériel et équipement", "Vente B2B spécialisée", True),
            "D1401": ("Assistanat commercial", "Assistanat commercial", True),
            "D1402": ("Relation commerciale grands comptes et entreprises", "Vente et relation commerciale", True),
            "D1403": ("Relation commerciale auprès de particuliers", "Vente et relation commerciale", True),
            "D1404": ("Relation commerciale en vente de véhicules", "Vente et relation commerciale", True),
            "D1406": ("Management en force de vente", "Management commercial", True),
            "D1407": ("Relation technico-commerciale", "Technico-commercial", True),
            "D1408": ("Téléconseil et télévente", "Vente à distance", True),
            "M1701": ("Administration des ventes", "Administration des ventes", True),
            "M1704": ("Management relation clientèle", "Relation clientèle", True),
            "M1707": ("Stratégie commerciale", "Stratégie commerciale", True),
        }
        self.assertEqual(METIERS, attendus)
        self.assertEqual(len({metier[0] for metier in METIERS.values()}), len(METIERS))

    def test_code_officiel_de_offre_est_prioritaire(self):
        self.assertEqual(code_rome({"romeCode": "D1407"}, "D1401"), "D1407")
        self.assertEqual(code_rome({}, "D1401"), "D1401")
        self.assertEqual(code_rome({"romeCode": "X9999"}, "D1401"), "D1401")

    def test_resume_distingue_collecte_absente_et_plafond_api(self):
        metiers = metiers_resume(
            {"offre-1": "D1401", "offre-2": "D1407"},
            [
                {"rome": "D1401", "total": "1310", "recuperees": "1150", "segments_plafonnes": "1"},
                {"rome": "D1407", "total": "1", "recuperees": "1"},
            ],
        )
        par_code = {metier["code"]: metier for metier in metiers}
        self.assertTrue(par_code["D1401"]["plafonnee"])
        self.assertTrue(par_code["D1401"]["partitionnement_applique"])
        self.assertEqual(par_code["D1401"]["actives"], 1)
        self.assertTrue(par_code["D1407"]["collecte"])
        self.assertFalse(par_code["D1407"]["plafonnee"])
        self.assertFalse(par_code["D1402"]["collecte"])
        self.assertIsNone(par_code["D1402"]["plafonnee"])

    @patch("scripts.extraire.time.sleep")
    @patch("scripts.extraire.requests.get")
    def test_partitionnement_temporel_depasse_1150_et_dedoublonne(self, get, _sleep):
        sources = [
            {"id": f"ancien-{i}", "dateCreation": "2000-01-01T00:00:00Z"} for i in range(600)
        ] + [
            {"id": f"recent-{i}", "dateCreation": "2026-01-01T00:00:00Z"} for i in range(600)
        ]

        def page(*args, **kwargs):
            params = kwargs["params"]
            debut, fin = map(int, params["range"].split("-"))
            minimum = datetime.strptime(params["minCreationDate"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            maximum = datetime.strptime(params["maxCreationDate"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            correspondantes = [
                o for o in sources
                if minimum <= datetime.strptime(o["dateCreation"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= maximum
            ]
            lot = correspondantes[debut:fin + 1]
            return type("Reponse", (), {
                "status_code": 206,
                "headers": {"Content-Range": f"offres {debut}-{debut + len(lot) - 1}/{len(correspondantes)}"},
                "json": lambda self: {"resultats": lot},
            })()

        get.side_effect = page
        offres, total, segments_plafonnes = chercher(
            "jeton-test", {"codeROME": "D1401"}, maximum=1150,
        )

        self.assertEqual(MAX_PAR_REQUETE, 3150)
        self.assertEqual(len(offres), 1200)
        self.assertEqual(len({o["id"] for o in offres}), 1200)
        self.assertEqual(total, 1200)
        self.assertEqual(segments_plafonnes, 0)
        self.assertGreater(get.call_count, 2)
        self.assertTrue(all(
            "minCreationDate" in appel.kwargs["params"]
            and "maxCreationDate" in appel.kwargs["params"]
            for appel in get.call_args_list
        ))
        self.assertTrue(all(
            appel.kwargs["headers"]["Authorization"] == "Bearer jeton-test"
            for appel in get.call_args_list
        ))

    @patch("scripts.extraire.time.sleep")
    @patch("scripts.extraire.requests.get")
    def test_pagination_utilise_la_borne_3149_du_schema_api(self, get, _sleep):
        sources = [{"id": str(i)} for i in range(3150)]

        def page(*args, **kwargs):
            debut, fin = map(int, kwargs["params"]["range"].split("-"))
            lot = sources[debut:fin + 1]
            return type("Reponse", (), {
                "status_code": 206,
                "headers": {"Content-Range": f"offres {debut}-{debut + len(lot) - 1}/3150"},
                "json": lambda self: {"resultats": lot},
            })()

        get.side_effect = page
        offres, total, segments_plafonnes = chercher("jeton-test", {"codeROME": "D1401"})

        self.assertEqual(len(offres), total)
        self.assertEqual(total, 3150)
        self.assertEqual(segments_plafonnes, 0)
        self.assertEqual(get.call_args_list[-1].kwargs["params"]["range"], "3000-3149")

    @patch("scripts.extraire.time.sleep")
    @patch("scripts.extraire.requests.get")
    def test_signale_un_segment_indivisible_qui_depasse_encore_le_plafond(self, get, _sleep):
        instant = "2026-01-01T00:00:00Z"
        sources = [{"id": str(i), "dateCreation": instant} for i in range(4)]

        def page(*args, **kwargs):
            params = kwargs["params"]
            debut, fin = map(int, params["range"].split("-"))
            correspondantes = [
                o for o in sources if params["minCreationDate"] <= o["dateCreation"] <= params["maxCreationDate"]
            ]
            lot = correspondantes[debut:fin + 1]
            return type("Reponse", (), {
                "status_code": 206,
                "headers": {"Content-Range": f"offres {debut}-{debut + len(lot) - 1}/{len(correspondantes)}"},
                "json": lambda self: {"resultats": lot},
            })()

        get.side_effect = page
        resultats, total, segments_plafonnes = chercher(
            "jeton-test", {"codeROME": "D1401"}, pas=2, maximum=3,
        )

        self.assertEqual(total, 4)
        self.assertEqual(len(resultats), 3)
        self.assertEqual(segments_plafonnes, 1)

    def test_grille_de_competences_couvre_les_roles_grands_comptes(self):
        self.assertTrue(REGEX_OUTILS["Négociation et vente"].search("négociation commerciale"))
        self.assertTrue(REGEX_OUTILS["Gestion de comptes clés"].search("gestion des grands comptes"))

    def test_fusion_remplace_les_lignes_relancees_et_dedoublonne(self):
        existantes = [
            ("D1401", "partagee", "2026-09-28"),
            ("D1402", "autre", "2026-09-28"),
        ]
        nouvelles = [
            ("D1402", "partagee", "2026-09-29"),
            ("D1402", "nouvelle", "2026-09-29"),
        ]

        fusion = fusionner_actives(existantes, nouvelles, {"D1401", "D1402"})

        self.assertEqual(len(fusion), len({ligne[1] for ligne in fusion}))
        self.assertEqual(
            fusion,
            [
                ("D1402", "nouvelle", "2026-09-29"),
                ("D1402", "partagee", "2026-09-29"),
            ],
        )

    def test_relance_partielle_conserve_les_autres_codes_et_dedoublonne(self):
        existantes = [
            ("D1401", "assistant", "2026-09-28"),
            ("D1402", "grands-comptes", "2026-09-28"),
            ("D1401", "grands-comptes", "2026-09-27"),
        ]

        fusion = fusionner_actives(existantes, [], {"D1401"})

        self.assertEqual(fusion, [("D1402", "grands-comptes", "2026-09-28")])

    def test_code_api_stage_est_present_dans_les_resumes_et_filtres(self):
        self.assertEqual(contrat_libelle("STG"), "Stage")
        self.assertEqual(contrats_resume([])["STG"], "Stage")

        source = (Path(__file__).resolve().parent.parent / "assets" / "commun.js").read_text(encoding="utf-8")
        self.assertIn('["stage", "Stage"]', source)
        self.assertIn('if (c === "STG") return "stage";', source)
        self.assertIn('memoC.push("stage")', source)
        for page in ("index.html", "salaires.html", "exigences.html", "recruteurs.html", "mouvement.html", "comparaison.html"):
            contenu = (Path(__file__).resolve().parent.parent / page).read_text(encoding="utf-8")
            self.assertIn("assets/commun.js", contenu)

    def test_normalisation_comparative_ne_garde_que_les_champs_utiles(self):
        offre = normaliser_offre("france_travail", {
            "id": "  ft-1 ",
            "title": "Commercial·e B2B",
            "company": "Acme",
            "location": "Paris",
            "salary_min": 40000,
            "salary_max": 50000,
            "skills": ["CRM", "CRM", ""],
            "tasks": ["Prospecter"],
            "description": "texte non nécessaire",
            "email": "personne@example.test",
        })

        self.assertEqual(offre["id"], "ft-1")
        self.assertEqual(offre["skills"], ["CRM"])
        self.assertEqual(offre["tasks"], ["Prospecter"])
        self.assertNotIn("description", offre)
        self.assertNotIn("email", offre)
        with self.assertRaises(ValueError):
            normaliser_offre("wttj", {"id": "sans-titre"})
        with self.assertRaises(ValueError):
            normaliser_offre("wttj", {
                "id": "salaire-incomplet", "title": "Commercial",
                "salary_min": 40000,
            })

    def test_candidats_doublons_sont_inter_sources_scores_et_non_fusionnes(self):
        ft = normaliser_offre("france_travail", {
            "id": "ft-1", "title": "Commercial B2B H/F", "company": "Acme Conseil",
            "location": "Paris", "salary_min": 40000, "salary_max": 50000,
        })
        wttj = normaliser_offre("wttj", {
            "id": "wttj-9", "title": "Commercial B2B", "company": "Acme Conseil",
            "location": "Paris", "salary_min": 42000, "salary_max": 48000,
        })
        different = normaliser_offre("wttj", {
            "id": "wttj-10", "title": "Commercial B2B", "company": "Autre société",
            "location": "Lyon",
        })

        candidats = candidats_doublons([ft, wttj, different])

        self.assertEqual(len(candidats), 1)
        self.assertEqual(candidats[0]["france_travail_id"], "ft-1")
        self.assertEqual(candidats[0]["wttj_id"], "wttj-9")
        self.assertEqual(candidats[0]["confiance"], "élevée")
        self.assertEqual(candidats[0]["decision"], "revue_manuelle_requise")
        self.assertEqual(candidats_doublons([ft, ft]), [])

    def test_statistiques_comparatives_separent_les_sources_et_ne_simulent_pas_wttj(self):
        ft_offres = [
            normaliser_offre("france_travail", {
                "id": "ft-1", "title": "Commercial", "salary_min": 40000,
                "salary_max": 50000, "skills": ["CRM"],
            }),
            normaliser_offre("france_travail", {
                "id": "ft-2", "title": "Chargé commercial", "salary_min": 50000,
                "salary_max": 50000, "skills": ["CRM", "Négociation"],
            }),
        ]

        resume = statistiques_comparatives(
            ft_offres,
            {"france_travail": "disponible", "wttj": "non_connecte"},
        )

        self.assertEqual(resume["sources"]["france_travail"]["nombre_offres"], 2)
        self.assertEqual(resume["sources"]["france_travail"]["salaire_moyen_annuel"], 47500)
        self.assertEqual(resume["sources"]["france_travail"]["competences"][0],
                         {"libelle": "CRM", "nombre_offres": 2})
        self.assertFalse(resume["sources"]["france_travail"]["taches_disponibles"])
        self.assertEqual(resume["sources"]["wttj"]["statut"], "non_connecte")
        self.assertIsNone(resume["sources"]["wttj"]["nombre_offres"])
        self.assertIsNone(resume["sources"]["wttj"]["salaire_moyen_annuel"])
        self.assertEqual(resume["doublons"]["statut"], "non_calculable")
        self.assertIsNone(resume["doublons"]["nombre_candidats"])
        self.assertEqual(resume["doublons"]["candidats"], [])

    def test_etats_vides_distinguent_zero_reel_et_source_non_connectee(self):
        resume = statistiques_comparatives([], {
            "france_travail": "disponible",
            "wttj": "non_connecte",
        })

        self.assertEqual(resume["sources"]["france_travail"]["nombre_offres"], 0)
        self.assertIsNone(resume["sources"]["france_travail"]["salaire_moyen_annuel"])
        self.assertIsNone(resume["sources"]["wttj"]["nombre_offres"])
        self.assertEqual(resume["doublons"]["statut"], "non_calculable")

        deux_sources = statistiques_comparatives([], {
            "france_travail": "disponible",
            "wttj": "disponible",
        })
        self.assertEqual(deux_sources["doublons"]["statut"], "calcule")
        self.assertEqual(deux_sources["doublons"]["nombre_candidats"], 0)

    def test_page_comparaison_affiche_les_etats_vides_sans_api_wttj_devinee(self):
        page = (Path(__file__).resolve().parent.parent / "comparaison.html").read_text(encoding="utf-8")
        self.assertIn("Non calculable tant que les deux sources", page)
        self.assertIn("aucune offre ni statistique WTTJ n'est inventée", page)
        self.assertNotIn("api.welcometothejungle.com/", page)
        source = (Path(__file__).resolve().parent.parent / "assets" / "commun.js").read_text(encoding="utf-8")
        self.assertIn("options.sansFiltres", source)
        self.assertIn("{ sansFiltres: true }", page)


if __name__ == "__main__":
    unittest.main()
