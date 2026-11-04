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

La source principale reste l'API officielle **France Travail — Offres d'emploi v2** ([documentation](https://francetravail.io/data/api/offres-emploi)). `scripts/extraire.py` interroge l'API pour chacun des codes ROME configurés dans `METIERS`, conserve les versions des annonces et écrit les offres actives dédoublonnées et la série historique. Le schéma OpenAPI limite une page à 150 offres et autorise `range` jusqu'à `3000-3149`, soit **3 150 résultats par recherche** (contre 1 150 dans l'ancienne limite utilisée par le collecteur). Si le total France entière est supérieur, les paramètres documentés `minCreationDate`/`maxCreationDate` subdivisent récursivement la période en intervalles temporels contigus, à la seconde; les offres des intervalles sont fusionnées et dédoublonnées par identifiant. Cette méthode n'utilise pas le département et conserve donc les offres sans localisation. Le total annoncé par la recherche initiale et le nombre d'offres distinctes récupérées restent enregistrés séparément.

La terminaison est explicite : une fenêtre d'une seconde ne peut plus être subdivisée et le service ne permet pas de paginer au-delà de 3 150 résultats dans cette fenêtre. Si elle contient davantage d'offres, les résultats restent incomplets; le résumé signale le code et le nombre de segments encore plafonnés au lieu de les présenter comme exhaustifs. Si `Content-Range` manque, la collecte échoue plutôt que de déclarer un total inconnu exhaustif. Les changements d'offres pendant l'extraction peuvent aussi faire varier le résultat entre requêtes. Les pages signalent les codes incomplets et les catégories qui n'ont pas encore été collectées. `scripts/resumer.py` produit `data/resume.json`, consommé par les six pages HTML. Le workflow `.github/workflows/veille.yml` est planifié chaque jour à 05:00 UTC (07:00 à Paris en été, 06:00 en hiver) et peut également être lancé manuellement.

Le code de contrat France Travail `STG` est affiché sous **Stage**, avec un filtre dédié partagé entre les cinq pages d'analyse métier, et figure dans le dictionnaire des contrats du résumé.

### Comparer les sources et disponibilité WTTJ

`comparaison.html` affiche les nombres d'offres et salaires **séparément pour chaque source**, ainsi que les compétences explicites disponibles. La moyenne annuelle brute est calculée sur le milieu de la fourchette de chaque offre qui publie un salaire annuel en EUR, puis moyennée arithmétiquement; les annonces sans salaire ne valent pas zéro. L'API WTTJ documente une réponse JSON en tableau, des champs de référence/intitulé/statut/profession/salaire, et les paramètres de pagination `page` et `per_page`. `scripts/extraire_wttj.py` demande les offres publiées et minimise immédiatement chaque objet vers les seuls champs nécessaires; aucun texte de description, employeur, profil, coordonnées ou donnée brute WTTJ n'est conservé. Le filtre des métiers commerciaux utilise des mots-clés dans l'intitulé et `profession_reference`; cette heuristique peut manquer des intitulés et inclure des faux positifs. Les compétences et tâches ne sont pas fournies par le schéma documenté.

La documentation officielle WTTJ confirme que [`GET /api/v1/external/jobs/all`](https://developers.welcomekit.co/jobs-api/jobs/list-all-jobs.md) retourne les offres de **toutes les organisations** et exige un partenariat dédié avec le scope `su_jobs_r`; ce n'est pas une route limitée au compte client. Le scope ordinaire `jobs_r` porte sur les offres d'une organisation précise via un autre endpoint. La portée documentée est donc multi-organisations lorsque WTTJ accorde le partenariat et que la clé fonctionne; elle ne signifie pas « tous les emplois en France ». La documentation ne précise pas la couverture géographique de la route, les valeurs par défaut/maximum de pagination ni le point de départ des pages. Faute d'une clé WTTJ accordée à ce dépôt, l'authentification, le schéma courant et la pagination n'ont pas pu être validés par un appel autorisé; le collecteur suit l'exemple officiel (tableau JSON), utilise `per_page=100`, demande la première page sans `page`, puis avance jusqu'à une page vide et dédoublonne les références. Une limite de sécurité interrompt les réponses répétées/infinies au lieu de publier un résultat présenté comme complet. Les quotas et les droits de republication analytiques doivent être confirmés avec WTTJ avant publication.

Les doublons inter-sources restent **non calculables** : le schéma documenté de cette route ne retourne pas de nom d'employeur ni de localisation normalisée dans les champs utilisés, qui sont requis par le rapprochement existant; un titre similaire seul ne suffit pas. Le collecteur ne substitue pas une référence d'organisation à un nom d'employeur et n'infère aucune localisation. Le rapprochement, lorsqu'il est possible avec des sources disposant des champs de lien requis, combine le titre (55 %), l'employeur (20 %), le lieu (15 %) et le salaire (10 % si les deux salaires existent), et ne fusionne jamais automatiquement les offres.

Pour activer WTTJ, demander une clé via le [formulaire officiel d'accès à l'API](https://help.welcometothejungle.com/) en précisant l'usage et demander explicitement le partenariat `su_jobs_r` permettant l'accès multi-organisations. Puis, dans GitHub, ouvrir **Settings → Secrets and variables → Actions → New repository secret**, nommer le secret `WTTJ_API_KEY` et y coller la clé. Ne pas ajouter de valeur réelle au dépôt, à `.env.example`, aux données ou au navigateur. Sans secret, le workflow conserve l'état WTTJ « non connecté »; avec une clé invalide, un droit insuffisant, une erreur réseau ou une réponse inattendue, il échoue clairement sans publier de résultat partiel.

Pour activer la collecte sur GitHub :

1. Dans les paramètres du dépôt, ajoutez les secrets Actions `FT_CLIENT_ID` et `FT_CLIENT_SECRET` obtenus pour l'API France Travail, ainsi que `WTTJ_API_KEY` seulement après l'accord de partenariat WTTJ.
2. Activez GitHub Pages si le site doit être publié.
3. Le workflow **veille** s'exécute chaque jour à 05:00 UTC; lancez-le aussi à la demande depuis **Actions → veille → Run workflow**. Il extrait les offres autorisées et actualise `data/resume.json`. Les catégories France Travail non collectées restent indiquées « à collecter »; WTTJ n'est pas compté sans clé et autorisation valides.

Les identifiants restent côté serveur dans les secrets GitHub Actions. Ils ne doivent jamais être placés dans une page HTML, un fichier de données publié ou un commit. En local, copiez `.env.example` vers `.env` et renseignez les identifiants France Travail; `.env` est ignoré par Git.

Le résumé publié contient les onze catégories, mais seules D1401 et D1402 ont été collectées à ce jour; les autres apparaissent « à collecter » jusqu'au prochain lancement du workflow. Leurs compteurs restent à zéro sans prétendre que l'API a été interrogée. Le fichier de données actuellement commité date d'avant le nouveau partitionnement; ses codes plafonnés restent explicitement marqués comme extraits sans cette stratégie jusqu'à la prochaine collecte.

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

Les tests unitaires de la taxonomie, du partitionnement temporel, des contrats, de l'authentification de recherche, de la fusion des extractions et des statistiques de comparaison s'exécutent avec :

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Interpréter les chiffres

La veille couvre le seul canal France Travail et une sélection de codes ROME, pas toutes les offres ni tous les intitulés possibles des métiers commerciaux. La limite de 3 150 résultats par recherche s'applique à chaque requête : le partitionnement par date de création permet de dépasser ce nombre par code lorsque les offres sont réparties sur plusieurs instants, sans garantir l'exhaustivité si un intervalle d'une seconde dépasse encore le plafond ou si l'API évolue pendant l'extraction. Les codes concernés gardent le total annoncé et le nombre effectivement récupéré; les courbes comptent les résultats collectés, sans extrapolation. Les nouvelles catégories n'ont pas d'historique avant leur première extraction. Les compétences sont repérées par une grille de mots-clés configurable, les salaires ne sont analysés que lorsqu'ils sont explicitement indiqués et leur estimation nette est indicative (brut annuel × 0,78 / 12, avant impôt). Les coordonnées approximatives au centre d'une commune ou d'un département ne donnent pas l'adresse de l'employeur. La page de comparaison ne contient pas de données WTTJ tant qu'un accès documenté et autorisé n'est pas obtenu.
