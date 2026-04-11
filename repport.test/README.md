# Plateforme NLP - Mémoire technique

## Présentation générale

Cette plateforme est une application web modulaire destinée à centraliser des fonctionnalités de gestion de contenus, de collaboration, de recherche et d’administration dans un environnement professionnel. L’architecture repose principalement sur une application Django, enrichie par des services asynchrones, un moteur de recherche, une base vectorielle et une couche de supervision.

Le projet est pensé pour être exécuté localement ou en conteneurs, avec une séparation claire entre :
- la couche métier Django,
- les services de persistance,
- les traitements asynchrones,
- l’indexation et la recherche,
- l’exposition via reverse proxy,
- la supervision et la qualité logicielle.

## Objectifs fonctionnels

La plateforme couvre les besoins suivants :
- authentification et gestion des comptes,
- administration centrale et paramétrage global,
- gestion de projets et collaboration entre membres,
- messagerie et notifications,
- publication de contenus et interactions communautaires,
- gestion de ressources et d’institutions,
- moteur de recherche interne et indexation avancée,
- support multilingue,
- traitements différés pour les tâches lourdes,
- supervision technique et observabilité.

## Architecture globale

### 1. Couche application
L’application principale est développée avec Django 5.1 et exposée via ASGI pour supporter les communications WebSocket ainsi que les requêtes HTTP classiques.

Composants principaux :
- `Plateforme/Plateforme/asgi.py` pour l’entrée ASGI,
- `Plateforme/Plateforme/wsgi.py` pour le mode WSGI,
- `Plateforme/Plateforme/settings.py` pour la configuration globale,
- `Plateforme/Plateforme/urls.py` pour le routage central.

### 2. Couche asynchrone
La plateforme utilise :
- Django Channels pour le temps réel,
- Redis comme broker et cache,
- Celery pour les tâches de fond,
- Celery Beat pour la planification périodique.

### 3. Couche données
Les données sont réparties entre :
- PostgreSQL avec l’extension `pgvector`,
- Redis pour le cache et les files de messages,
- Qdrant pour les vecteurs et recherches sémantiques,
- Elasticsearch pour l’indexation et la recherche textuelle.

### 4. Couche d’exposition
L’accès utilisateur passe par Nginx, qui joue le rôle de reverse proxy, de terminaison HTTP et de serveur pour les fichiers statiques et média.

### 5. Couche supervision
La supervision repose sur :
- Prometheus pour la collecte de métriques,
- Grafana pour les tableaux de bord,
- des règles d’alerte définies dans `monitoring/alerts.yml`.

## Stack technique

### Backend principal
- Python 3.11
- Django 5.1
- Django REST Framework
- Django Channels
- Celery
- Daphne
- Gunicorn
- Redis
- PostgreSQL
- Elasticsearch
- Qdrant
- Nginx

### Front et intégration
- Templates Django
- i18n / locale Django
- HTMX
- Bootstrap 5 via `crispy-bootstrap5`

### Qualité et validation
- Pytest
- Pytest-Django
- Pytest-Cov
- Ruff
- Bandit
- Pyright
- Playwright pour les scénarios de test navigateur

## Conteneurs et services Docker

Le fichier `docker-compose.yml` orchestre l’ensemble de la plateforme.

### Services principaux

- `db` : PostgreSQL avec `pgvector`
- `redis` : cache, broker et coordination
- `qdrant` : base vectorielle
- `elasticsearch` : moteur d’indexation et de recherche
- `django` : application principale
- `nginx` : reverse proxy
- `celery_worker` : traitement asynchrone côté service secondaire
- `django_celery_worker` : traitements de fond côté Django
- `django_celery_beat` : planification périodique

### Ports exposés
- `80` et `443` pour Nginx
- `8888` pour l’application Django
- `8000` pour le service HTTP secondaire
- `5432` pour PostgreSQL
- `6379` pour Redis
- `9200` pour Elasticsearch
- `6333` et `6334` pour Qdrant

### Volumes persistants
- `postgres_data`
- `redis_data`
- `qdrant_data`
- `elasticsearch_data`
- `static_volume`
- `media_volume`
- `fastapi_cache`

## Modules fonctionnels de la plateforme

### 1. Comptes et authentification
Le module `accounts` couvre :
- création et gestion des comptes,
- authentification par email,
- intégration Allauth,
- double facteur d’authentification,
- gestion OTP basée sur Redis,
- sécurité de session et contrôle d’accès.

### 2. Pages publiques et navigation
Le module `pages` gère :
- la page d’accueil,
- les pages de présentation,
- l’expérience utilisateur générale,
- les middlewares de sécurité associés à l’interface.

### 3. Projets
Le module `projects` centralise :
- la création et le suivi des projets,
- l’organisation des membres,
- les permissions de participation,
- les échanges liés aux projets,
- l’intégration temps réel via WebSocket.

### 4. Espace de discussion de projet
Le module `project_chatroom` fournit :
- un espace de discussion privé par projet,
- le chat temps réel,
- la gestion des messages,
- les pièces jointes,
- les indicateurs de frappe,
- le contrôle d’accès par statut d’adhésion.

### 5. Forum
Le module `forum` regroupe :
- les discussions communautaires,
- les fils de questions/réponses,
- les échanges publics structurés,
- les communications WebSocket associées.

### 6. Événements
Le module `events` permet :
- la publication d’événements,
- la consultation et l’inscription,
- l’animation de la communauté,
- l’exposition dans la recherche et les flux.

### 7. Ressources
Le module `resources` couvre :
- le dépôt de ressources,
- l’organisation documentaire,
- l’approbation et la publication,
- la consultation par catégorie.

### 8. Institutions et annuaire
Le module `institutions` sert à :
- référencer les institutions,
- structurer les relations avec l’écosystème,
- rendre les données institutionnelles consultables.

### 9. Flux d’activité
Le module `feed` agrège :
- les nouveautés,
- les mises à jour récentes,
- les activités du système,
- une vue consolidée des contenus utiles.

### 10. Notifications
Le module `notifications` prend en charge :
- les alertes utilisateur,
- les notifications temps réel,
- la diffusion via Channels,
- la synchronisation avec les événements applicatifs.

### 11. Messages directs
Le module `direct_messages` fournit :
- la messagerie privée entre utilisateurs,
- les échanges WebSocket,
- la persistance et la diffusion des messages.

### 12. Partage
Le module `sharing` gère :
- les mécanismes de mise à disposition des contenus,
- les partages entre utilisateurs ou groupes,
- les règles de visibilité.

### 13. Traduction et multilinguisme
Le module `translate` et la configuration i18n permettent :
- l’affichage multilingue,
- la prise en charge des langues de l’interface,
- l’adaptation à un contexte d’usage international.

### 14. Recherche
Le module `search` fournit :
- la recherche textuelle,
- l’intégration Elasticsearch,
- les index de modèles métiers,
- la mise en avant des contenus pertinents.

Les entités indexées incluent notamment :
- utilisateurs,
- cours,
- outils,
- corpus,
- documents,
- projets,
- événements,
- institutions.

### 15. Paramétrage global
Le module `settings` centralise :
- les informations de plateforme,
- les paramètres email,
- les notifications globales,
- les fonctionnalités activables par drapeaux,
- la sécurité,
- le mode maintenance.

## Configuration applicative

### Variables d’environnement importantes

Le projet s’appuie sur des variables d’environnement pour externaliser la configuration :

- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `ELASTICSEARCH_HOST`
- `QDRANT_HOST`
- `QDRANT_PORT`
- `QDRANT_GRPC_PORT`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `FASTAPI_URL`
- `FASTAPI_API_KEY`
- `ALLOWED_HOSTS`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`

### Paramètres de qualité et sécurité

Le dépôt contient aussi :
- `pytest.ini` pour la configuration des tests,
- `ruff.toml` pour le linting,
- `bandit.toml` pour l’analyse de sécurité,
- `pyrightconfig.json` pour l’analyse statique Python.

## Flux d’exécution

### Démarrage de l’application Django
Au démarrage, la commande de service :
- collecte les fichiers statiques,
- exécute les migrations,
- lance `daphne` sur le port applicatif.

### Gestion du temps réel
Le routage ASGI agrège plusieurs routes WebSocket pour :
- les notifications,
- les messages directs,
- les échanges de projets,
- le chatroom de projet.

### Tâches asynchrones
Les tâches lourdes sont isolées dans Celery pour :
- les traitements longs,
- les opérations différées,
- la planification périodique,
- le traitement en arrière-plan.

## Supervision et observabilité

La supervision technique s’appuie sur :
- Prometheus pour la collecte des métriques,
- Grafana pour la visualisation,
- des alertes configurées pour suivre la santé du système,
- des dashboards provisionnés automatiquement.

Le reverse proxy Nginx est configuré avec :
- compression gzip,
- limitation de taille des requêtes,
- journalisation d’accès,
- inclusion des configurations `conf.d`.

## Installation locale

### Prérequis
- Docker
- Docker Compose
- Python 3.11 si exécution hors conteneurs
- accès réseau pour récupérer les dépendances Python

### Démarrage avec Docker

```bash
docker-compose up --build
```

### Accès aux services
- Django : `http://localhost:8888`
- Nginx : `http://localhost`
- PostgreSQL : `localhost:5432`
- Redis : `localhost:6379`
- Elasticsearch : `localhost:9200`
- Qdrant : `localhost:6333`

### Initialisation base de données
Le script `init-db.sql` :
- active l’extension `vector`,
- prépare les privilèges de base,
- ajoute des colonnes manquantes si les tables existent déjà.

## Dépendances principales

Le fichier `Plateforme/requirements.txt` inclut notamment :
- Django,
- Channels,
- Daphne,
- django-allauth,
- django-redis,
- django-elasticsearch-dsl,
- crispy-forms,
- channels_redis,
- Celery,
- Playwright,
- sentence-transformers,
- pytesseract,
- PyMuPDF,
- python-docx,
- pytest et ses extensions.

## Dockerfiles

### Image Django
Le `Plateforme/Dockerfile` utilise :
- `python:3.11-slim`,
- `gcc`, `libpq-dev`, `curl`,
- installation des dépendances Python,
- création d’un utilisateur non-root pour l’exécution en production,
- `gunicorn` pour le mode production.

### Image Elasticsearch
Le `elasticsearch/Dockerfile` ajoute :
- `analysis-phonetic`,
- `analysis-icu`.

## Qualité logicielle

### Tests
Les tests utilisent :
- `pytest`,
- `pytest-django`,
- `pytest-asyncio`,
- `pytest-cov`,
- `pytest-mock`.

### Linting et sécurité
- `ruff` pour le style et la qualité,
- `bandit` pour l’analyse de sécurité,
- `pyright` pour la cohérence statique,
- `bandit` et `ruff` sont configurés pour ignorer certains dossiers générés ou spécifiques aux migrations.

### Commandes utiles

```bash
python manage.py test
pytest
ruff check .
bandit -r Plateforme
```

## Structure de haut niveau

```text
Plateforme_NLP/
├── docker-compose.yml
├── init-db.sql
├── nginx/
├── monitoring/
├── grafana/
├── prometheus/
├── Plateforme/
├── elasticsearch/
├── report.tex
└── repport.test/
```

## Notes de maintenance

- Le projet est prévu pour fonctionner de manière modulaire.
- Les composants Docker peuvent être lancés séparément si nécessaire.
- Les caches Redis doivent être pris en compte pour le temps réel, les OTP et les traitements asynchrones.
- L’indexation Elasticsearch doit être synchronisée avec les modèles métiers.
- Les volumes Docker doivent être conservés pour ne pas perdre les données persistantes.

## Conclusion

Cette plateforme combine une application web Django riche fonctionnellement, une architecture temps réel, une recherche avancée, des traitements asynchrones et une couche de supervision complète. Le tout est pensé pour être maintenable, conteneurisé et documenté comme base de mémoire technique.
