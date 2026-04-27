import json
import glob
import os
import random

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from scraping.intelligence import ConfidenceCalculator

def phase_a():
    print("=" * 60)
    print("  Évaluation Confidence - Phase A (Préparation)")
    print("=" * 60)
    
    calc = ConfidenceCalculator()
    all_items = []
    
    # 1. Load 10 items per category
    for file_path in glob.glob("evaluation/ground_truth/*.json"):
        if "urls_to_test" in file_path:
            continue
            
        category = os.path.basename(file_path).replace(".json", "")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Shuffle deterministically to get a random but consistent sample
        random.seed(42)
        random.shuffle(data)
        
        sample = data[:10]
        
        for idx, item in enumerate(sample):
            title = item.get("title_en") or item.get("dataset_name") or item.get("job_title") or "Unknown Title"
            url = item.get("url") or item.get("source_url") or ""
            
            # 2. Calculate confidence using the real calculator
            res = calc.calculate(category, item)
            confidence = res.get("percent", 0.0)
            
            all_items.append({
                "id": f"{category}_{idx+1}",
                "category": category,
                "title": title,
                "source_url": url,
                "calculated_confidence": confidence,
                "human_label": ""  # To be filled manually (1 to 5, or 0.0 to 1.0)
            })
            
    print(f"Loaded {len(all_items)} items for annotation.")
    
    # 3. Save to evaluation/annotations/confidence_to_annotate.json
    out_dir = "evaluation/annotations"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "confidence_to_annotate.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)
        
    print(f"\nGénéré: {out_path}\n")
    print("Voici les 10 premiers items générés :")
    print("-" * 60)
    for it in all_items[:10]:
        print(f"ID: {it['id']:<15} | Score calculé: {it['calculated_confidence']:>5.1f}% | Titre: {it['title'][:40]}...")

if __name__ == "__main__":
    phase_a()
