import unittest

from scripts.extraire import METIERS, code_rome, fusionner_actives
from scripts.resumer import REGEX_OUTILS


class MetiersTest(unittest.TestCase):
    def test_taxonomie_couvre_assistanat_et_developpement_commercial(self):
        self.assertEqual(
            METIERS["D1401"],
            ("Assistant(e) commercial(e)", "Assistant commercial", True),
        )
        self.assertEqual(
            METIERS["D1402"],
            (
                "Responsable commercial(e) grands comptes / business developer",
                "Développement commercial",
                True,
            ),
        )

    def test_code_officiel_de_offre_est_prioritaire(self):
        self.assertEqual(code_rome({"romeCode": "D1402"}, "D1401"), "D1402")
        self.assertEqual(code_rome({}, "D1401"), "D1401")
        self.assertEqual(code_rome({"romeCode": "X9999"}, "D1401"), "D1401")

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
