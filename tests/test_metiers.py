import unittest
from unittest.mock import patch

from scripts.extraire import MAX_PAR_ROME, METIERS, code_rome, chercher, fusionner_actives
from scripts.resumer import REGEX_OUTILS, metiers_resume


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
                {"rome": "D1401", "total": "1310", "recuperees": "1150"},
                {"rome": "D1407", "total": "1", "recuperees": "1"},
            ],
        )
        par_code = {metier["code"]: metier for metier in metiers}
        self.assertTrue(par_code["D1401"]["plafonnee"])
        self.assertEqual(par_code["D1401"]["actives"], 1)
        self.assertTrue(par_code["D1407"]["collecte"])
        self.assertFalse(par_code["D1407"]["plafonnee"])
        self.assertFalse(par_code["D1402"]["collecte"])
        self.assertIsNone(par_code["D1402"]["plafonnee"])

    @patch("scripts.extraire.time.sleep")
    @patch("scripts.extraire.requests.get")
    def test_pagination_transmet_le_token_et_respecte_le_plafond(self, get, _sleep):
        def page(*args, **kwargs):
            debut, fin = map(int, kwargs["params"]["range"].split("-"))
            nombre = max(0, min(fin + 1, 1200) - debut)
            return type("Reponse", (), {
                "status_code": 206,
                "headers": {"Content-Range": f"offres {debut}-{debut + nombre - 1}/1200"},
                "json": lambda self: {"resultats": [{"id": str(i)} for i in range(nombre)]},
            })()

        get.side_effect = page
        offres, total = chercher("secret-du-test", {"codeROME": "D1401"})

        self.assertEqual(MAX_PAR_ROME, 1150)
        self.assertEqual(len(offres), MAX_PAR_ROME)
        self.assertEqual(total, 1200)
        self.assertEqual(get.call_count, 8)
        self.assertEqual(
            [appel.kwargs["params"]["range"] for appel in get.call_args_list],
            [f"{debut}-{min(debut + 149, MAX_PAR_ROME - 1)}" for debut in range(0, MAX_PAR_ROME, 150)],
        )
        self.assertTrue(all(
            appel.kwargs["headers"]["Authorization"] == "Bearer secret-du-test"
            for appel in get.call_args_list
        ))

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

        self.assertEqual(
            fusion,
            [
                ("D1402", "grands-comptes", "2026-09-28"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
