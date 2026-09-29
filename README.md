# Assistant commercial — le marché de l'emploi, lu dans les offres

Site statique en français consacré au métier d'assistant commercial. Il observe les offres France Travail du code ROME **D1401 — Assistanat commercial** et présente leur répartition géographique, les salaires affichés, les compétences mentionnées, les recruteurs et l'évolution des extractions.

## Pages

| Page | Ce qu'elle présente |
|---|---|
| `index.html` | Filtres, indicateurs, carte, départements et contrats |
| `salaires.html` | Salaires bruts annoncés et estimation du net |
| `exigences.html` | Expérience, formation, outils et compétences |
| `recruteurs.html` | Employeurs, secteurs et dernières offres |
| `mouvement.html` | Historique des extractions et limites des chiffres |

## Actualisation quotidienne

La source existe déjà : l'API officielle **France Travail — Offres d'emploi v2**. `scripts/extraire.py` interroge l'API avec le code ROME configuré dans `METIERS`, conserve les versions des annonces et écrit les offres actives et la série historique. `scripts/resumer.py` produit `data/resume.json`, consommé par les cinq pages HTML. Le workflow `.github/workflows/veille.yml` est planifié chaque jour à 05:00 UTC (07:00 à Paris en été, 06:00 en hiver) et peut également être lancé manuellement.

Pour activer la collecte sur GitHub :

1. Dans les paramètres du dépôt, ajoutez les secrets Actions `FT_CLIENT_ID` et `FT_CLIENT_SECRET` obtenus pour l'API France Travail.
2. Activez GitHub Pages si le site doit être publié.
3. Lancez **Actions → veille → Run workflow** pour produire le premier résumé D1401 sans attendre la prochaine exécution planifiée.

Les identifiants restent côté serveur dans les secrets GitHub Actions. Ils ne doivent jamais être placés dans une page HTML, un fichier de données publié ou un commit. En local, copiez `.env.example` vers `.env` et renseignez les mêmes variables; `.env` est ignoré par Git.

Si le résumé déployé ne contient pas encore le code D1401, le site masque volontairement les anciennes statistiques d'un autre périmètre et affiche les étapes pour lancer la collecte. Il ne remplace pas les données absentes par des chiffres d'exemple.

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

Ouvrez ensuite `http://localhost:8125`. Le périmètre ROME et son libellé se configurent dans `scripts/extraire.py` (`METIERS`); la grille de compétences/mots-clés est dans `scripts/resumer.py` (`OUTILS`).

## Interpréter les chiffres

La veille couvre le seul canal France Travail et la requête ROME D1401; elle ne représente pas toutes les offres ni tous les intitulés possibles du métier. Les compétences sont repérées par une grille de mots-clés configurable, les salaires ne sont analysés que lorsqu'ils sont explicitement indiqués et leur estimation nette est indicative (brut annuel × 0,78 / 12, avant impôt). Les coordonnées approximatives au centre d'une commune ou d'un département ne donnent pas l'adresse de l'employeur.
