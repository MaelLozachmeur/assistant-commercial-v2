# Métiers commerciaux — le marché de l'emploi, lu dans les offres

Site statique en français consacré à une sélection de métiers commerciaux. Il observe les offres France Travail de **11 codes ROME** couvrant l'assistanat et l'administration des ventes, la vente B2B et auprès de particuliers, la vente automobile, le technico-commercial, la vente à distance, la relation clientèle et le pilotage commercial.

Les codes et leurs libellés viennent du [référentiel ROME France Travail](https://github.com/France-Travail/mobiville/blob/main/api/src/assets/datas/unix_referentiel_code_rome_v346_utf8.xml) ; les groupes d'affichage sont propres au site. Les codes suivis sont **D1213**, **D1401**, **D1402**, **D1403**, **D1404**, **D1406**, **D1407**, **D1408**, **M1701**, **M1704** et **M1707**. Les fonctions grands comptes et business development restent dans le seul code ROME D1402. Le périmètre n'est pas exhaustif : les ventes au détail spécialisées et le conseil en information médicale sont notamment laissés de côté. Chaque offre active est dédoublonnée par son identifiant France Travail et classée selon le `romeCode` officiel de l'offre.

## Pages

| Page | Ce qu'elle présente |
|---|---|
| `index.html` | Filtres, indicateurs, carte, départements et contrats |
| `salaires.html` | Salaires bruts annoncés et estimation du net |
| `exigences.html` | Expérience, formation, outils et compétences |
| `recruteurs.html` | Employeurs, secteurs et dernières offres |
| `mouvement.html` | Historique des extractions et limites des chiffres |

## Actualisation quotidienne

La seule source d'offres est l'API officielle **France Travail — Offres d'emploi v2**. `scripts/extraire.py` interroge l'API pour chacun des codes ROME configurés dans `METIERS`, conserve les versions des annonces et écrit les offres actives dédoublonnées et la série historique. Chaque code est plafonné à **1 150 résultats récupérés** par extraction; le total annoncé par l'API reste enregistré séparément. Les pages signalent les codes au plafond et indiquent les catégories qui n'ont pas encore été collectées. `scripts/resumer.py` produit `data/resume.json`, consommé par les cinq pages HTML. Le workflow `.github/workflows/veille.yml` est planifié chaque jour à 05:00 UTC (07:00 à Paris en été, 06:00 en hiver) et peut également être lancé manuellement.

Pour activer la collecte sur GitHub :

1. Dans les paramètres du dépôt, ajoutez les secrets Actions `FT_CLIENT_ID` et `FT_CLIENT_SECRET` obtenus pour l'API France Travail.
2. Activez GitHub Pages si le site doit être publié.
3. Lancez **Actions → veille → Run workflow** après fusion pour extraire les codes et actualiser `data/resume.json`. Les catégories ajoutées au résumé restent indiquées « à collecter » jusqu'à leur première extraction; aucun chiffre n'est inventé pour les annonces non encore récupérées.

Les identifiants restent côté serveur dans les secrets GitHub Actions. Ils ne doivent jamais être placés dans une page HTML, un fichier de données publié ou un commit. En local, copiez `.env.example` vers `.env` et renseignez les mêmes variables; `.env` est ignoré par Git.

Le résumé publié contient les onze catégories, mais seules D1401 et D1402 ont été collectées à ce jour; les autres apparaissent « à collecter » jusqu'au prochain lancement du workflow. Leurs compteurs restent à zéro sans prétendre que l'API a été interrogée.

## Développement local

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Renseigner FT_CLIENT_ID et FT_CLIENT_SECRET dans .env
.venv\Scripts\python.exe scripts\extraire.py --verifier
.venv\Scripts\python.exe scripts\extraire.py
.venv\Scripts\python.exe scripts\resumer.py
.venv\Scripts\python.exe -m http.server 8125
```

Ouvrez ensuite `http://localhost:8125`. Le périmètre ROME, les libellés, groupes et choix cochés par défaut se configurent dans `scripts/extraire.py` (`METIERS`); la grille de compétences/mots-clés est dans `scripts/resumer.py` (`OUTILS`). Les pages lisent la taxonomie du résumé et les filtres, graphiques par métier et légende cartographique sont générés à partir de cette liste.

Les tests unitaires de la taxonomie, de la pagination plafonnée, de l'authentification de recherche et de la fusion des extractions s'exécutent avec :

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Interpréter les chiffres

La veille couvre le seul canal France Travail et une sélection de codes ROME, pas toutes les offres ni tous les intitulés possibles des métiers commerciaux. La limite de l'API est de 1 150 résultats par code et par extraction : si le total annoncé dépasse ce nombre, les statistiques décrivent les offres récupérées et les courbes d'évolution comptent les résultats collectés, sans extrapolation. Les nouvelles catégories n'ont pas d'historique avant leur première extraction. Les compétences sont repérées par une grille de mots-clés configurable, les salaires ne sont analysés que lorsqu'ils sont explicitement indiqués et leur estimation nette est indicative (brut annuel × 0,78 / 12, avant impôt). Les coordonnées approximatives au centre d'une commune ou d'un département ne donnent pas l'adresse de l'employeur.
