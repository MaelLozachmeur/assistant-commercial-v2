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
| `comparaison.html` | Indicateurs par source, salaires, compétences et candidats doublons |

## Actualisation quotidienne

La source historique est l'API officielle **France Travail — Offres d'emploi v2** ([documentation](https://francetravail.io/data/api/offres-emploi)). `scripts/extraire.py` interroge l'API pour chacun des codes ROME configurés dans `METIERS`, conserve les versions des annonces et écrit les offres actives dédoublonnées et la série historique. Le schéma OpenAPI limite une page à 150 offres et autorise `range` jusqu'à `3000-3149`, soit **3 150 résultats par recherche** (contre 1 150 dans l'ancienne limite utilisée par le collecteur). Si le total France entière est supérieur, les paramètres documentés `minCreationDate`/`maxCreationDate` subdivisent récursivement la période en intervalles temporels contigus, à la seconde; les offres des intervalles sont fusionnées et dédoublonnées par identifiant. Cette méthode n'utilise pas le département et conserve donc les offres sans localisation. Le total annoncé par la recherche initiale et le nombre d'offres distinctes récupérées restent enregistrés séparément.

La terminaison est explicite : une fenêtre d'une seconde ne peut plus être subdivisée et le service ne permet pas de paginer au-delà de 3 150 résultats dans cette fenêtre. Si elle contient davantage d'offres, les résultats restent incomplets; le résumé signale le code et le nombre de segments encore plafonnés au lieu de les présenter comme exhaustifs. Si `Content-Range` manque, la collecte échoue plutôt que de déclarer un total inconnu exhaustif. Les changements d'offres pendant l'extraction peuvent aussi faire varier le résultat entre requêtes. Les pages signalent les codes incomplets et les catégories qui n'ont pas encore été collectées. `scripts/resumer.py` produit `data/resume.json`, consommé par les six pages HTML. Le workflow `.github/workflows/veille.yml` est planifié chaque jour à 05:00 UTC (07:00 à Paris en été, 06:00 en hiver) et peut également être lancé manuellement.

Le code de contrat France Travail `STG` est affiché sous **Stage**, avec un filtre dédié partagé entre les cinq pages d'analyse métier, et figure dans le dictionnaire des contrats du résumé.

### Comparer les sources et disponibilité WTTJ

`comparaison.html` affiche les nombres d'offres et salaires **séparément pour chaque source**, ainsi que les compétences explicites. La moyenne annuelle brute comparable est calculée sur les seules fourchettes déclarées, en EUR/an confirmé, puis moyennée arithmétiquement; les annonces sans salaire ne valent pas zéro. Les tâches ne sont pas structurées dans le résumé France Travail actuel et restent indiquées comme indisponibles.

Au 6 octobre 2026, aucune documentation publique officielle décrivant une API de consultation des offres WTTJ n'a été trouvée dans les pages officielles consultées ([site WTTJ](https://www.welcometothejungle.com/fr/), [page partenaires consultée](https://www.welcometothejungle.com/fr/partners)). La racine `https://api.welcometothejungle.com` ne fournit pas de documentation d'API. Cela ne permet pas de conclure qu'aucun accès privé partenaire n'existe; cela signifie qu'aucun accès public, schéma, mécanisme d'authentification, pagination, quota ou droit de réutilisation ne peut être confirmé ici. Le site ne récupère donc pas les annonces WTTJ, n'interroge aucun endpoint observé dans son code public et ne scrape pas ses pages. L'absence de données WTTJ est rendue par « non connecté »/« non calculable », jamais par un zéro inventé.

`scripts/comparer.py` contient le modèle canonique minimal et les statistiques comparatives pour les sources connectées; les adaptateurs de collecte sont séparés. Le rapprochement combine la similarité du titre (55 %), de l'employeur (20 %), du lieu (15 %) et du salaire (10 % uniquement lorsque devise, période et statut déclaré sont comparables). Un titre seul ne suffit pas; une proximité d'employeur ou de lieu est aussi requise. Les candidats sont scorés et signalés pour revue humaine, sans jamais fusionner ni retirer des offres des totaux de leur source. Seuls les identifiants, intitulés, employeurs, lieux, salaires et compétences/tâches utiles à ces calculs sont normalisés; les descriptions et coordonnées ne sont pas conservées par ce module.

### Source Adzuna

L'adaptateur `scripts/adzuna.py` interroge l'API REST officielle Adzuna ([présentation](https://developer.adzuna.com/overview), [recherche](https://developer.adzuna.com/docs/search)) pour la France (`fr`) avec une requête ciblée par chacun des onze codes ROME. Il collecte au plus deux pages de 50 annonces par requête (1 100 résultats maximum, 22 appels API par lancement), puis dédoublonne les annonces par identifiant dans `data/adzuna.json` en conservant tous les codes de recherche associés. Ce plafond est une limite de collecte locale, **pas** une affirmation sur le quota Adzuna; les requêtes qui atteignent le plafond sont marquées comme possiblement incomplètes. Le fichier ne conserve pas les descriptions : uniquement titre, employeur, localisation, date, codes de recherche, identifiant, fourchette de salaire, indicateur `salary_is_predicted` et lien `redirect_url`. La page de comparaison crédite Adzuna et relie chaque intitulé à l'annonce d'origine.

Les salaires Adzuna prédits sont identifiés comme estimations et séparés des salaires déclarés. La documentation publique consultée décrit les bornes `salary_min`/`salary_max` et l'indicateur `salary_is_predicted`, mais ne précise ni la devise renvoyée ni la périodicité de salaire dans la recherche. L'adaptateur associe EUR au pays demandé (`fr`), mais ne convertit ni n'annualise les nombres. Ils sont visibles avec cette réserve, mais exclus des moyennes annuelles et du rapprochement salarial tant que la devise et la périodicité ne sont pas confirmées. Une moyenne comparative n'est calculée que sur les salaires déclarés dont la devise est EUR et la période explicitement annualisée; elle est la moyenne arithmétique des milieux de fourchettes.

**Conditions avant activation/publication :** les pages publiques Adzuna consultées n'indiquent ni quota de requêtes, ni licence/droit de republication des annonces ou des champs, ni consigne complète d'attribution pour une republication dans un site public. Les conditions affichées lors de l'inscription et celles propres au compte API peuvent apporter ces précisions; les vérifier et obtenir l'autorisation de publier les champs avant d'ajouter les clés. Le tableau de bord crédite déjà Adzuna et renvoie vers chaque annonce comme précaution, mais cela ne remplace pas une vérification des conditions applicables. La couverture des recherches, quotas et droits de republication ne peut pas être garantie par ce dépôt.

Pour obtenir les identifiants, inscrivez-vous sur [developer.adzuna.com/signup](https://developer.adzuna.com/signup) et créez une application. Dans **GitHub → Settings → Secrets and variables → Actions → New repository secret**, créez exactement `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` avec les valeurs affichées par Adzuna. Ne partagez pas ces valeurs et ne les placez jamais dans un fichier versionné, `data/` ou le navigateur. Sans ces deux secrets, le workflow France Travail continue et Adzuna est indiqué « non configuré » sans résultats fictifs. Si l'API échoue (y compris erreur d'authentification), le statut d'erreur est visible, aucun résultat de repli n'est inventé et l'étape Adzuna ne bloque pas la publication France Travail.

Après vérification des conditions et ajout des secrets, activez GitHub Pages si nécessaire puis lancez **Actions → veille → Run workflow** après fusion. Le workflow quotidien collecte Adzuna en plus de France Travail et écrit les annonces dans `data/adzuna.json`, séparément des données France Travail; le résumé publié alimente ensuite `comparaison.html`. La pagination est volontairement bornée à deux pages par requête et la couverture dépend des termes de recherche, des annonces indexées et des règles de quota du compte.

Pour activer WTTJ, obtenir d'abord de WTTJ une documentation officielle et une autorisation écrite couvrant l'usage analytique et la republication des champs d'offres. Confirmer avec eux le périmètre géographique, les champs retournés (dont salaires, compétences et tâches), l'authentification exacte, les quotas/pagination, les durées de conservation et les droits d'affichage. Si un accès partenaire existe, demander les identifiants/jetons et permissions précis indiqués dans cette documentation, puis les ajouter comme secrets GitHub Actions uniquement. Les noms de secrets et les variables d'environnement ne sont volontairement pas prédéfinis : ils doivent reprendre le mécanisme documenté par WTTJ, sans identifiants devinés. Après validation des conditions, un adaptateur côté workflow pourra mapper uniquement ces champs autorisés vers le format canonique; aucun secret ne doit être publié dans `data/` ou envoyé au navigateur.

Pour activer la collecte sur GitHub :

1. Dans les paramètres du dépôt, ajoutez les secrets Actions `FT_CLIENT_ID` et `FT_CLIENT_SECRET` obtenus pour l'API France Travail.
2. Pour Adzuna, vérifiez d'abord les conditions applicables, puis ajoutez `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` comme secrets Actions. Cette source est facultative.
3. Activez GitHub Pages si le site doit être publié.
4. Lancez **Actions → veille → Run workflow** après fusion pour collecter les offres et actualiser `data/resume.json`. Les catégories France Travail non encore collectées restent « à collecter »; aucune donnée manquante n'est inventée.

Les identifiants restent côté serveur dans les secrets GitHub Actions. Ils ne doivent jamais être placés dans une page HTML, un fichier de données publié ou un commit. En local, copiez `.env.example` vers `.env` et renseignez les mêmes variables; `.env` est ignoré par Git.

Le résumé publié contient les onze catégories, mais seules D1401 et D1402 ont été collectées à ce jour; les autres apparaissent « à collecter » jusqu'au prochain lancement du workflow. Leurs compteurs restent à zéro sans prétendre que l'API a été interrogée. Le fichier de données actuellement commité date d'avant le nouveau partitionnement; ses codes plafonnés restent explicitement marqués comme extraits sans cette stratégie jusqu'à la prochaine collecte.

## Développement local

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Renseigner FT_CLIENT_ID et FT_CLIENT_SECRET; Adzuna est facultatif.
# Après vérification des conditions, renseigner ADZUNA_APP_ID et ADZUNA_APP_KEY pour l'activer.
.venv\Scripts\python.exe scripts\extraire.py --verifier
.venv\Scripts\python.exe scripts\extraire.py
.venv\Scripts\python.exe scripts\adzuna.py
.venv\Scripts\python.exe scripts\resumer.py
.venv\Scripts\python.exe -m http.server 8125
```

Ouvrez ensuite `http://localhost:8125`. Le périmètre ROME, les libellés, groupes et choix cochés par défaut se configurent dans `scripts/extraire.py` (`METIERS`); la grille de compétences/mots-clés est dans `scripts/resumer.py` (`OUTILS`). Les pages lisent la taxonomie du résumé et les filtres, graphiques par métier et légende cartographique sont générés à partir de cette liste.

Les tests unitaires de la taxonomie, du partitionnement temporel, des contrats, de l'authentification de recherche, de la fusion des extractions et des statistiques de comparaison s'exécutent avec :

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Interpréter les chiffres

La veille France Travail couvre une sélection de codes ROME, pas toutes les offres ni tous les intitulés possibles des métiers commerciaux. La limite de 3 150 résultats par recherche s'applique à chaque requête : le partitionnement par date de création permet de dépasser ce nombre par code lorsque les offres sont réparties sur plusieurs instants, sans garantir l'exhaustivité si un intervalle d'une seconde dépasse encore le plafond ou si l'API évolue pendant l'extraction. Les codes concernés gardent le total annoncé et le nombre effectivement récupéré; les courbes comptent les résultats collectés, sans extrapolation. Adzuna est une source facultative dont les requêtes/pagination sont plafonnées localement et dont la couverture et le quota de compte ne sont pas confirmés. Les nouvelles catégories France Travail n'ont pas d'historique avant leur première extraction. Les compétences sont repérées par une grille de mots-clés configurable, les salaires ne sont analysés que lorsqu'ils sont explicitement indiqués et leur estimation nette est indicative (brut annuel × 0,78 / 12, avant impôt). Les coordonnées approximatives au centre d'une commune ou d'un département ne donnent pas l'adresse de l'employeur. La page de comparaison ne contient pas de données WTTJ tant qu'un accès documenté et autorisé n'est pas obtenu.
