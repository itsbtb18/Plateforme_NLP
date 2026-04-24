# Plateforme NLP - Architecture detaillee du module Traduction / Resume

Ce document decrit en detail l architecture du module de traduction et de resume de la plateforme.

## 1. Vue globale

Le module est base sur un microservice FastAPI dedie:

- Service: `translation_summarization_service`
- API: `/health`, `/translate`, `/summarize`, `/chat`
- Providers LLM: Gemini et Groq
- Fallback final traduction: Google Translate (`deep_translator`)
- Fallback final resume: resume local heuristique
- Infrastructure de controle: Redis (cache + queue + mutex + pacing)
- Integration applicative: proxy Django dans `Plateforme/translate`

## 2. Architecture logique

### 2.1 Composants

1. Client (frontend ou endpoint Django)
2. Django proxy (`api/ts/translate`, `api/ts/summarize`, `api/ts/health`)
3. Microservice TS FastAPI
4. Orchestrateur central `TranslationSummarizationService`
5. Providers externes:
- Gemini API
- Groq API
6. Redis:
- cache de sortie
- file FIFO par utilisateur
- mutex global
- pacing global
7. Fallback local:
- Google Translate pour traduction
- resume local en cas d echec global

### 2.2 Flux haut niveau

#### Traduction

1. Requete API `/translate`
2. Validation + auth optionnelle (header `X-TS-Api-Key`)
3. Normalisation des langues (`fr`, `en`, `ar`, `auto`, aliases)
4. Preparation texte + chunking intelligent
5. Passage dans la queue utilisateur (si `user_id` present)
6. Prise de mutex global
7. Course parallele providers disponibles (Gemini/Groq)
8. Premier succes retourne resultat
9. Sinon fallback Google Translate
10. Cache resultat final et reponse API

#### Resume

1. Requete API `/summarize`
2. Validation + auth optionnelle
3. Preparation texte + decoupage sections
4. Queue utilisateur + mutex global
5. Course parallele providers
6. Si succes: rendu resume structure
7. Si timeout/echec global: fallback local
8. Cache resultat et reponse API

## 3. API exposee

### 3.1 GET /health

Retour:

```json
{
  "status": "ok",
  "primary_provider": "gemini",
  "fallback_provider": "groq"
}
```

### 3.2 POST /translate

Corps:

```json
{
  "text": "...",
  "source_language": "fr",
  "target_language": "en",
  "user_id": "optional"
}
```

Reponse:

```json
{
  "task": "translation",
  "output": "...",
  "provider_used": "gemini|groq|google|cache",
  "fallback_used": true
}
```

### 3.3 POST /summarize

Corps:

```json
{
  "text": "...",
  "language": "en",
  "style": "brief",
  "max_words": 300,
  "user_id": "optional"
}
```

Reponse:

```json
{
  "task": "summarization",
  "output": "...",
  "provider_used": "gemini|groq|local|local-timeout|cache",
  "fallback_used": true
}
```

### 3.4 POST /chat

Corps:

```json
{
  "system_prompt": "You are a helpful assistant.",
  "user_prompt": "...",
  "provider": "gemini",
  "user_id": "optional"
}
```

## 4. Orchestration interne

Le coeur est dans `TranslationSummarizationService`.

### 4.1 Ordre providers

- `TS_PRIMARY_PROVIDER`
- `TS_FALLBACK_PROVIDER`

Validation automatique des valeurs invalides.

### 4.2 Execution parallele et premier succes

Le service lance Gemini et Groq en parallele (si disponibles), puis:

- prend le premier provider qui reussit
- annule les taches restantes

Effet: reduction forte de latence vs fallback strictement sequentiel.

### 4.3 Timeout court par provider

Chaque appel provider est enveloppe dans `asyncio.wait_for` avec timeout dedie (`TS_PROVIDER_TIMEOUT_SECONDS`).

### 4.4 Limitation de concurrence

Semaphore global provider:

- `TS_PROVIDER_MAX_CONCURRENCY`

Permet de limiter le nombre d appels IA concurrents.

### 4.5 Delai anti burst

Avant appel provider:

- `TS_PROVIDER_CALL_DELAY_SECONDS`

Permet de lisser le trafic et eviter les spikes.

## 5. Resilience avancee

### 5.1 Retry + backoff exponentiel

Pour erreurs transitoires et rate limit:

- retries: `TS_RATE_LIMIT_MAX_RETRIES`
- backoff: `2^(attempt+1)` avec cap
- respect potentiel de `Retry-After`

### 5.2 Cooldown rate limit

Si 429 ou quota:

- cooldown provider temporaire
- hard quota cooldown plus long

### 5.3 Circuit breaker

Compteur d echecs consecutifs par provider:

- seuil: `TS_CIRCUIT_BREAKER_THRESHOLD`
- cooldown: `TS_CIRCUIT_BREAKER_COOLDOWN_SECONDS`

Si seuil atteint, provider ignore temporairement.

### 5.4 Fallback final garanti

- Traduction: fallback Google Translate (chunks plus petits)
- Resume: fallback local (extraction resumee)

## 6. Gestion des textes longs

### 6.1 Nettoyage

- normalisation retours ligne
- reduction espaces
- correction cesures PDF

### 6.2 Chunking intelligent

- split intelligent (langchain si dispo)
- fallback simple si dependance absente
- overlap configurable

### 6.3 Rebalancing

Limite nombre de chunks via:

- `TS_TRANSLATION_MAX_CHUNKS_PER_DOCUMENT`

### 6.4 Protection contre "faux resume"

Apres traduction, verification heuristique pour detecter output trop compresse.

## 7. Queue et equite utilisateur

Si `user_id` est present:

1. hash user -> scope
2. insertion FIFO dans Redis list
3. attente tour en tete de file
4. release explicite apres traitement

Evite qu un utilisateur monopolise le service.

## 8. Mutex global et pacing

### 8.1 Mutex global Redis

Cle lock:

- `ts:scheduler:mutex`

Protege contre surcharge interne et collisions.

### 8.2 Pacing global

Le service impose un intervalle minimal global entre appels provider, base sur:

- `TS_GLOBAL_REQUESTS_PER_MINUTE`
- `TS_GLOBAL_MIN_INTERVAL_SECONDS`

## 9. Cache Redis

Namespaces:

- `ts:translation`
- `ts:summary`

Cache base sur hash du payload normalise.

Objectif:

- eviter recalculs sur memes requetes
- baisser cout et latence

## 10. Prompts et qualite

`PromptEngine` applique des consignes strictes:

### 10.1 Traduction

- traduction complete (pas de resume)
- preservation structure document
- conservation termes techniques / code / URLs

### 10.2 Resume

- style et langue parametrables
- mode section pour documents longs
- format de sortie coherent

## 11. Integration Django

Le service est consomme via `Plateforme/translate`:

- `ts_client.py`: client HTTP sync
- `views.py`: endpoints proxy
- `urls.py`: routes API TS

Endpoints exposant le proxy:

- `/api/ts/translate/`
- `/api/ts/summarize/`
- `/api/ts/health/`

Note:

- `ts_health()` inclut un cache local TTL pour eviter de spammer le microservice TS.

## 12. Deploiement Docker

Service `translation_summarization` dans `docker-compose.yml`:

- port: `8010`
- healthcheck: `/health` toutes les 30s
- variables env de throttling/retry/chunking injectees

Exemple de parametres de stabilite:

- `TS_TRANSLATION_CHUNK_SIZE=400`
- `TS_TRANSLATION_MAX_CHUNKS_PER_DOCUMENT=5`
- `TS_PROVIDER_TIMEOUT_SECONDS=10`
- `TS_PROVIDER_CALL_DELAY_SECONDS=0.3`
- `TS_PROVIDER_MAX_CONCURRENCY=2`
- `TS_RATE_LIMIT_MAX_RETRIES=3`

## 13. Gestion erreurs HTTP

Le service mappe les erreurs vers:

- 429: rate limit / queue saturation
- 502: erreurs provider auth/techniques

Message client simplifie et securise.

## 14. Observabilite

Logs structurants:

- start/end requete
- provider utilise
- fallback utilise
- retries et delais
- activation circuit breaker
- fallback local/Google

## 15. Bonnes pratiques d exploitation

1. Eviter polling agressif de `/health`
2. Garder healthcheck docker >= 30s
3. Ajuster chunking selon charge et type document
4. Conserver une concurrence provider faible au debut
5. Monitorer ratio fallback et 429
6. Verifier quotas API Gemini/Groq

## 16. Fichiers techniques importants

- `translation_summarization_service/app/main.py`
- `translation_summarization_service/app/service.py`
- `translation_summarization_service/app/config.py`
- `translation_summarization_service/app/prompt_engine.py`
- `translation_summarization_service/app/providers/gemini_provider.py`
- `translation_summarization_service/app/providers/groq_provider.py`
- `translation_summarization_service/app/schemas.py`
- `Plateforme/translate/ts_client.py`
- `Plateforme/translate/views.py`
- `Plateforme/translate/urls.py`
- `docker-compose.yml`

---

Si besoin, je peux aussi generer une version "architecture diagram" (Mermaid) et une section "runbook production" (incident 429, timeout, fallback loops, queue saturation).
