# README_PRESENTATION

## 1. Introduction et Périmètre
Le module de web scraping a pour objectif d'alimenter automatiquement une plateforme collaborative de recherche en NLP arabe en collectant, structurant, qualifiant et préparant des contenus à forte valeur académique (ressources, événements, actualités, opportunités) avant leur validation éditoriale. Il agit comme une couche d'acquisition intelligente: il interroge le web de façon ciblée, transforme des pages hétérogènes en objets exploitables, mesure la confiance d'extraction, puis persiste les résultats dans l'écosystème Django/PostgreSQL pour la modération, l'analyse et la diffusion.

Les 6 catégories gérées sont:
- Tools: complexité élevée, car il faut extraire des champs techniques précis (liens GitHub, licence, capacités, langues supportées) à partir de sources très variées.
- Courses: complexité moyenne à élevée, avec normalisation de niveau académique, plateforme, prix/gratuité, institution et cohérence pédagogique.
- News: complexité moyenne, centrée sur la fraîcheur, la date de publication, la pertinence NLP arabe et la déduplication rapide.
- Opportunities: complexité élevée, avec extraction fiable de deadline, type d'opportunité, institution et conditions d'éligibilité depuis des annonces non standardisées.
- Corpus: complexité élevée, car les jeux de données exigent des métadonnées techniques (liens de téléchargement, variantes linguistiques, taille estimée, provenance).
- Events: complexité très élevée, notamment sur la qualité des dates (start/end), la détection d'URL réellement événementielles et le filtrage des faux positifs (pages agrégatrices, calendriers génériques).

## 2. Architecture et Pipeline de Données (Le "Comment ça marche")
Le pipeline suit une chaîne déterministe, observable et pilotée par catégorie:

1. Stratégie de requêtage (SearchQuery actives)
- Chaque scraper charge dynamiquement ses requêtes actives depuis la base (`SearchQuery` par catégorie, `is_active=True`).
- Cette stratégie rend l'acquisition pilotable sans redéploiement: les administrateurs ajustent les intentions de recherche directement dans l'interface.
- Pour certains cas (ex. events), des templates de requêtes et des garde-fous (limites de lots et quotas de recherche) complètent les requêtes DB pour garantir une couverture minimale.

2. Recherche sémantique ciblée via Tavily
- Le client `TavilySearchClient` exécute des recherches asynchrones avec configuration par catégorie (`search_events`, `search_tools`, `search_courses`, `search_news`, `search_opportunities`, `search_corpus`).
- Chaque profil impose profondeur, volume et domaines prioritaires (ex. GitHub/HuggingFace pour Tools, plateformes MOOC pour Courses, etc.).
- Les résultats sont normalisés en triplets utiles (`title`, `url`, `content`) avec filtrage des entrées vides.

3. Extraction et structuration via Groq (LLM llama-3.1-8b-instant)
- Les extracteurs LLM par catégorie (events/tools/courses/news/opportunities/corpus) transforment les snippets Tavily en objets structurés JSON.
- Les prompts imposent un schéma strict (champs obligatoires/optionnels, dates normalisées, traduction arabe/anglais, score de pertinence).
- Le client LLM (`GroqLLMClient`) applique une politique de routage robuste (primaire/fallback). Dans la configuration de référence Groq, le modèle mobilisé peut être `llama-3.1-8b-instant` pour des traitements rapides; le pipeline reste compatible avec d'autres modèles configurés.
- En cas de réponse bruitée (code fences, JSON incomplet), des mécanismes de nettoyage/parsing et de reprise limitent la casse opérationnelle.

4. Pipeline de validation (ExtractionQualityValidator, scores de confiance)
- Avant persistance, chaque candidat passe dans un double filtre:
  - Calcul de confiance et de complétude (scoring interne par catégorie, pertinence NLP arabe, qualité des champs).
  - Validation qualité (`ExtractionQualityValidator`): contrôle des minimums (titre, URL, cohérence, seuil de confiance, statut de traduction).
- Les items sous seuil ou incohérents sont ignorés/rejetés afin de protéger la qualité du corpus final.

5. Sauvegarde dans l'ORM Django (PostgreSQL)
- Les candidats validés sont persistés via `update_or_create` dans les modèles cibles (events/resources/pages/feed selon la catégorie).
- Le module enregistre l'état d'exécution dans `ScrapingRun` (statut, progression, compteurs, erreurs, durée), ainsi que les sources dans `ScrapingSource` et les notifications dans `ScrapingNotification`.
- Les contenus sont généralement injectés en statut de modération (`pending`) pour validation humaine avant diffusion.

6. Orchestration API et supervision temps réel
- Déclenchement via endpoint Django (`run_scraper`) puis exécution asynchrone Celery (`run_scraper_task`) avec fallback synchrone si nécessaire.
- Suivi temps réel par WebSockets (`ScrapingStatusConsumer`, route `ws/scraping/<task_uuid>/`), permettant de remonter progression, source courante, items créés/échoués et statut final.

## 3. Stack Technologique
Technologies clés du module:
- Django: orchestration applicative, endpoints admin/API, ORM, modération.
- PostgreSQL: persistance transactionnelle des runs, sources, requêtes, métadonnées et objets métier.
- Tavily API: recherche sémantique web multi-domaine, configurable par catégorie.
- Groq: extraction/structuration LLM en JSON strict, avec politique de fallback.
- Pydantic/JSON: schématisation et validation de données structurées dans la chaîne API globale; côté scraping, usage intensif de JSON strict et `JSONField` pour métadonnées et diagnostics.
- WebSockets (Django Channels): télémétrie et monitoring temps réel des runs de scraping.

## 4. Nouvelles Approches (L'innovation du projet)
Le projet opère une transition claire d'un scraping classique basé sur le DOM vers un scraping sémantique et agentique.

Dans une approche DOM traditionnelle, l'extraction dépend de sélecteurs CSS fragiles et casse au moindre changement de front-end. Ici, la logique se déplace du niveau "structure HTML" vers le niveau "sens du contenu": la recherche fournit des signaux textuels pertinents, puis le LLM reconstruit des objets métier complets avec normalisation (dates, liens, champs bilingues, typologie de contenu).

Cette approche est moderne et puissante pour trois raisons:
- Robustesse à l'hétérogénéité web: des pages très différentes peuvent produire un schéma final homogène sans écrire un parseur dédié pour chaque site.
- Précision orientée métier: le LLM extrait des champs complexes (deadline, type d'opportunité, GitHub URL, langue, institution) difficiles à fiabiliser avec des règles statiques.
- Compréhension contextuelle NLP arabe: la pertinence ne se limite pas à des mots-clés exacts, mais intègre le contexte scientifique, linguistique et applicatif du domaine arabe.

## 5. Comparaison avec les "Related Works" (État de l'art)
| Critère | Approche traditionnelle (BeautifulSoup/Scrapy) | Notre approche (LLM + Search API) |
|---|---|---|
| Dépendance au design UI | Très forte (sélecteurs CSS/XPath fragiles) | Faible (agnostique au design visuel) |
| Coût de maintenance | Élevé (un script par site, retouches fréquentes) | Réduit (pipeline générique piloté par requêtes + prompts) |
| Résilience aux changements | Faible (casse au redesign) | Élevée (tolérance aux variations de structure) |
| Qualité sémantique extraite | Limitée (règles codées en dur) | Forte (qualification contextuelle, extraction de champs complexes) |
| Passage à l'échelle multi-domaines | Lent et coûteux | Rapide (même architecture pour Tools/Courses/News/Opportunities/Corpus/Events) |
| Adaptation au NLP arabe | Souvent superficielle | Native (prompts orientés arabe + validation de pertinence) |

## 6. Limites actuelles et Travaux futurs
Limites techniques actuelles (transparence scientifique):
- Rate-limits et quotas LLM/API: les pics de charge peuvent dégrader débit et latence d'extraction.
- Hallucinations JSON: malgré les prompts stricts, certains retours LLM restent partiellement invalides ou incomplets.
- Couverture des requêtes: la qualité dépend encore de la richesse des `SearchQuery` actives; des angles morts thématiques subsistent.
- Variabilité multi-source: certaines pages très bruitées (annuaires/listings) génèrent des faux positifs.
- Dépendance externe: qualité des résultats liée à la disponibilité de Tavily/LLM et à la stabilité réseau.

Travaux futurs prioritaires:
- Renforcer la validation formelle des schémas (garde-fous typés, politiques de rejet plus fines, scoring calibré par catégorie).
- Étendre automatiquement les requêtes via expansion sémantique pilotée par ontologies NLP arabe.
- Mettre en place un banc d'évaluation continu (précision/rappel par catégorie, benchmark temporel, audit d'erreurs).
- Développer un mécanisme de consensus multi-pass LLM (self-check + re-ranking) pour réduire les hallucinations.
- Approfondir la boucle humaine (feedback des rejets admin réinjecté en apprentissage des prompts/règles).
- Étendre l'observabilité (SLO de scraping, alertes qualité, dérive par source et par domaine).
