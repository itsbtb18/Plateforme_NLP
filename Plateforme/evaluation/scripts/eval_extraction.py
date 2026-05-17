import os
import json
import glob
import random
import difflib
import time
import re
import sys

import django
sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from sentence_transformers import SentenceTransformer, util
from scraping.direct_scrape import _fetch_page_text, _extract_single_candidate
from scraping.extractors.core.llm_validation import GroqLLMClient, build_custom_extraction_prompt

# Semantic model
_model = None
def get_model():
    global _model
    if _model is None:
        print("Loading SentenceTransformer model...")
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model

def semantic_similarity(text_a: str, text_b: str) -> float:
    if not text_a or not text_b:
        return 0.0
    model = get_model()
    emb_a = model.encode(text_a, convert_to_tensor=True)
    emb_b = model.encode(text_b, convert_to_tensor=True)
    return float(util.cos_sim(emb_a, emb_b))

def text_f1(pred, truth):
    if not truth and not pred: return 1.0
    if not truth or not pred: return 0.0
    return difflib.SequenceMatcher(None, str(pred).lower(), str(truth).lower()).ratio()

def exact_match(pred, truth):
    if not truth and not pred: return 1.0
    if not truth or not pred: return 0.0
    return 1.0 if str(pred).lower().strip() == str(truth).lower().strip() else 0.0

def date_match_flexible(pred, truth):
    if not truth and not pred: return 1.0
    if not truth or not pred: return 0.0
    
    p = str(pred).strip()
    t = str(truth).strip()
    
    if p == t: return 1.0
    
    if len(p) >= 7 and len(t) >= 7:
        if p[:7] == t[:7]: return 1.0
        
    if len(p) >= 4 and len(t) >= 4:
        if p[:4] == t[:4]: return 1.0
        
    return 0.0

MANDATORY_FIELDS = ["title_en", "description_en", "source_url", "access_link"]
OPTIONAL_ENRICHMENT_FIELDS = [
    "organizer", "location", "city", "country",
    "github_link", "license", "paper_link",
    "institution", "salary", "duration"
]

def compute_hallucination_rate_initial(gt_item: dict, extracted: dict) -> float:
    hal_count = 0
    total_fields_checked = 0
    for k, v in extracted.items():
        if k in ["extraction_confidence", "relevance_score", "keywords", "tags", "id", "_cat"]: continue
        if v and str(v).lower() not in ["none", "null", "n/a", ""]:
            total_fields_checked += 1
            truth_v = gt_item.get(k)
            if not truth_v or str(truth_v).lower() in ["none", "null", "n/a", ""]:
                hal_count += 1
    return hal_count / max(total_fields_checked, 1)

def compute_hallucination_rate_corrected(gt_item: dict, extracted: dict) -> float:
    errors = 0
    total = 0
    for field in MANDATORY_FIELDS + OPTIONAL_ENRICHMENT_FIELDS:
        if field in gt_item and gt_item[field]:
            total += 1
            gt_val = str(gt_item[field]).lower().strip()
            ext_val = str(extracted.get(field, "")).lower().strip()
            
            if ext_val and ext_val != gt_val:
                # Use semantic for complex text fields
                if any(kw in field for kw in ["title", "description", "content"]):
                    if semantic_similarity(gt_val, ext_val) < 0.5:
                        errors += 1
                else:
                    if gt_val != ext_val:
                        errors += 1
    return errors / total if total > 0 else 0.0

def eval_extraction():
    all_items = []
    for file_path in glob.glob("evaluation/ground_truth/*.json"):
        if "urls_to_test" in file_path: continue
        cat = os.path.basename(file_path).replace(".json", "")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        random.seed(42)
        random.shuffle(data)
        
        num_items = 1 if os.environ.get("EVAL_SHORT") == "1" else 10
        sample = data[:num_items]
            
        for it in sample:
            it["_cat"] = cat
            all_items.append(it)

    results = []
    errors_log = []
    
    for idx, item in enumerate(all_items):
        cat = item["_cat"]
        url = item.get("url") or item.get("source_url") or item.get("download_url") or item.get("access_link")
        print(f"[{idx+1}/{len(all_items)}] Cat: {cat} | URL: {url}")
        
        if not url:
            print("  -> ERREUR: No URL in ground truth")
            results.append({"cat": cat, "error": "No URL"})
            continue
            
        try:
            from django.conf import settings as django_settings
            is_mock = getattr(django_settings, "SCRAPING_MOCK_LLM", False)
            
            candidate = None
            if is_mock:
                candidate = _extract_single_candidate(cat, url, "", "")
            else:
                page_text, page_title = _fetch_page_text(url)
                if not page_text or len(page_text) < 50:
                    raise ValueError("No page text or text too short")
                page_text = page_text[:12000]
                candidate = _extract_single_candidate(cat, url, page_title, page_text)
            
            if not candidate:
                raise ValueError("Extraction returned None")
                
            # Metrics
            truth_title = item.get("title_en") or item.get("dataset_name") or item.get("job_title") or item.get("title")
            pred_title = candidate.get("title_en") or candidate.get("dataset_name") or candidate.get("job_title") or candidate.get("title")
            
            t_f1_lex = text_f1(pred_title, truth_title)
            t_f1_sem = semantic_similarity(pred_title, truth_title)
            
            truth_desc = item.get("description_en") or item.get("description") or item.get("content_en") or item.get("content")
            pred_desc = candidate.get("description_en") or candidate.get("description") or candidate.get("content_en") or candidate.get("content")
            d_f1_sem = semantic_similarity(pred_desc, truth_desc)
            
            # Date Fields
            truth_date = item.get("start_date") or item.get("published_date") or item.get("date") or item.get("deadline") or ""
            pred_date = candidate.get("start_date") or candidate.get("published_date") or candidate.get("date") or candidate.get("deadline") or ""
            
            date_em_strict = exact_match(pred_date, truth_date) if truth_date else None
            date_em_flex = date_match_flexible(pred_date, truth_date) if truth_date else None
            
            truth_url = item.get("url") or item.get("source_url") or item.get("access_link") or ""
            pred_url = candidate.get("url") or candidate.get("source_url") or candidate.get("access_link") or ""
            url_em = exact_match(pred_url, truth_url) if truth_url else None
            
            hal_rate_init = compute_hallucination_rate_initial(item, candidate)
            hal_rate_corr = compute_hallucination_rate_corrected(item, candidate)
            
            results.append({
                "cat": cat,
                "error": None,
                "t_f1_lex": t_f1_lex,
                "t_f1_sem": t_f1_sem,
                "d_f1_sem": d_f1_sem,
                "date_em_strict": date_em_strict,
                "date_em_flex": date_em_flex,
                "url_em": url_em,
                "hal_rate_init": hal_rate_init,
                "hal_rate_corr": hal_rate_corr
            })
            
            print(f"  -> SUCCESS (Titre Sem: {t_f1_sem:.2f}, Hal Corr: {hal_rate_corr:.2f})")
            
        except Exception as e:
            err = str(e)
            print(f"  -> ERREUR: {err}")
            errors_log.append(err)
            results.append({"cat": cat, "error": err})
            
        if getattr(django_settings, "SCRAPING_MOCK_LLM", False):
            time.sleep(0.01)

    from collections import defaultdict
    summary = defaultdict(lambda: {"t_lex": [], "t_sem": [], "d_sem": [], "date_strict": [], "date_flex": [], "url_em": [], "hal_init": [], "hal_corr": [], "errs": 0, "total": 0})
    summary["GLOBAL"] = {"t_lex": [], "t_sem": [], "d_sem": [], "date_strict": [], "date_flex": [], "url_em": [], "hal_init": [], "hal_corr": [], "errs": 0, "total": 0}
    
    for r in results:
        cat = r["cat"]
        summary[cat]["total"] += 1
        summary["GLOBAL"]["total"] += 1
        if r["error"]:
            summary[cat]["errs"] += 1
            summary["GLOBAL"]["errs"] += 1
        else:
            summary[cat]["t_lex"].append(r["t_f1_lex"])
            summary[cat]["t_sem"].append(r["t_f1_sem"])
            summary[cat]["d_sem"].append(r["d_f1_sem"])
            summary[cat]["hal_init"].append(r["hal_rate_init"])
            summary[cat]["hal_corr"].append(r["hal_rate_corr"])
            if r["date_em_strict"] is not None: summary[cat]["date_strict"].append(r["date_em_strict"])
            if r["date_em_flex"] is not None: summary[cat]["date_flex"].append(r["date_em_flex"])
            if r["url_em"] is not None: summary[cat]["url_em"].append(r["url_em"])
            
            summary["GLOBAL"]["t_lex"].append(r["t_f1_lex"])
            summary["GLOBAL"]["t_sem"].append(r["t_f1_sem"])
            summary["GLOBAL"]["d_sem"].append(r["d_f1_sem"])
            summary["GLOBAL"]["hal_init"].append(r["hal_rate_init"])
            summary["GLOBAL"]["hal_corr"].append(r["hal_rate_corr"])
            if r["date_em_strict"] is not None: summary["GLOBAL"]["date_strict"].append(r["date_em_strict"])
            if r["date_em_flex"] is not None: summary["GLOBAL"]["date_flex"].append(r["date_em_flex"])
            if r["url_em"] is not None: summary["GLOBAL"]["url_em"].append(r["url_em"])
            
    print("\n" + "="*120)
    print("RÉSULTATS DE L'EXTRACTION (HAL. CORRIGÉE)")
    print("="*120)
    print(f"{'Catégorie':<12} | {'Tit Sem':<7} | {'Desc Sem':<8} | {'Date Flx':<8} | {'URL EM':<6} | {'Hal Init':<8} | {'Hal Corr':<8} | {'Errs'}")
    print("-" * 120)
    
    def avg(l): return sum(l)/len(l) if l else 0.0
    
    for cat in sorted(summary.keys()):
        if cat == "GLOBAL": continue
        s = summary[cat]
        print(f"{cat:<12} | {avg(s['t_sem']):<7.2f} | {avg(s['d_sem']):<8.2f} | {avg(s['date_flex']):<8.2f} | {avg(s['url_em']):<6.2f} | {avg(s['hal_init'])*100:<8.1f} | {avg(s['hal_corr'])*100:<8.1f} | {s['errs']}/{s['total']}")
        
    g = summary["GLOBAL"]
    print("-" * 120)
    print(f"{'GLOBAL':<12} | {avg(g['t_sem']):<7.2f} | {avg(g['d_sem']):<8.2f} | {avg(g['date_flex']):<8.2f} | {avg(g['url_em']):<6.2f} | {avg(g['hal_init'])*100:<8.1f} | {avg(g['hal_corr'])*100:<8.1f} | {g['errs']}/{g['total']}")

if __name__ == "__main__":
    eval_extraction()
