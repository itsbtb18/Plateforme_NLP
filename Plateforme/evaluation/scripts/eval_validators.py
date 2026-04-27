import json
import os
import time

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from scraping.validators.network_validator import NetworkValidator
from scraping.validators.content_validator import ContentValidator

def evaluate_validators():
    print("=" * 60)
    print("  Évaluation des Validateurs (Network & Content)")
    print("=" * 60)
    
    with open("evaluation/ground_truth/urls_to_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Loaded {len(data)} URLs for testing.")
    
    results = {
        "network": {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
        "content": {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
        "combined": {"TP": 0, "TN": 0, "FP": 0, "FN": 0},
    }
    
    # Simulate LLM call cost (1 call per valid page sent to LLM)
    llm_calls_saved = 0
    total_expected_invalid = 0
    
    for i, item in enumerate(data):
        url = item["url"]
        expected_valid = item["expected_valid"]
        if not expected_valid:
            total_expected_invalid += 1
            
        print(f"\n[{i+1}/{len(data)}] URL: {url} (Expected: {'PASS' if expected_valid else 'REJECT'})")
        
        # 1. Network Validation
        net_val = NetworkValidator(url=url)
        try:
            net_res = net_val.run()
            net_pass = net_res.get("overall") in ["GREEN", "YELLOW"]
            net_reason = net_res.get("blocking_reason") or "OK"
        except Exception as e:
            net_pass = False
            net_reason = str(e)
            
        if expected_valid and net_pass: results["network"]["TP"] += 1
        elif not expected_valid and not net_pass: results["network"]["TN"] += 1
        elif not expected_valid and net_pass: results["network"]["FP"] += 1
        elif expected_valid and not net_pass: results["network"]["FN"] += 1
            
        print(f"  Network: {'PASS' if net_pass else 'REJECT'} ({net_reason})")

        # 2. Content Validation
        # If network fails in production, content validation isn't run.
        # But for evaluation, we'll run it separately to measure its individual performance.
        # Note: ContentValidator actually fetches the text itself via urllib.
        content_pass = False
        content_verdict = "N/A"
        if url.startswith("http"): # Skip DNS errors that crash immediately
            try:
                # We use a generic category 'events' to test NLP keywords
                content_val = ContentValidator(url=url, category="events")
                content_res = content_val.run()
                content_verdict = content_res.get("verdict")
                content_pass = content_verdict in ["RELEVANT", "UNCERTAIN"]
            except Exception as e:
                content_pass = False
                content_verdict = f"ERROR: {e}"

        if expected_valid and content_pass: results["content"]["TP"] += 1
        elif not expected_valid and not content_pass: results["content"]["TN"] += 1
        elif not expected_valid and content_pass: results["content"]["FP"] += 1
        elif expected_valid and not content_pass: results["content"]["FN"] += 1

        print(f"  Content: {'PASS' if content_pass else 'REJECT'} ({content_verdict})")

        # 3. Combined Cascade (Network -> Content)
        combined_pass = net_pass and content_pass
        if expected_valid and combined_pass: results["combined"]["TP"] += 1
        elif not expected_valid and not combined_pass: 
            results["combined"]["TN"] += 1
            llm_calls_saved += 1
        elif not expected_valid and combined_pass: results["combined"]["FP"] += 1
        elif expected_valid and not combined_pass: results["combined"]["FN"] += 1
            
        print(f"  Combined: {'PASS' if combined_pass else 'REJECT'}")
        
    # --- Final Output ---
    print("\n" + "=" * 60)
    print("  Résultats Finaux")
    print("=" * 60)
    
    def print_metrics(name, d):
        total = d['TP'] + d['TN'] + d['FP'] + d['FN']
        true_reject = d['TN']
        false_reject = d['FN']
        true_pass = d['TP']
        false_pass = d['FP']
        
        fr_rate = (false_reject / (true_pass + false_reject)) * 100 if (true_pass + false_reject) > 0 else 0
        correct_rate = ((true_reject + true_pass) / total) * 100 if total > 0 else 0
        
        print(f"{name:<10} | {true_pass:<9} | {false_pass:<10} | {true_reject:<11} | {false_reject:<12} | {fr_rate:>5.1f}% | {correct_rate:>6.1f}%")

    print(f"{'Validator':<10} | {'True Pass':<9} | {'False Pass':<10} | {'True Reject':<11} | {'False Reject':<12} | {'FR %':>6} | {'Correct'}")
    print("-" * 80)
    print_metrics("Network", results["network"])
    print_metrics("Content", results["content"])
    print_metrics("Combined", results["combined"])
    
    print("\nImpact Économique:")
    print(f"- LLM Calls Saved: {llm_calls_saved} / {total_expected_invalid} ({llm_calls_saved/max(1, total_expected_invalid)*100:.1f}%)")

if __name__ == "__main__":
    evaluate_validators()
