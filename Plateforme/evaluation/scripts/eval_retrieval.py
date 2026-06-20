import asyncio
import json
import os
import sys
import django
import re
from urllib.parse import urlparse
from typing import List, Dict

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from scraping.network.search_client import TavilySearchClient

GT_PATH = "evaluation/ground_truth/"
CATEGORIES = ["events", "tools", "courses", "news", "opportunities", "corpus"]

def normalize_url(url: str) -> dict:
    """Extrait les identifiants canoniques d'une URL pour un matching flexible."""
    if not url:
        return {"type": "none", "id": ""}
    url = url.lower().strip().rstrip('/')
    
    # arXiv : extrait l'ID numérique (ex: 2604.12345)
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})', url)
    if arxiv_match:
        return {"type": "arxiv", "id": arxiv_match.group(1)}
    
    # GitHub : extrait owner/repo
    github_match = re.search(r'github\.com/([^/]+/[^/?\s#]+)', url)
    if github_match:
        return {"type": "github", "id": github_match.group(1).lower()}
    
    # HuggingFace : extrait le dataset path
    hf_match = re.search(r'huggingface\.co/(?:datasets/)?([^/?\s#]+/[^/?\s#]+)', url)
    if hf_match:
        return {"type": "huggingface", "id": hf_match.group(1).lower()}
    
    # EURAXESS : extrait le job ID numérique
    euraxess_match = re.search(r'euraxess\.ec\.europa.eu/jobs/(\d+)', url)
    if euraxess_match:
        return {"type": "euraxess", "id": euraxess_match.group(1)}
    
    # Coursera : extrait le slug final
    coursera_match = re.search(r'coursera\.org/(?:learn|specializations|professional-certificates)/([^/?\s#]+)', url)
    if coursera_match:
        return {"type": "coursera", "id": coursera_match.group(1).lower()}
    
    # Défaut : domaine + path sans query params
    parsed = urlparse(url)
    clean_path = parsed.netloc + parsed.path.rstrip('/')
    return {"type": "generic", "id": clean_path}

def urls_match(gt_url: str, result_url: str) -> tuple[bool, str]:
    """Retourne (is_match, match_type) où match_type est 'exact', 'canonical', ou 'none'."""
    if not gt_url or not result_url:
        return False, "none"
        
    if gt_url.lower().strip().rstrip('/') == result_url.lower().strip().rstrip('/'):
        return True, "exact"
    
    gt_norm = normalize_url(gt_url)
    res_norm = normalize_url(result_url)
    
    if gt_norm["type"] != "none" and gt_norm["type"] == res_norm["type"] and gt_norm["id"] == res_norm["id"]:
        return True, "canonical"
    
    return False, "none"

async def evaluate_item(client: TavilySearchClient, category: str, gt_item: Dict, mode: str = "custom"):
    title = gt_item.get("title_en") or gt_item.get("title") or gt_item.get("dataset_name") or gt_item.get("job_title") or gt_item.get("name")
    target_url = gt_item.get("source_url") or gt_item.get("url") or gt_item.get("access_link") or gt_item.get("website")
    
    if not title or not target_url:
        return None

    # Construct query
    query = title
    
    if mode == "custom":
        search_func = getattr(client, f"search_{category}", client.search_web)
        results = await search_func(query, max_results=10)
    else:
        results = await client._search(query, config={"search_depth": "advanced", "max_results": 10})

    # Evaluation
    rank = 0
    match_type = "none"
    found = False
    
    for i, res in enumerate(results[:5]):
        res_url = str(res.get("url", ""))
        is_match, m_type = urls_match(target_url, res_url)
        if is_match:
            found = True
            rank = i + 1
            match_type = m_type
            break
            
    mrr = 1.0 / rank if found else 0.0
    p5 = 1.0 if found else 0.0
    
    return {
        "id": gt_item.get("id"),
        "category": category,
        "mode": mode,
        "found": found,
        "rank": rank,
        "match_type": match_type,
        "mrr": mrr,
        "p5": p5
    }

async def run_eval():
    client = TavilySearchClient()
    if not client.is_enabled:
        print("Tavily client is disabled. Check API keys.")
        return

    all_results = []
    semaphore = asyncio.Semaphore(5)

    async def sem_eval(cat, item, mode):
        async with semaphore:
            return await evaluate_item(client, cat, item, mode)

    tasks = []
    for category in CATEGORIES:
        file_path = os.path.join(GT_PATH, f"{category}.json")
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            gt_items = json.load(f)
            
        for item in gt_items[:10]:
            tasks.append(sem_eval(category, item, "custom"))
            tasks.append(sem_eval(category, item, "default"))

    print(f"Running {len(tasks)} search evaluations with CANONICAL matching...")
    results = []
    for i in range(0, len(tasks), 5):
        chunk = tasks[i:i+5]
        res = await asyncio.gather(*chunk)
        results.extend(res)
        print(f"  Progress: {len(results)}/{len(tasks)} items processed...")
    
    all_results = [r for r in results if r]

    # Analysis
    summary = {}
    for r in all_results:
        key = (r["category"], r["mode"])
        if key not in summary:
            summary[key] = {"p5_sum": 0, "mrr_sum": 0, "exact_count": 0, "canonical_count": 0, "count": 0}
        summary[key]["p5_sum"] += r["p5"]
        summary[key]["mrr_sum"] += r["mrr"]
        summary[key]["count"] += 1
        if r["match_type"] == "exact":
            summary[key]["exact_count"] += 1
        elif r["match_type"] == "canonical":
            summary[key]["canonical_count"] += 1

    # Generate Markdown Report
    report = "# Rapport d'Évaluation — Performance de Recherche (ÉVAL-2)\n\n"
    report += "**Mise à jour** : Intégration du matching canonique (arXiv IDs, GitHub slugs, HuggingFace datasets).\n\n"
    
    custom_results = [r for r in all_results if r["mode"] == "custom"]
    overall_p5 = sum(r["p5"] for r in custom_results) / len(custom_results) if custom_results else 0
    overall_mrr = sum(r["mrr"] for r in custom_results) / len(custom_results) if custom_results else 0
    
    report += "## Résumé Global (Mode Custom)\n"
    report += f"- **Precision@5 Moyenne** : {overall_p5:.3f} (Cible ≥ 0.70)\n"
    report += f"- **MRR Moyen** : {overall_mrr:.3f} (Cible ≥ 0.75)\n"
    report += f"- **Verdict** : {'**PASS**' if overall_p5 >= 0.70 and overall_mrr >= 0.75 else '**FAIL**'}\n\n"

    report += "## Performance par Catégorie\n"
    report += "| Catégorie | Mode | Exact Match | Canonical Match | Combined P@5 | MRR |\n"
    report += "| :--- | :--- | :---: | :---: | :---: | :---: |\n"
    
    for (cat, mode), vals in sorted(summary.items()):
        p5 = vals["p5_sum"] / vals["count"]
        mrr = vals["mrr_sum"] / vals["count"]
        exact_rate = vals["exact_count"] / vals["count"]
        canonical_rate = vals["canonical_count"] / vals["count"]
        report += f"| {cat.upper()} | {mode} | {exact_rate:.2f} | {canonical_rate:.2f} | {p5:.3f} | {mrr:.3f} |\n"

    report += "\n## Analyse Comparative\n"
    report += "Le matching canonique permet de récupérer les items où Tavily renvoie une URL valide mais structurellement différente de celle du Ground Truth (ex: arXiv `abs` vs `pdf`).\n"

    os.makedirs("evaluation/reports", exist_ok=True)
    with open("evaluation/reports/eval_2_retrieval.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nReport generated: evaluation/reports/eval_2_retrieval.md")

if __name__ == "__main__":
    asyncio.run(run_eval())
