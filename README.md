# Plateforme_NLP

Plateforme_NLP est une plateforme multi-services orientée NLP qui combine :

- une application Django (portail principal)
- un backend FastAPI (chatbot, ingestion, RAG)
- un microservice dédié Traduction / Résumé (TS)
- une stack de données (PostgreSQL, Redis, Qdrant, Elasticsearch)
- des workers Celery et un reverse proxy Nginx

Ce README documente la structure globale du projet, puis détaille le fonctionnement technique des outils de traduction et de résumé.

## 1) Vue d'ensemble architecture

Le flux principal est le suivant :

1. Le frontend et les vues Django reçoivent les actions utilisateur.
2. Django peut déléguer des fonctions IA au backend FastAPI ou au service TS.
3. Le service TS applique la traduction/résumé avec providers configurables (Gemini, Groq) + fallback Google Translate.
4. Redis est utilisé pour cache, file d'attente utilisateur et régulation des appels.
5. Les workers Celery traitent les tâches asynchrones (documents, scraping, post-traitement).

## 2) Structure du repository (niveau macro)

- Plateforme/
- fastapi_chatbot/
- translation_summarization_service/
- scraping/ et scraping_data/
- elasticsearch/ et nginx/
- data/ (volumes persistants locaux)
- tests et scripts à la racine

### Détail des dossiers critiques

- Plateforme/
Application Django principale (auth, forum, projets, traductions, etc.).

- Plateforme/translate/
Passerelle Django vers le microservice TS.
Contient le client HTTP synchrone et les endpoints proxy.

- fastapi_chatbot/
Service FastAPI IA (chat, ingestion, recherche vectorielle, orchestrations).

- translation_summarization_service/
Microservice autonome de traduction/résumé.

- translation_summarization_service/app/
Code applicatif TS :
- main.py : API FastAPI (/health, /translate, /summarize, /chat)
- service.py : orchestration providers, chunking, retries, fallback, cache
- config.py : variables d'environnement TS
- prompt_engine.py : prompts de traduction/résumé
- providers/gemini_provider.py : provider Gemini
- providers/groq_provider.py : provider Groq
- schemas.py : modèles de requêtes/réponses

- translation_summarization_service/tests/
Tests du comportement de fallback, cache, rate-limit et file d'attente.

- docker-compose.yml
Orchestration complète des services avec profils (scraping, full, scheduler).

## 3) Services Docker (résumé)

Le projet tourne principalement via Docker Compose.

Services clés :

- db : PostgreSQL + pgvector
- redis : broker/cache/queue
- qdrant : base vectorielle
- elasticsearch : moteur de recherche
- django : application web principale
- fastapi : backend IA
- translation_summarization : microservice TS dédié
- celery_worker : worker FastAPI
- django_celery_worker : worker scraping côté Django
- django_celery_beat : scheduler périodique
- nginx : reverse proxy

## 4) Outils techniques de traduction et résumé

### 4.1 API du microservice TS

Le microservice expose :

- GET /health
Retourne statut + provider primaire + provider fallback.

- POST /translate
Entrée : text, source_language, target_language, user_id optionnel.
Sortie : task, output, provider_used, fallback_used.

- POST /summarize
Entrée : text, language, style, max_words, user_id optionnel.
Sortie : task, output, provider_used, fallback_used.

- POST /chat
Endpoint utilitaire multi-provider orienté prompts (system_prompt/user_prompt).

### 4.2 Providers et stratégie de fallback

Ordre provider configurable :

- TS_PRIMARY_PROVIDER (gemini ou groq)
- TS_FALLBACK_PROVIDER (gemini ou groq)

Comportement en cas d'échec :

1. Provider primaire essayé en premier.
2. Si rate-limit, erreur réseau transitoire, ou échec de génération, bascule sur fallback.
3. Si les deux providers échouent, fallback final vers Google Translate via deep-translator pour la traduction.

Le service retourne explicitement provider_used et fallback_used, ce qui simplifie l'observabilité.

### 4.3 Résilience et contrôle de charge

Le service TS implémente :

- Retry exponentiel pour erreurs 429 / rate-limit
- Détection d'erreurs réseau transitoires (timeout, DNS, connection reset/refused)
- Cooldown provider après rate-limit
- File d'attente FIFO par utilisateur
- Mutex global anti-concurrence agressive
- Pacing global entre requêtes (throttling)

### 4.4 Qualité de traduction/résumé

Techniques appliquées dans le moteur :

- Prétraitement texte : nettoyage, normalisation d'espaces, correction des césures PDF
- Chunking intelligent via langchain-text-splitters (avec fallback interne)
- Rebalancing des chunks pour limiter la fragmentation
- Détection de sortie "résumée" quand une traduction complète est attendue
- Post-traitement pour lisibilité (ponctuation, sauts de ligne)

### 4.5 Chunking configurable (important)

Variables clés :

- TS_TRANSLATION_CHUNK_SIZE
- TS_TRANSLATION_CHUNK_OVERLAP
- TS_TRANSLATION_MAX_CHUNKS_PER_DOCUMENT
- TS_GOOGLE_FALLBACK_CHUNK_SIZE

Le fallback Google utilise des chunks plus petits que la chaîne LLM principale pour réduire les échecs sur textes longs.

## 5) Intégration Django vers TS

La passerelle Django se trouve dans Plateforme/translate :

- ts_client.py
Client HTTP synchrone qui appelle le service TS et remonte les erreurs de manière explicite.

- views.py
Endpoints proxy protégés :
- POST /api/ts/translate/
- POST /api/ts/summarize/
- GET /api/ts/health/

- urls.py
Déclare les routes API TS côté application Django.

## 6) Variables d'environnement principales

Le template recommandé est .env.example.

Variables critiques pour TS :

- TS_SERVICE_PORT
- TS_SERVICE_API_KEY
- TS_PRIMARY_PROVIDER
- TS_FALLBACK_PROVIDER
- TS_GEMINI_API_KEY
- TS_GROQ_API_KEY
- TS_GROQ_TRANSLATION_MODEL
- TS_GROQ_SUMMARIZATION_MODEL
- TS_PROVIDER_HTTP_TIMEOUT_SECONDS
- TS_TRANSLATION_CHUNK_SIZE
- TS_TRANSLATION_CHUNK_OVERLAP
- TS_TRANSLATION_MAX_CHUNKS_PER_DOCUMENT
- TS_GOOGLE_FALLBACK_CHUNK_SIZE

Variables critiques infra :

- POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
- REDIS_PASSWORD
- DJANGO_SECRET_KEY
- FASTAPI_URL, FASTAPI_API_KEY

## 7) Démarrage rapide

### 7.1 Préparer la configuration

1. Copier .env.example vers .env
2. Renseigner les clés API (au minimum Gemini et/ou Groq)
3. Vérifier les secrets Django/DB/Redis

### 7.2 Lancer la stack complète

Commande typique :

docker compose --profile full up -d --build

Option scheduler (beat) :

docker compose --profile scheduler up -d --build

### 7.3 Vérifier l'état

- Health TS : http://localhost:8010/health
- Health Django via Nginx : http://localhost/health
- Health FastAPI : http://localhost:8001/health (selon mapping)

## 8) Tests et validation

Tests ciblés TS :

pytest translation_summarization_service/tests/test_service_fallback.py -q

Ces tests couvrent notamment :

- ordre primaire/fallback
- fallback provider
- fallback Google traduction
- cache de chunks
- gestion rate-limit
- contraintes de file d'attente

## 9) Diagnostic des erreurs de traduction/résumé

### Cas fréquent : erreur 502 All providers failed

Vérifications prioritaires :

1. Vérifier TS_GEMINI_API_KEY et TS_GROQ_API_KEY dans .env
2. Vérifier que le container translation_summarization est bien running
3. Vérifier la connectivité sortante du container vers APIs providers
4. Consulter ts_logs.txt et logs Docker du service TS
5. Tester /health puis /translate avec un payload court

### Cas fréquent : 429 Too Many Requests

Actions recommandées :

- réduire parallélisme côté appelant
- ajuster TS_RATE_LIMIT_MAX_RETRIES / TS_RATE_LIMIT_MAX_WAIT_SECONDS
- ajuster TS_TRANSLATION_CHUNK_SIZE pour limiter pression provider

## 10) Bonnes pratiques opérationnelles

- Ne jamais committer les secrets réels dans .env
- Garder TS_SERVICE_API_KEY non vide en environnement partagé
- Surveiller logs provider_used et fallback_used pour anticiper saturation
- Séparer les clés API par usage (chat, internal, scraping, TS) si possible
- Conserver des valeurs de chunking adaptées aux langues et à la taille des documents

## 11) Références internes utiles

- docker-compose.yml
- .env.example
- Plateforme/translate/ts_client.py
- Plateforme/translate/views.py
- translation_summarization_service/app/main.py
- translation_summarization_service/app/service.py
- translation_summarization_service/app/config.py
- translation_summarization_service/tests/test_service_fallback.py

---

Si nécessaire, ce README peut être complété par :

- un diagramme d'architecture détaillé (réseau + flux API)
- un tableau de troubleshooting par code HTTP
- une section performance tuning par workload (petits textes vs longs documents)
