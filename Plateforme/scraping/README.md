# Rapport d analyse complet du module scraping

## 1) Perimetre et methode

Ce rapport couvre l ensemble des fichiers du module:

- `Plateforme/scraping/**`

Et les points d integration applicatifs relies a la moderation/publication:

- `Plateforme/events/**`
- `Plateforme/resources/**`
- `Plateforme/feed/**`
- `Plateforme/pages/**`
- `Plateforme/search/**`

Methode utilisee:

1. Inventaire complet des fichiers et sous-modules.
2. Lecture des flux critiques (urls, views, tasks, scrapers, extractors, settings, validators, admin).
3. Verification des chemins LLM/traduction.
4. Verification du workflow de moderation (pending/approved).
5. Controle des incoherences de configuration et des divergences structurelles.
6. Verification des erreurs IDE (aucune erreur statique remontee sur `Plateforme/scraping`).

---

## 2) Resume executif

- Le module scraping est globalement bien structure: orchestration Celery, extraction par categorie, suivi d execution, moderation, metriques.
- Les contenus scrapes ne sont pas censes etre publics directement: ils sont majoritairement crees en `pending`, puis publies via validation admin.
- Le systeme LLM existe, mais la traduction arabe n est pas garantie de bout en bout:
  - fallback frequent vers champs EN,
  - traduction LLM conditionnelle,
  - drapeaux `auto_translate` non relies a un pipeline automatique global.
- Une erreur technique concrete a ete identifiee: `SS.ROBOTS_TIMEOUT` est utilise sans etre defini dans les settings centralises.
- Plusieurs incoherences d architecture peuvent creer des comportements partiels selon la categorie (mapping, commandes, admin actions).

---

## 3) Cartographie fonctionnelle (A -> Z)

## A. Entree API/Backoffice

- Routes principales: `Plateforme/scraping/urls.py`
- Exports de vues: `Plateforme/scraping/views/__init__.py`
- Implementation principale de moderation/control: `Plateforme/scraping/views_root.py`

Fonctions cles:

- lancement de scraping (`run_scraper`)
- statut de run (`run_scraper_status` / `task_status`)
- liste des resultats scrapes
- validation/suppression unitaire ou en masse
- analytics, trends, metriques

## B. Orchestration des runs

- Tache Celery principale: `Plateforme/scraping/tasks.py` (`run_scraper_task`)
- Log de run: `ScrapingRun`
- Source tracking: `ScrapingSource`, `ScrapingSourceHealth`
- Push progression: websocket channels (`push_scraping_progress`)

Comportement:

1. Creation du run (`status=running`).
2. Dispatch Celery.
3. Fallback synchrone si Celery indisponible.
4. Mise a jour des compteurs (`items_found`, `items_created`, `items_skipped`).
5. Finalisation `completed` ou `failed`.

## C. Selection de scrapers par categorie

Registry:

- `Plateforme/scraping/scrapers/__init__.py`

Categories supportees par le registry:

- `events`, `tools`, `courses`, `news`, `opportunities`, `corpus`

Chaque categorie a son scraper dedie (`scrapers/events.py`, `tools.py`, `courses.py`, `news.py`, `opportunities.py`, `corpus.py`).

## D. Acquisition de donnees

- Web search: `Plateforme/scraping/network/search_client.py` (Tavily)
- Validations reseau/contenu:
  - `Plateforme/scraping/validators/network_validator.py`
  - `Plateforme/scraping/validators/content_validator.py`

## E. Extraction/normalisation LLM

- Extractors categorie par categorie:
  - `Plateforme/scraping/extractors/events/llm_event_extractor.py`
  - `Plateforme/scraping/extractors/tools/llm_tool_extractor.py`
  - `Plateforme/scraping/extractors/courses/llm_course_extractor.py`
  - `Plateforme/scraping/extractors/news/llm_news_extractor.py`
  - `Plateforme/scraping/extractors/opportunities/llm_opportunity_extractor.py`
  - `Plateforme/scraping/extractors/corpus/llm_corpus_extractor.py`

Mecanisme general:

1. Entrer des resultats de recherche (titre/url/content).
2. Prompt systeme strict.
3. Parsing JSON.
4. Normalisation des champs.
5. Rejet des items incomplets.

## F. Enrichissement (facultatif / non central au run)

- Moteur: `Plateforme/scraping/enrichment_engine.py`
- Usage principal observe: action admin `re_enrich_selected` dans `Plateforme/scraping/admin.py`

Conclusion importante:

- L enrichissement n est pas le pipeline principal systematique de chaque run; il est surtout expose en action admin.

## G. Dedup, pertinence, score

- Base scraper + intelligence/completeness:
  - `Plateforme/scraping/scrapers/base.py`
  - `Plateforme/scraping/intelligence.py`
  - `Plateforme/scraping/field_mapping.py`

## H. Persistance et flags de moderation

Ecriture en base depuis les scrapers, avec forcage vers moderation:

- `tools.py`: creation/update en `approval_status="pending"`, `is_approved=False`
- `courses.py`: idem
- `events.py`: remet en pending si necessaire
- `news.py`, `opportunities.py`, `corpus.py`: appliquent pending/is_approved si les champs existent

## I. Workflow moderation

- Vues de moderation: `Plateforme/scraping/views_root.py`
- Action de validation: `_apply_scraping_item_action(..., action="validate")`

Effet de validation:

- `approval_status = "approved"`
- `is_approved = True` (si champ present)
- `approval_date`, `approved_by` si disponibles

## J. Visibilite publique

La couche publique filtre majoritairement sur `approved`:

- Events: `Plateforme/events/views.py`
- Resources: `Plateforme/resources/views.py` (statuses visibles = `approved`)
- Feed/news: `Plateforme/feed/views.py`
- Pages agregations: `Plateforme/pages/views.py`
- Search index: `Plateforme/search/documents.py`

Conclusion:

- Les contenus pending ne sont pas censes etre visibles publiquement, sauf vues backoffice/admin ou cas specifiques d auteur/staff.

---

## 4) Reponse explicite: Pourquoi la traduction LLM n est pas toujours faite ?

Ta question: "pourquoi y a pas un llm qui fait la traduction ?"

Reponse courte:

- Il y a bien des composants LLM, mais pas une garantie de traduction automatique complete et uniforme sur tout le pipeline.

Ca vient de plusieurs causes techniques:

1. Traduction conditionnelle au lieu d obligatoire
- Dans plusieurs extractors, si `title_ar` / `description_ar` manque, le fallback copie EN vers AR:
  - ex. `title_ar = ... or title_en`
  - ex. `description_ar = ... or description_en`

2. LLM desactive si cle absente ou indisponible
- Les extractors court-circuitent quand la cle Groq n est pas configuree.
- Ils retournent alors `[]` ou des donnees partielles.

3. Pipeline events different des autres categories
- `events.py` a un post-traitement `_fill_missing_arabic_fields`.
- Ce post-traitement utilise `GROQ_INTERNAL_API_KEY` (pas la meme cle que `GROQ_SCRAPING_API_KEY`).
- Si cette cle "internal" manque, on retombe sur un fallback regle-based (pas une vraie traduction semantique complete).

4. Echec LLM silencieux/fallback
- En cas de reponse non JSON, timeout, 413/429, le code continue avec fallback.

5. `auto_translate` n active pas automatiquement la traduction
- Le flag existe dans `field_mapping.py`, mais il est metadata/completeness.
- Il n est pas branche a un orchestrateur global "traduire tous les champs AR".

Impact concret:

- Tu peux avoir beaucoup de contenus avec champs arabes remplis par copie du texte anglais, ou par traduction partielle, selon categorie et disponibilite des cles.

---

## 5) Reponse explicite: Les elements scrapes vont-ils directement sur le site ?

Ta question: "est ce qu ils seront directement dans le site ou pending admin approval ?"

Reponse courte:

- En pratique, le flux est concu pour `pending admin approval`.

Pourquoi:

1. Les scrapers forcent majoritairement `approval_status="pending"` a la creation/update.
2. La publication est faite ensuite via action de validation (`scraping_result_validate` / bulk action).
3. Les vues publiques et index de recherche filtrent sur `approval_status="approved"`.

Donc:

- Non, un item scrape n est normalement pas public immediatement.
- Il devient public apres validation (ou si un flux staff fait explicitement approved).

---

## 6) Erreurs et incoherences detectees

## Erreur critique

1. Setting manquant pour robots timeout
- Fichier usage: `Plateforme/scraping/robots_policy.py`
- Code utilise: `SS.ROBOTS_TIMEOUT`
- Fichier settings: `Plateforme/scraping/scraping_settings.py`
- Constat: `ROBOTS_TIMEOUT` n est pas defini dans `ScrapingSettings`.
- Risque: erreur runtime lors des verifications robots si ce chemin est execute.

## Erreurs fonctionnelles importantes

2. Mapping admin incoherent pour la categorie news
- Fichier: `Plateforme/scraping/admin.py` (`_get_model_instance_for_meta`)
- Mapping actuel news: `("QA.models", "Post")`
- Or le modele detecte est `feed.models.Post` (via scraper news et modeles reels).
- Risque: actions admin de type re-enrich/redownload peuvent echouer pour les metas `news` (objet introuvable).

3. Categories non harmonisees entre registry et choix de source
- Registry complet: `scrapers/__init__.py` inclut `news/opportunities/corpus`
- `ScrapingSource.CATEGORY_CHOICES` dans `models.py` n inclut pas `opportunities/corpus` et inclut `institutions`.
- Risque: incoherence UI/formulaire/admin, confusion de configuration.

4. `ALL_CATEGORIES` incomplet
- Fichier: `Plateforme/scraping/constants.py`
- `ALL_CATEGORIES` = `events/tools/courses` seulement.
- Commande `discover_selectors` utilise `ALL_CATEGORIES` pour ses `choices`.
- Risque: impossibilite out-of-the-box de lancer cette commande pour `news/opportunities/corpus`.

5. `SCRAPER_REGISTRY` incomplet pour certaines operations
- Fichier: `Plateforme/scraping/constants.py`
- Registry media command: uniquement `events/courses/tools`.
- `verify_scraping_media` depend de ce registry pour redownload.
- Risque: redownload non pris en charge pour d autres categories.

## Risques de maintenabilite

6. Double implementation de couches proches
- Presence de versions paralleles (`views_root.py` + `views.py`, `llm_validation.py` + `extractors/core/llm_validation.py`, et duplication intelligence root/core).
- Risque: derive fonctionnelle dans le temps, corrections appliquees a un seul endroit.

7. Endpoint `validate_source` minimal
- Fichier: `Plateforme/scraping/views_root.py`
- Retourne un success statique "Endpoint is working".
- Pendant ce temps, la validation reelle existe en tache async (`tasks.validate_source_async`) via signaux.
- Risque: confusion UX/API (endpoint de validation qui ne valide pas vraiment).

## Point de controle positif

8. Erreurs statiques IDE
- Verification effectuee sur `Plateforme/scraping`
- Resultat: aucune erreur remontee par l analyse IDE.

---

## 7) Recommandations prioritaires

Priorite P0 (immediat):

1. Ajouter `ROBOTS_TIMEOUT` dans `ScrapingSettings` (ou remplacer usage par un timeout existant).
2. Corriger mapping news dans `scraping/admin.py` vers `feed.models.Post`.

Priorite P1:

3. Harmoniser toutes les listes de categories (`SCRAPERS`, `ScrapingSource.CATEGORY_CHOICES`, `ALL_CATEGORIES`, registries commandes).
4. Etendre `SCRAPER_REGISTRY` ou adapter `verify_scraping_media` pour toutes categories cibles.

Priorite P2:

5. Unifier les chemins LLM/traduction (une source de verite pour client/config).
6. Relier explicitement `auto_translate` a un pipeline de traduction obligatoire (si c est l objectif produit).
7. Clarifier/retirer les duplications de modules pour limiter la derive.

---

## 8) Verdict final a tes 2 questions

1. Pourquoi la traduction LLM ne se fait pas partout ?
- Parce qu elle est conditionnelle, heterogene selon categories, et avec fallback EN->AR; `auto_translate` ne declenche pas une traduction globale obligatoire.

2. Les contenus scrapes sont-ils directement publies ?
- Non en fonctionnement nominal: ils sont crees en pending puis valides par admin avant visibilite publique.

---

## 9) Notes de verification

Ce rapport est base sur la lecture code et la verification croisee des flux suivants:

- routing/views moderation
- tasks Celery
- scrapers par categorie
- extractors LLM
- enrichment/admin actions
- modeles approval_status
- filtres de visibilite publique
- settings/constants/management commands

Si tu veux, je peux maintenant produire un 2eme fichier avec un plan de patch concret (fichiers + diff logique) pour corriger automatiquement les points P0/P1.

---

## 10) Comment ca marche exactement quand tu cliques sur "Demarrer scraping"

Voici le flux reel, de l interface jusqu a la base:

1. Tu cliques sur le bouton dans `templates/scraping/dashboard.html`.
2. La fonction JS `runScraper(cat)` envoie un POST vers `scraping/run/<category>/`.
3. Le backend `run_scraper` (dans `scraping/views_root.py`) cree un `ScrapingRun` en status `running`.
4. Le backend essaie de lancer Celery: `run_scraper_task.delay(category, run_id=..., user_id=...)`.
5. Le frontend recoit `status=started` et ouvre un WebSocket sur `ws/scraping/<run_id>/`.
6. Le consumer `ScrapingStatusConsumer` rejoint le groupe `scraping_<run_id>`.
7. La task Celery `run_scraper_task` envoie des messages via `push_scraping_progress(...)`.
8. Le JS recoit ces messages et met a jour:
  - la ligne de narration,
  - la progression `Queries processed: x / y`,
  - le compteur `items_scraped/items_failed`.
9. A la fin, quand status devient `completed` ou `failed`, le JS fait un fetch final sur `status/<run_id>/` pour afficher le resume.

Important:

- Le WebSocket utilise `run_id` (pas le `task_id` Celery), et c est coherent avec `push_scraping_progress(str(run.id), ...)`.
- Si Celery est indisponible, la vue tombe en mode synchrone et retourne directement un resultat final.

---

## 11) Comment chaque section scrape concretement

## 11.1 Events

Pipeline principal (`scrapers/events.py`):

1. Construit des requetes (`_build_search_queries`) depuis:
  - queries actives en DB,
  - templates par defaut (annee courante + suivante).
2. Lance Tavily (`search_events`) sur chaque requete.
3. Nettoie/filtre les resultats (URL valide, source autorisee, resultat viable, dedup URL).
4. Passe par extraction LLM (`LLMEventExtractor`) par batch.
5. En cas de limite Groq ou manque de candidats, fabrique des fallback candidates a partir des resultats search.
6. Dedup final des candidats.
7. Complete les champs arabes manquants via `_fill_missing_arabic_fields`:
  - d abord LLM interne (`GROQ_INTERNAL_API_KEY`),
  - sinon fallback regle-based.
8. Sauvegarde chaque evenement (`_save_event_candidate`), avec forcage moderation pending.

## 11.2 Tools

Pipeline principal (`scrapers/tools.py`):

1. Recupere les queries actives categorie tools.
2. Tavily `search_web`.
3. Extraction LLM `LLMToolExtractor`.
4. Normalisation (title/description/capabilities/liens).
5. `update_or_create` sur `resources.NLPTool` (lookup github_url sinon title_en).
6. Forcage moderation: `approval_status=pending`, `is_approved=False`.

## 11.3 Courses

Pipeline principal (`scrapers/courses.py`):

1. Queries actives courses.
2. Tavily `search_web`.
3. Extraction LLM `LLMCourseExtractor`.
4. Normalisation (niveau, prix, plateforme, langue).
5. Resolve institution (cree/recupere institution et country).
6. `update_or_create` sur `resources.Course`.
7. Forcage moderation pending.

## 11.4 News

Pipeline principal (`scrapers/news.py`):

1. Resolve modele cible dynamiquement (candidats: events.News, resources.News, feed.Post).
2. Queries actives news.
3. Tavily `search_web`.
4. Extraction LLM `LLMNewsExtractor`.
5. Normalisation.
6. `update_or_create` sur le modele trouve avec mapping de champs flexible.
7. A la creation: applique flags de moderation si les champs existent.

## 11.5 Opportunities

Pipeline principal (`scrapers/opportunities.py`):

1. Resolve modele cible dynamiquement.
2. Queries actives opportunities.
3. Tavily `search_web`.
4. Extraction LLM `LLMOpportunityExtractor`.
5. Normalisation (job_title, institution, type, deadline, url).
6. `update_or_create` avec mapping compatible selon champs disponibles.
7. A la creation: flags moderation pending.

## 11.6 Corpus

Pipeline principal (`scrapers/corpus.py`):

1. Resolve modele cible dynamiquement.
2. Queries actives corpus.
3. Tavily `search_web`.
4. Extraction LLM `LLMCorpusExtractor`.
5. Normalisation (dataset_name, description, download_url, language_variants).
6. `update_or_create` selon URL sinon titre.
7. A la creation: flags moderation pending.

---

## 12) Pourquoi ton ecran peut rester bloque a "0/6 ... please wait"

Tu as demande pourquoi ca reste a 0/6 pendant longtemps. Voici la cause technique precise.

## Cause racine principale

Dans `run_scraper_task`:

1. Un premier message est envoye tout de suite: `progress=0`, `total=total_sources`.
2. Ensuite la task lance `scraper.run()` (operation longue).
3. Les messages incrementaux `progress=1..N` sont envoyes seulement apres que `scraper.run()` soit termine, via une boucle finale sur les sources.

Resultat:

- Pendant l execution reelle, l interface n a pas de progression intermediaire numerique.
- Donc visuellement tu vois `0/6` longtemps, puis saut final.

## Problemes supplementaires qui aggravent l effet

1. Mauvaise unite de progression dans le texte UI
- Le front affiche "Queries processed: x/y".
- Le backend alimente `y` avec `total_sources` (nombre de sources actives), pas le nombre de queries ni de batches.
- Donc le message est trompeur.

2. Le fallback polling ne renvoie pas de progression live
- `run_scraper_status` retourne surtout l etat final (`status`, compteurs finaux), pas des compteurs de progression intermediaires.
- Si le websocket n apporte pas de messages intermediaires, le front ne peut pas inventer un avancement fiable.

3. Consumer initial base sur champs non modelises
- `ScrapingStatusConsumer._send_current_status()` lit `run.total_sources`, `run.progress`, `run.items_scraped`.
- Ces champs ne sont pas dans le modele `ScrapingRun` actuel.
- Le consumer envoie donc des valeurs par defaut (0), ce qui contribue a un demarrage visuel a zero.

---

## 13) Pourquoi il y a ces bugs (explication architecture)

Ces bugs viennent d un decalage entre design UI et emission reelle des evenements:

1. Le dashboard est pense pour un suivi live granulaire.
2. La task Celery n emet pas de progression granulaire pendant le coeur de `scraper.run()`.
3. La progression est reconstruite "apres coup" sur les sources, donc trop tard pour une UX temps reel.
4. Le wording UI parle de queries, mais la mesure backend est basee sur sources.
5. Le consumer essaie de lire des champs de progression qui ne sont pas persistes dans `ScrapingRun`.

Donc ce n est pas un seul bug isole, c est un ensemble de petites incoherences entre:

- le front (narration + compteur),
- la task async (moments d emission),
- le modele (absence des champs de progression persistes).

---

## 14) Ce qu il faut faire pour avoir le comportement que tu veux

Objectif UX que tu as demande:

- "je veux un texte live qui resume ce qu il fait maintenant"
- "je veux un compteur qui avance vraiment (pas bloque a 0/6)"

Plan concret:

1. Emettre des progress events pendant `scraper.run()` (pas seulement debut/fin).
2. Choisir une unite unique de progression:
  - soit par source,
  - soit par query,
  - soit par batch LLM.
3. Aligner le texte UI sur cette unite (ne plus afficher "Queries" si tu comptes des sources).
4. Ajouter dans `ScrapingRun` des champs persistes de progression (ex: `progress_current`, `progress_total`, `current_step`, `current_source`, `current_query`).
5. Faire retourner ces champs par `run_scraper_status` pour fallback polling robuste.
6. Conserver la narration existante, mais la lier a des etapes reelles (search, extraction, validation, save).

Exemple de narration cible:

- Step 1/4: Discovery (Tavily) en cours...
- Step 2/4: Extraction LLM en cours...
- Step 3/4: Validation et dedup en cours...
- Step 4/4: Sauvegarde en base + mise en file moderation...

Avec compteur:

- Sources: `2/6`
- Queries: `5/14`
- Items: `12 created, 3 skipped`

---

## 15) Reponse courte finale a ta question de blocage

Pourquoi tu vois "0/6" bloque:

- parce que la task envoie `0/6` au debut,
- puis elle travaille longtemps sans envoyer de progression intermediaire,
- et elle envoie les increments surtout en fin de traitement.

Donc ton impression est correcte: le scraping tourne, mais le suivi live actuel est incomplet.

