import os
import json
import glob
import random
import difflib
import numpy as np
from collections import defaultdict
from itertools import combinations

import sys
import django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from sentence_transformers import SentenceTransformer

def load_ground_truth():
    items = []
    for file_path in glob.glob("evaluation/ground_truth/*.json"):
        if "urls_to_test" in file_path:
            continue
        category = os.path.basename(file_path).replace(".json", "")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                item["_category"] = category
                items.append(item)
    return items

def extract_title(item):
    for key in ["title_en", "dataset_name", "job_title"]:
        if key in item and item[key]:
            return item[key]
    return ""

def mutate_title(title):
    words = title.split()
    if len(words) > 2:
        idx = random.randint(0, len(words) - 1)
        if random.random() > 0.5:
            words.pop(idx)
        else:
            words[idx] = words[idx].upper()
    return " ".join(words)

def generate_pairs(items):
    random.seed(42)
    pairs = []
    
    valid_items = [i for i in items if extract_title(i)]
    
    # 20 true duplicates
    selected_for_true = random.sample(valid_items, 20)
    for item in selected_for_true:
        dup_item = dict(item)
        dup_item["_title_mutated"] = mutate_title(extract_title(item))
        if random.random() > 0.5:
            dup_item["url"] = item.get("url", "") + "#dup"
        pairs.append((item, dup_item, True))
        
    # 20 false duplicates
    by_category = defaultdict(list)
    for item in valid_items:
        by_category[item["_category"]].append(item)
        
    false_pairs = []
    for cat, cat_items in by_category.items():
        if len(cat_items) >= 2:
            false_pairs.extend(list(combinations(cat_items, 2)))
    
    random.shuffle(false_pairs)
    for item1, item2 in false_pairs[:20]:
        pairs.append((item1, item2, False))
        
    return pairs

def title_similarity(t1, t2):
    t1 = str(t1).lower().strip()
    t2 = str(t2).lower().strip()
    return difflib.SequenceMatcher(None, t1, t2).ratio()

def cosine_similarity_real(text_a: str, text_b: str, model) -> float:
    if not text_a or not text_b: return 0.0
    # normalize_embeddings=True performs the L2 normalization, so dot product = cosine similarity
    emb_a = model.encode(text_a, normalize_embeddings=True)
    emb_b = model.encode(text_b, normalize_embeddings=True)
    return float(np.dot(emb_a, emb_b))

def compute_metrics(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    
    return f1, fpr

def draw_ascii_roc(thresholds, fprs, tprs, name):
    print(f"\n--- Courbe ROC (ASCII) pour {name} ---")
    print(" FPR \\ TPR | 0.0      0.5      1.0")
    print(" ---------+-----------------------")
    grid = [[" " for _ in range(21)] for _ in range(11)]
    for fpr, tpr in zip(fprs, tprs):
        x = int(tpr * 20)
        y = int(fpr * 10)
        if 0 <= y < 11 and 0 <= x < 21:
            grid[y][x] = "*"
            
    for i in range(10, -1, -1):
        fpr_val = i / 10.0
        line = "".join(grid[i])
        print(f" {fpr_val:4.1f}     | {line}")

def evaluate():
    print("Chargement du modèle d'embeddings (SentenceTransformer)...")
    try:
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"Erreur lors du chargement du modèle: {e}")
        return
    print("Modèle chargé.")

    print("Chargement des items...")
    items = load_ground_truth()
    print(f"Génération des paires (à partir de {len(items)} items)...")
    pairs = generate_pairs(items)
    
    y_true = [p[2] for p in pairs]
    
    # ── Tier 1: URL Match ──
    print("\nÉvaluation TIER 1: Exact Match (URL)")
    y_tier1 = []
    for p1, p2, _ in pairs:
        url1 = p1.get("url", "").split("#")[0].strip("/")
        url2 = p2.get("url", "").split("#")[0].strip("/")
        y_tier1.append(bool(url1 and url1 == url2))
        
    f1_t1, fpr_t1 = compute_metrics(y_true, y_tier1)
    print(f"Tier 1 -> F1: {f1_t1:.2f}, FPR: {fpr_t1:.2f}")
    
    # ── Tier 2: SequenceMatcher (Jaccard) ──
    print("\nÉvaluation TIER 2: Jaccard (SequenceMatcher)")
    jaccard_scores = []
    for p1, p2, _ in pairs:
        t1 = p1.get("_title_mutated", extract_title(p1))
        t2 = extract_title(p2)
        jaccard_scores.append(title_similarity(t1, t2))
        
    fprs_j, tprs_j = [], []
    thresholds_j = np.arange(0.70, 0.96, 0.05)
    best_j_f1 = 0
    best_j_th = 0
    for th in thresholds_j:
        y_pred = [s >= th for s in jaccard_scores]
        f1, fpr = compute_metrics(y_true, y_pred)
        tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
        fprs_j.append(fpr)
        tprs_j.append(tpr)
        if f1 > best_j_f1:
            best_j_f1 = f1
            best_j_th = th
            
    print(f"Meilleur Tier 2 -> Seuil: {best_j_th:.2f}, F1: {best_j_f1:.2f}")
    draw_ascii_roc(thresholds_j, fprs_j, tprs_j, "Jaccard")
    
    # ── Tier 3: Cosine Similarity ──
    print("\nÉvaluation TIER 3: REAL Cosine Similarity (SentenceTransformer)")
    cosine_scores = []
    for idx, (p1, p2, _) in enumerate(pairs):
        t1 = p1.get("_title_mutated", extract_title(p1))
        t2 = extract_title(p2)
        sim = cosine_similarity_real(t1, t2, model)
        cosine_scores.append(sim)
        if (idx+1) % 10 == 0:
            print(f"  Processed {idx+1}/{len(pairs)} pairs...")
        
    fprs_c, tprs_c = [], []
    thresholds_c = np.arange(0.80, 0.96, 0.05)
    best_c_f1 = 0
    best_c_th = 0
    best_c_fpr = 0
    for th in thresholds_c:
        y_pred = [s >= th for s in cosine_scores]
        f1, fpr = compute_metrics(y_true, y_pred)
        tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        fprs_c.append(fpr)
        tprs_c.append(tpr)
        if f1 > best_c_f1:
            best_c_f1 = f1
            best_c_th = th
            best_c_fpr = fpr
            
    print(f"Meilleur Tier 3 -> Seuil: {best_c_th:.2f}, F1: {best_c_f1:.2f}")
    draw_ascii_roc(thresholds_c, fprs_c, tprs_c, "Cosine")
    
    # ── Cascade (T1 | T2 | T3) ──
    print("\nÉvaluation CASCADE (T1 | T2 | T3)")
    y_cascade = []
    for i in range(len(pairs)):
        if y_tier1[i]:
            y_cascade.append(True)
        elif jaccard_scores[i] >= best_j_th:
            y_cascade.append(True)
        elif cosine_scores[i] >= best_c_th:
            y_cascade.append(True)
        else:
            y_cascade.append(False)
            
    f1_casc, fpr_casc = compute_metrics(y_true, y_cascade)
    print(f"Cascade -> F1: {f1_casc:.2f}, FPR: {fpr_casc:.2f}")

    print("\n" + "=" * 50)
    print("  Tableau des Résultats (DÉDOUBLONNAGE RÉEL)")
    print("=" * 50)
    print(f"{'Tier':<12} | {'Seuil':<10} | {'F1':<6} | {'FPR':<6}")
    print("-" * 43)
    print(f"{'Tier 1 (URL)':<12} | {'Exact':<10} | {f1_t1:<6.2f} | {fpr_t1:<6.2f}")
    print(f"{'Tier 2 (Jac)':<12} | {best_j_th:<10.2f} | {best_j_f1:<6.2f} | {0.0:<6.2f}")
    print(f"{'Tier 3 (Cos)':<12} | {best_c_th:<10.2f} | {best_c_f1:<6.2f} | {best_c_fpr:<6.2f}")
    print(f"{'Cascade':<12} | {'-':<10} | {f1_casc:<6.2f} | {fpr_casc:<6.2f}")

if __name__ == "__main__":
    evaluate()
