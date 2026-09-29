# Métiers commerciaux — le marché de l'emploi, lu dans les offres

Site statique en français consacré aux métiers commerciaux. Il observe les offres France Travail des codes ROME **D1401 — Assistanat commercial** et **D1402 — Relation commerciale grands comptes et entreprises**, puis présente leur répartition géographique, les salaires affichés, les compétences mentionnées, les recruteurs et l'évolution des extractions.

Le code D1402 couvre ici les fonctions commerciales grands comptes et business development. Elles restent regroupées sous ce code ROME unique, plutôt que d'être ajoutées une seconde fois sous des intitulés voisins. Chaque offre active est dédoublonnée par son identifiant France Travail et classée selon le `romeCode` officiel de l'offre.

## Pages

| Page | Ce qu'elle présente |
|---|---|
| `index.html` | Filtres, indicateurs, carte, départements et contrats |
| `salaires.html` | Salaires bruts annoncés et estimation du net |
| `exigences.html` | Expérience, formation, outils et compétences |
| `recruteurs.html` | Employeurs, secteurs et dernières offres |
| `mouvement.html` | Historique des extractions et limites des chiffres |

## Actualisation quotidienne

La seule source d'offres est l'API officielle **France Travail — Offres d'emploi v2**. `scripts/extraire.py` interroge l'API pour chacun des codes ROME configurés dans `METIERS`, conserve les versions des annonces et écrit les offres actives dédoublonnées et la série historique. `scripts/resumer.py` produit `data/resume.json`, consommé par les cinq pages HTML. Le workflow `.github/workflows/veille.yml` est planifié chaque jour à 05:00 UTC (07:00 à Paris en été, 06:00 en hiver) et peut également être lancé manuellement.

Pour activer la collecte sur GitHub :

1. Dans les paramètres du dépôt, ajoutez les secrets Actions `FT_CLIENT_ID` et `FT_CLIENT_SECRET` obtenus pour l'API France Travail.
2. Activez GitHub Pages si le site doit être publié.
3. Lancez **Actions → veille → Run workflow** après fusion pour extraire les deux codes et actualiser `data/resume.json`. Le résumé actuellement commité ne sera élargi qu'après cette extraction; aucun chiffre n'est inventé pour le nouveau périmètre.

Les identifiants restent côté serveur dans les secrets GitHub Actions. Ils ne doivent jamais être placés dans une page HTML, un fichier de données publié ou un commit. En local, copiez `.env.example` vers `.env` et renseignez les mêmes variables; `.env` est ignoré par Git.

Après le changement de périmètre, les pages n'affichent que les métiers réellement présents dans `data/resume.json`. Tant que l'extraction élargie n'a pas été exécutée, le résumé publié peut encore ne contenir que D1401; il ne remplace pas les données absentes par des chiffres d'exemple.

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

Les tests unitaires de la fusion des extractions et de la taxonomie s'exécutent avec :

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Interpréter les chiffres

La veille couvre le seul canal France Travail et les seuls codes ROME D1401 et D1402; elle ne représente pas toutes les offres ni tous les intitulés possibles des métiers commerciaux. Les compétences sont repérées par une grille de mots-clés configurable, les salaires ne sont analysés que lorsqu'ils sont explicitement indiqués et leur estimation nette est indicative (brut annuel × 0,78 / 12, avant impôt). Les coordonnées approximatives au centre d'une commune ou d'un département ne donnent pas l'adresse de l'employeur. L'historique D1402 ne commence qu'à partir de sa première extraction; les graphiques de tendance n'assimilent pas les dates antérieures à des zéros.
