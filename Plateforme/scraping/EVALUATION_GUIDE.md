# Guide d'Évaluation — Module de Web Scraping
# Plateforme NLP Multilingue · Avril 2026

---

## PARTIE 1 — Analyse Critique : Ce qui s'applique et ce qui ne s'applique PAS

Le rapport d'évaluation proposé contient **5 composants**. Voici l'analyse honnête, composant par composant, confrontée à votre code réel.

---

### ✅ Composant 1 — Extraction LLM : **S'APPLIQUE** (avec corrections)

**Ce qui est correct :**
- Votre module utilise bien `GroqLLMClient` (dans `extractors/core/llm_validation.py`) avec Gemini/Groq pour extraire des champs structurés (titre, date, lieu, description, URL) depuis du contenu web.
- Le F1 par champ et la détection d'hallucinations sont des métriques pertinentes.
- Le BERTScore est adapté pour évaluer les champs textuels (titre, description).

**Ce qui doit être corrigé :**
- Le rapport propose 50 items (20 events + 15 tools + 15 news). **Il manque 3 catégories** : courses, corpus, opportunities. Votre module en supporte 6, pas 3.
- Le rapport ne mentionne pas la validation LLM post-extraction (`LLMValidator.validate()`) qui ajoute un 2e passage LLM pour le quality_score, is_relevant, is_spam. Cette couche doit aussi être évaluée.
- Les champs à évaluer varient par catégorie. Pour les events c'est `title_en, start_date, location_en, description_en, event_type`. Pour les tools c'est `title_en, description_en, tool_type, access_link`. Le rapport générique ne reflète pas ces différences.

**Formule BERTScore** : ✅ Correcte et applicable.

---

### ✅ Composant 2 — Découverte Tavily : **S'APPLIQUE** (avec ajustements)

**Ce qui est correct :**
- Votre module utilise bien `TavilySearchClient` (dans `network/search_client.py`).
- Precision@k, Recall@k, MRR sont les bonnes métriques pour évaluer un système de retrieval.

**Ce qui doit être corrigé :**
- Le rapport ne mentionne pas la **rotation de clés API** (primary + backup). L'évaluation devrait mesurer le comportement en cas de basculement.
- Le rapport ne couvre pas les **requêtes personnalisées** (custom AI Prompts depuis `ScrapingSource.scrape_config`). L'évaluation devrait comparer les requêtes par défaut vs. les requêtes custom.
- Votre EventScraper utilise aussi du **CSS-based discovery** direct (crawling HTML de sites connus), pas seulement Tavily. Le rapport ignore complètement ce canal de découverte.

---

### ⚠️ Composant 3 — Déduplication : **PARTIELLEMENT APPLICABLE** (incomplet)

**Ce qui est correct :**
- Votre module utilise bien Jaccard pour la déduplication fuzzy des titres.
- L'analyse du seuil (0.70 à 0.95) et la courbe ROC sont pertinentes.

**Ce qui est FAUX ou MANQUANT :**

Le rapport évalue **uniquement** le seuil Jaccard. Or votre module implémente **3 niveaux** de déduplication en cascade :

| Niveau | Méthode | Code source | Évalué dans le rapport ? |
|--------|---------|-------------|--------------------------|
| Tier 1 | Exact match (URL, DOI, arXiv ID, ROR ID) | `_check_duplicate_policy()` | ❌ NON |
| Tier 2 | Fuzzy Jaccard (`SequenceMatcher`) | `_find_semantic_title_match()` | ✅ OUI |
| Tier 3 | Semantic embeddings pgvector (cosine similarity 0.88) | `embeddings.py` → `find_semantic_duplicate()` | ❌ NON |

**De plus**, le seuil n'est pas unique :
- `SCRAPING_JACCARD_THRESHOLD = 0.85` (pour events, news)
- `SCRAPING_STRICT_JACCARD = 0.90` (pour tools, courses, institutions)
- `SCRAPING_SEMANTIC_THRESHOLD = 0.88` (pour pgvector)

Le rapport utilise un seul seuil (0.85). C'est incomplet.

**Ce qui manque aussi :**
- La translitération phonétique arabe (`_transliterate_to_phonetic()`, `get_semantic_hash()`) qui normalise les titres cross-script avant comparaison. Aucune évaluation de cette composante.
- Les règles de dédup **par catégorie** sont différentes (events = URL + date range, tools = GitHub URL + access_link, news = DOI/arXiv). Le rapport les traite comme identiques.

---

### ⚠️ Composant 4 — Score de Confiance : **PARTIELLEMENT APPLICABLE** (formule incorrecte)

**Ce qui est FAUX :**

Le rapport propose cette formule :
```
S_c = [Σ (w_i × I(f_i))] / [Σ w_i]
Avec: title=10, date=8, url=5, location=6, description=4
```

**Votre code réel** dans `intelligence.py` → `ConfidenceCalculator` utilise :

```python
# Events (votre vrai code) :
FIELD_WEIGHTS = {
    "title_en": 0.25, "title": 0.05, "description_en": 0.20,
    "description": 0.05, "start_date": 0.10, "scraped_date": 0.05,
    "source_url": 0.10, "source_domain": 0.05, "url": 0.05,
    "location_en": 0.05, "location": 0.03, "end_date": 0.02,
}
```

Les poids sont **complètement différents** et sont des fractions (0.0-1.0), pas des entiers (4-10).

**Autres différences majeures :**

| Aspect | Rapport proposé | Votre code réel |
|--------|----------------|-----------------|
| Valeur I(f_i) | Binaire (0 ou 1) | Continue (0.0-1.0) via `score_field()` avec courbes exponentielles |
| Seuil minimum | 0.35 | `SCRAPING_MIN_CONFIDENCE = 30.0` (sur 100) |
| Bonus présence | Absent | `presence_ratio >= 0.5 → floor 58%`, `>= 0.7 → floor 68%` |
| Cap traduction | Absent | `apply_translation_confidence_cap()` → cap à 85 si non traduit |
| Credit traduction | Absent | `translation_field_credit()` → 0.0 à 1.0 selon statut |
| Poids par catégorie | Un seul jeu | 6 jeux différents (events, tools, news, corpus, courses, opportunities) |

La courbe Precision-Recall reste une bonne approche, mais avec **vos vrais poids et votre vraie formule**.

---

### ✅ Composant 5 — Évaluation Humaine : **S'APPLIQUE** (bien adapté)

**Ce qui est correct :**
- Les 5 critères Likert (exactitude, complétude, pertinence NLP, hallucination, fraîcheur) sont tous pertinents.
- Le Cohen's Kappa est la bonne métrique pour l'accord inter-annotateurs.
- L'analyse des erreurs par composant responsable est excellente et très actionable.

**Ce qui doit être ajusté :**
- L'échantillon de 35 items (15+10+10) ne couvre que 3 catégories sur 6. Ajouter corpus, courses et opportunities.
- Ajouter un critère "Qualité de la traduction arabe" (votre module gère le bilinguisme EN/AR).

---

### ❌ Éléments du rapport qui NE S'APPLIQUENT PAS du tout

| Élément mentionné | Pourquoi ça ne s'applique pas |
|-------------------|-------------------------------|
| "Index BM25" et "reconstruction automatique" | Votre module n'utilise PAS BM25. La recherche est faite via Tavily API, pas un index local. |
| "Migrer le dead letter de JSON vers DB" | C'est une recommandation d'amélioration, pas une évaluation. |

---

### 🔴 Composants de VOTRE module NON COUVERTS par le rapport

Le rapport proposé **ignore complètement** ces composants critiques de votre système :

| Composant manquant | Fichier source | Pourquoi l'évaluer |
|-------------------|---------------|-------------------|
| NetworkValidator (5 probes) | `validators/network_validator.py` | Taux de faux positifs RED, temps de validation |
| ContentValidator (keyword relevance) | `validators/content_validator.py` | Taux de filtrage, items pertinents rejetés à tort |
| Circuit Breaker | `scrapers/circuit_breaker.py` | Temps de récupération, faux positifs OPEN |
| Source Health Scoring | `models.py` → `ScrapingSourceHealth` | Corrélation health score vs. qualité réelle |
| Dead Letter Queue | `dead_letter.py` | Volume, types d'erreurs, taux de récupération |
| Translation Pipeline | `utils.py` | Qualité détection copied vs. translated |
| Field Mapping Completeness | `field_mapping.py` | Couverture des champs par catégorie |

---

## PARTIE 2 — Comment Évaluer Correctement Votre Module

### Protocole Complet en 7 Composants

---

### ÉVAL-1 : Qualité d'Extraction LLM

**Objectif** : Mesurer la fidélité de l'extraction LLM par champ.

**Protocole :**
1. Construire un ground truth de **60 items** : 10 par catégorie (events, tools, news, courses, corpus, opportunities).
2. Pour chaque item : visiter la vraie page, annoter manuellement tous les champs.
3. Exécuter `_extract_single_candidate()` (de `direct_scrape.py`) sur chaque URL.
4. Comparer champ par champ.

**Métriques :**

| Métrique | Type de champ | Formule |
|----------|--------------|---------|
| Exact Match | date, URL, event_type, tool_type | `1 si identique, 0 sinon` |
| BERTScore F1 | title_en, description_en | `F_BERT = 2×P×R/(P+R)` |
| Taux d'hallucination | Tous | `champs_inventés / champs_total` |

**Présentation des résultats :**

```
Catégorie    | Titre F1 | Date EM | URL EM | Desc F1 | Halluc. %
-------------|----------|---------|--------|---------|----------
events       | 0.94     | 0.78    | 0.85   | 0.91    | 6.7%
tools        | 0.92     | —       | 0.83   | 0.88    | 13.3%
news         | 0.95     | 0.81    | 0.87   | 0.90    | 6.7%
courses      | ?        | ?       | ?      | ?       | ?
corpus       | ?        | ?       | ?      | ?       | ?
opportunities| ?        | ?       | ?      | ?       | ?
```

---

### ÉVAL-2 : Qualité de Découverte (Retrieval Tavily)

**Objectif** : Mesurer si Tavily trouve les bonnes pages.

**Protocole :**
1. Construire un test set de **30 items connus** (5 par catégorie) avec URLs exactes.
2. Pour chaque item, définir la requête qui devrait le trouver.
3. Exécuter `TavilySearchClient.search_{category}()` pour chaque requête.
4. Vérifier si l'URL attendue apparaît dans les top-5 résultats.

**Métriques :**
- `Precision@5 = |pertinents ∩ top-5| / 5`
- `Recall@5 = |pertinents ∩ top-5| / |pertinents|`
- `MRR = (1/|Q|) × Σ(1/rank_i)`

---

### ÉVAL-3 : Qualité de Déduplication (3 niveaux)

**Objectif** : Évaluer les 3 tiers de déduplication séparément.

**Protocole :**
1. Construire un dataset de **40 paires** : 20 vrais doublons + 20 faux doublons.
2. Pour chaque paire, exécuter les 3 niveaux et noter lequel la détecte.

**Métriques par tier :**

```
Tier    | Méthode                    | Seuil  | Precision | Recall | F1
--------|----------------------------|--------|-----------|--------|----
Tier 1  | Exact URL/DOI/arXiv        | exact  | ?         | ?      | ?
Tier 2  | Jaccard (SequenceMatcher)  | 0.85   | ?         | ?      | ?
Tier 3  | pgvector cosine            | 0.88   | ?         | ?      | ?
CASCADE | Les 3 combinés             | —      | ?         | ?      | ?
```

**Analyse du seuil Jaccard :**
Faire varier de 0.70 à 0.95 et tracer la courbe ROC. Faire la même chose pour le seuil cosine (0.80 à 0.95).

**Évaluation de la translitération phonétique :**
Tester avec des paires arabe/anglais qui désignent le même item (ex: "مؤتمر ACL" vs "ACL Conference").

---

### ÉVAL-4 : Score de Confiance (ConfidenceCalculator)

**Objectif** : Valider que votre `ConfidenceCalculator` (intelligence.py) discrimine bien les bons items des mauvais.

**Protocole :**
1. Collecter **100 items** de votre base (via `ScrapedItemMeta.confidence_score`).
2. Annoter manuellement chacun : bon (1) ou mauvais (0).
3. Tracer la courbe Precision-Recall en faisant varier le seuil de 0 à 100.

**Formule RÉELLE de votre code :**
```
raw_score = Σ(weight_i × score_field(f_i)) / Σ(weight_i)

Avec score_field():
  - Texte : 0.12 + 0.86 × (1 - e^(-len/70))    # courbe exponentielle
  - Date ISO : 1.0 | Date partielle : 0.85 | Année seule : 0.7
  - URL https : 1.0 | http : 0.95 | autre : 0.2
  - Absent : 0.0

Puis ajustement :
  - Si >= 50% champs présents → floor à 58%
  - Si >= 70% champs présents → floor à 68%
  - Cap à 85% si translation_status != "translated"
```

**Présentation :**

```
Seuil | Precision | Recall | F1   | Items sauvés | Bons perdus
------|-----------|--------|------|--------------|------------
20    | ?         | ?      | ?    | ?            | ?
30 ✓  | ?         | ?      | ?    | ?            | ?
40    | ?         | ?      | ?    | ?            | ?
50    | ?         | ?      | ?    | ?            | ?
```

---

### ÉVAL-5 : Validation Pré-vol (Network + Content)

**Objectif** : Mesurer l'efficacité du filtrage avant extraction LLM.

**Protocole :**
1. Préparer **50 URLs** : 25 valides et pertinentes + 25 invalides ou hors-sujet.
2. Exécuter `NetworkValidator(url).run()` et `ContentValidator(url, category).run()`.
3. Mesurer le taux de filtrage correct.

**Métriques :**

| Validator | True Reject | False Reject | True Pass | False Pass |
|-----------|------------|-------------|-----------|------------|
| Network   | ?          | ?           | ?         | ?          |
| Content   | ?          | ?           | ?         | ?          |
| Combiné   | ?          | ?           | ?         | ?          |

**Impact économique** : Calculer le nombre d'appels LLM évités grâce au filtrage pré-vol.

---

### ÉVAL-6 : Résilience (Circuit Breaker + Source Health)

**Objectif** : Vérifier le comportement du système sous stress.

**Protocole :**
1. Simuler des échecs répétés sur une source et vérifier les transitions CLOSED→OPEN→HALF_OPEN.
2. Mesurer le temps de récupération après quarantaine.
3. Vérifier que le health score décroît correctement (decay exponentiel : -5, -10, -20, -40, -50).

**Métriques :**

| Test | Attendu | Résultat |
|------|---------|----------|
| 5 échecs → OPEN | Circuit s'ouvre | ? |
| 300s après OPEN → HALF_OPEN | Probe autorisé | ? |
| Probe réussit → CLOSED | Circuit se ferme | ? |
| Probe échoue → OPEN | Circuit reste ouvert | ? |

---

### ÉVAL-7 : Évaluation Humaine

**Objectif** : Capturer la qualité perçue qui échappe aux métriques automatiques.

**Protocole :**
1. Exporter **48 items** de la base : 8 par catégorie.
2. 2-3 annotateurs évaluent chaque item sur 6 critères (Likert 1-5).

**6 Critères adaptés à votre module :**

| Critère | 5 — Excellent | 3 — Acceptable | 1 — Insuffisant |
|---------|--------------|----------------|-----------------|
| Exactitude factuelle | Tous les champs corrects | 1 erreur mineure | Infos incorrectes |
| Complétude | Tous les champs importants | 1 champ manquant | Champs critiques absents |
| Pertinence NLP | Clairement NLP/IA | Lié à l'IA mais pas NLP | Sans rapport |
| Absence d'hallucination | Tout vérifiable | 1 détail suspect | Champs inventés |
| Fraîcheur | Item actuel | Ancien mais pertinent | Obsolète |
| **Qualité traduction AR** | Arabe correct et naturel | Compréhensible | Copié de l'anglais ou absent |

**Accord inter-annotateurs** : Cohen's Kappa ≥ 0.60 requis pour chaque critère.

---

## PARTIE 3 — Tableau Récapitulatif Final

```
# | Composant              | Métriques                        | Cible
--|------------------------|----------------------------------|----------
1 | Extraction LLM         | F1/champ, BERTScore, Halluc. %   | F1≥0.85, Halluc<10%
2 | Découverte Tavily       | P@5, R@5, MRR                    | P@5≥0.70, MRR≥0.75
3 | Déduplication (3 tiers) | F1 par tier, FPR, Courbe ROC     | F1≥0.88, FPR<8%
4 | Score Confiance         | Courbe P-R, AUC, seuil optimal   | AUC≥0.85, F1≥0.80
5 | Validation Pré-vol      | True/False Reject/Pass rates     | FalseReject<5%
6 | Résilience              | Temps récupération, transitions   | Recovery<5min
7 | Évaluation Humaine      | Likert moyen, Cohen's Kappa       | Moy≥3.8, κ≥0.60
```

---

## PARTIE 4 — Erreurs du Rapport Original à Corriger

| # | Erreur dans le rapport | Correction |
|---|----------------------|------------|
| 1 | Formule S_c avec poids entiers (title=10) | Utiliser vos vrais poids fractionnaires (title_en=0.25) |
| 2 | I(f_i) binaire (0/1) | Votre `score_field()` retourne des valeurs continues avec courbe exponentielle |
| 3 | Seuil unique 0.85 | Votre code a 3 seuils : 0.85, 0.90, 0.88 |
| 4 | Seuil confiance 0.35 | Votre code utilise `SCRAPING_MIN_CONFIDENCE = 30.0` (sur 100) |
| 5 | 3 catégories (events, tools, news) | Votre module supporte 6 catégories |
| 6 | Dédup = Jaccard seul | Votre système a 3 tiers : exact + Jaccard + pgvector |
| 7 | Mention de "BM25" | N'existe pas dans votre module |
| 8 | Pas de validation pré-vol | Votre module a NetworkValidator + ContentValidator |
| 9 | Pas de circuit breaker | Votre module a RedisCircuitBreaker + SourceHealth |
| 10 | Pas de traduction AR | Votre module gère le bilinguisme avec 6 statuts de traduction |

---

*Ce guide est basé sur l'analyse complète du code source de votre module scraping (~14,900 lignes).*
*Chaque recommandation correspond à un composant réel de votre implémentation.*
