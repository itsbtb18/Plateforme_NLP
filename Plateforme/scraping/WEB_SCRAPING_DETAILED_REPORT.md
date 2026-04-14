# Rapport detaille - Module Web Scraping

## 1. Objectif du module

Le module de web scraping de la plateforme a pour role de collecter, valider, enrichir et persister des contenus externes pertinents pour l'ecosysteme NLP.

Les 5 categories principales prises en charge sont:
- events
- tools
- news
- courses
- institutions

Le module est concu pour fonctionner en mode production avec:
- execution asynchrone (Celery)
- suivi de sante des sources
- controle de debit (rate limit)
- resilience reseau (retry, backoff, circuit breaker)
- observabilite (Prometheus)
- enrichissement intelligent (NLP + LLM optionnel)

## 2. Architecture globale

Flux principal:

1. L'utilisateur (admin) declenche un scraping depuis l'interface Django.
2. Une entree de suivi est creee dans ScrapingRun.
3. Une tache Celery est lancee sur la queue scraping.
4. Le moteur selectionne un scraper par categorie (ou source custom).
5. Le scraper recupere les contenus (HTTP/RSS/Playwright selon besoin).
6. Les items sont valides, dedupliques, puis enrichis.
7. Les donnees sont sauvegardees dans les modeles metier cibles.
8. Les metriques et statuts sont publies (Prometheus + WebSocket).

Composants principaux:
- Couche Web: vues Django + endpoints de controle
- Couche Orchestration: taches Celery + manager
- Couche Scrapers: base commune + scrapers specialises par categorie
- Couche Qualite: validation reseau/contenu + dedup + freshness
- Couche Intelligence: enrichment metadata + NER + scoring
- Couche Monitoring: Prometheus + journaux + dead letters

## 3. Outils et technologies utilises

### 3.1 Framework et orchestration
- Django (application scraping, vues, modeles, admin)
- Celery (execution asynchrone des runs)
- django-celery-beat (planification periodique, scheduler adaptatif)
- Django Channels (push WebSocket du statut de scraping)

### 3.2 Collecte web
- requests (HTTP client)
- BeautifulSoup (parsing HTML)
- feedparser (RSS/Atom)
- Playwright (fallback rendu JS sur sites dynamiques)

### 3.3 Traitement, NLP et enrichissement
- spaCy (NER multilingue selon configuration)
- client Groq LLM optionnel (classification/validation/enrichissement)
- logique heuristique de langue, type d'evenement, score de pertinence

### 3.4 Stockage et observabilite
- Django ORM (ScrapingSource, ScrapingRun, ScrapedItemMeta, ScrapingSourceHealth)
- Prometheus client (counters, gauges, histograms)
- cache Django (rate-limit et robots policy)
- dead-letter logs (JSONL) pour erreurs irreversibles

### 3.5 APIs et sources externes integrees
- arXiv API
- Semantic Scholar API
- HuggingFace Hub API
- ROR API
- OpenAlex API
- Wayback Machine API

## 4. Modeles de donnees (coeur)

### 4.1 ScrapingSource
Definition d'une source configurable.

Attributs importants:
- identite: id, name, category, url/base_url, description
- controle: is_active, is_default, source_type(web/api)
- robustesse: fail_count, consecutive_failures, last_error, fallback_url
- execution: last_scraped, last_run_status, last_run_items_created
- extraction: scrape_config, css_selectors, use_rss, force_playwright, verify_ssl, proxy_url
- validation: validation_status, validation_detail, last_validated_at
- scheduling adaptatif: schedule_tier, schedule_interval_hours

### 4.2 ScrapingRun
Journal d'execution d'un run.

Attributs importants:
- category, task_id (Celery), status (running/completed/failed)
- items_found, items_created, items_skipped
- erreurs, timestamps
- triggered_by, source

### 4.3 ScrapingSourceHealth
Etat de sante et circuit breaker par source.

Attributs importants:
- compteurs: attempts/successes/failures/consecutive_failures
- health_score (0-100)
- circuit_state (closed/open/half_open)
- cooldown, derniere tentative/succes/echec
- logique metier: record_success, record_failure, is_available

### 4.4 ScrapedItemMeta
Metadonnees d'intelligence et de qualite sur item scrape.

Attributs importants:
- provenance: source_name, source_url, content_source(live/wayback/cache)
- dedup: skip_reason, was_skipped, match_score, matched_item_id
- intelligence: domain_scores, primary_domain, relevance_score
- qualite: enrichment_status, completeness_score
- embedding dedup (pgvector si disponible, sinon JSON)

## 5. Endpoints de controle (Django)

Exposes via l'app scraping:
- dashboard, metrics, results, detail, validate/delete/bulk action
- run/<category>/ pour lancer un scraping de categorie
- run-custom/<source_id>/ pour source personnalisee
- status/<run_id>/ et task-status/<run_id>
- runs/recent, rerun
- analytics, trends, skip-reasons, source-health
- sources add/delete/list
- test source + statut de test

Ces endpoints sont proteges par:
- login
- verification admin/staff
- CSRF pour les actions sensibles
- limitation de debit selon endpoint

## 6. Pipeline de fonctionnement detaille

### 6.1 Demarrage d'un run
1. Creation/recuperation d'un ScrapingRun.
2. Association de l'identifiant task Celery.
3. Chargement des sources actives de la categorie.
4. Publication initiale de progression (WebSocket).

### 6.2 Execution scraper
Deux modes:
- mode categorie: get_scraper(category).run()
- mode source custom: CustomDomainScraper(source).scrape()

Sortie attendue:
- items_found
- items_created
- items_skipped
- errors
- details de resultats

### 6.3 Traitement des erreurs
- Si categorie invalide: run failed + metriques echec
- Si exception runtime: run failed + dead letter + marquage source en echec
- fallback optionnel via fallback_url apres echec de validation
- desactivation automatique source apres echecs consecutifs critiques

### 6.4 Finalisation run
- mise a jour ScrapingRun
- metriques Prometheus (runs, durations, items)
- synchro des metriques de sante source
- push progression finale (completed/failed)

## 7. Robustesse et securite

### 7.1 Retry et backoff
Le socle scraper implemente:
- retries reseau limites
- backoff exponentiel
- gestion de statuts HTTP non retryables
- rotation User-Agent

### 7.2 Circuit breaker
Par source:
- fermeture nominale (closed)
- ouverture en cas de degradations (open)
- sonde de reprise (half_open)
- retour closed si succes

### 7.3 robots.txt
- verification via RobotFileParser
- cache des regles robots
- policy fail-open configurable

### 7.4 Rate limiting
Decorator de controle de debit cote vues:
- quota par utilisateur/endpoint
- fallback anon par IP
- reponse 429 avec Retry-After

### 7.5 Dead-letter
Persist des echecs irreversibles en JSONL:
- categorie/source
- URL/titre
- type d'erreur
- compteur de retry

## 8. Enrichissement intelligent

Le moteur d'enrichissement applique:
- remplissage de champs manquants selon mapping de categorie
- enrichissement specifique par type (events/tools/news/courses/institutions)
- extraction d'entites nommees (spaCy)
- detection de langue
- score de pertinence
- statut d'enrichissement + completude

Si le client LLM est disponible:
- certaines etapes utilisent une aide LLM (timeout et retries controles)

Si indisponible:
- le pipeline continue en mode degrade (heuristiques locales)

## 9. Scheduling adaptatif

Le scheduler adaptatif:
- analyse les N derniers runs completes par source
- estime le taux de nouveaux items par jour
- attribue un tier (very_high/high/medium/low/dormant)
- met a jour automatiquement la periodicite (django-celery-beat)

Tache periodique presente:
- update_adaptive_schedules (03:00 UTC)

## 10. Metriques Prometheus exposees

Exemples de metriques:
- scrape_runs_total{category,status}
- scrape_duration_seconds{category}
- scrape_items_total{category,outcome}
- scrape_source_duration_seconds{category,source_name,source_tier}
- scrape_source_items_total{category,source_name,outcome}
- scrape_dedup_hits_total{category,dedup_rule}
- source_health_score{source_url}
- circuit_breaker_state{source_url,state}
- scrape_queue_lag_seconds{category}
- enrichment_duration_seconds{category,enrichment_step}
- enrichment_failures_total{category,enrichment_step,failure_reason}

## 11. Commandes d'exploitation

Execution manuelle:
- python manage.py run_scraper --category events
- python manage.py run_scraper --all

Operations utiles:
- seed des sources par defaut
- synchro des schedules
- verification media de scraping
- rerun d'un run en echec depuis l'interface

## 12. Bonnes pratiques de production

- activer Redis comme backend cache pour rate-limit coherent multi-workers
- isoler la queue Celery scraping des autres workloads
- configurer des timeouts stricts par source externe
- surveiller les metriques de sante/circuit breaker en continu
- maintenir une politique de fallback propre (fallback_url, wayback)
- auditer regulierement les dead-letter logs
- conserver un set minimal de sources par defaut actives

## 13. Resume technique

Le module web scraping est une brique mature orientee production.

Points forts:
- architecture modulaire par categorie
- execution asynchrone et observable
- mecanismes de resilience avances
- enrichissement intelligent des donnees
- governance des sources (sante, validation, quarantaine, planning adaptatif)

Ce module alimente durablement la plateforme avec des contenus externes qualifies, tout en limitant les risques operationnels (instabilite reseau, derive de sources, doublons, erreurs silencieuses).