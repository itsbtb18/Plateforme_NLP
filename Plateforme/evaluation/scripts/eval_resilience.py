import os
import django
import sys
import time
from datetime import timedelta
import concurrent.futures

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Plateforme.settings")
django.setup()

from django.utils import timezone
from scraping.models import ScrapingSourceHealth

def run_tests():
    print("=" * 60)
    print("  Rapport d'Évaluation — Résilience (ÉVAL-6)")
    print("=" * 60)
    
    results = []
    
    # Clean up test data
    ScrapingSourceHealth.objects.filter(source_name__startswith="TestResilience_").delete()

    # --- Test 1 & 2: Transitions & Decay ---
    print("\n[RES-01 & RES-02 à RES-06] Transitions et Decay")
    health = ScrapingSourceHealth.objects.create(
        category="events",
        source_name="TestResilience_A",
        health_score=100.0,
        circuit_state="closed"
    )
    
    decays_expected = [95.0, 85.0, 65.0, 25.0, 0.0]
    decay_results = []
    
    # 5 failures
    for i in range(5):
        health.record_failure("test failure")
        health.refresh_from_db()
        decay_results.append(health.health_score)
    
    decay_pass = (decay_results == decays_expected)
    if decay_pass:
        print(f"✓ Decay conforme: {decay_results}")
        results.append(("RES-02 à RES-06", "Decay score exact (95, 85, 65, 25, 0)", "PASS"))
    else:
        print(f"✗ Decay attendu {decays_expected}, obtenu {decay_results}")
        results.append(("RES-02 à RES-06", "Decay score exact", "FAIL"))

    # State should be open now because health_score dropped < threshold or 5 failures
    open_pass = (health.circuit_state == "open")
    if open_pass:
        print("✓ Circuit OPEN après pannes répétées")
    else:
        print("✗ Circuit n'est pas OPEN")
    
    # Move in time to simulate cooldown
    health.circuit_opened_at = timezone.now() - timedelta(seconds=health.circuit_cooldown_seconds + 1)
    health.save()
    
    # The allow_request logic in ScrapingSourceHealth
    # Let's check allow_request
    allow = health.is_available()
    half_open_pass = (health.circuit_state == "half_open" and allow == True)
    if half_open_pass:
        print("✓ Circuit HALF_OPEN après cooldown")
    else:
        print(f"✗ Circuit n'est pas HALF_OPEN (allow={allow}, state={health.circuit_state})")
        
    health.record_success()
    health.refresh_from_db()
    closed_pass = (health.circuit_state == "closed")
    if closed_pass:
        print("✓ Circuit CLOSED après succès")
    else:
        print("✗ Circuit n'est pas CLOSED")

    if open_pass and half_open_pass and closed_pass:
        results.append(("RES-01", "Transitions d'état (CLOSED→OPEN→HALF_OPEN→CLOSED)", "PASS"))
    else:
        results.append(("RES-01", "Transitions d'état (CLOSED→OPEN→HALF_OPEN→CLOSED)", "FAIL"))

    # --- Test 3: Isolation ---
    print("\n[RES-07] Isolation entre sources")
    health_b = ScrapingSourceHealth.objects.create(
        category="events",
        source_name="TestResilience_B",
        health_score=100.0,
        circuit_state="closed"
    )
    
    health.circuit_state = "open"
    health.save()
    
    health_b.refresh_from_db()
    isolation_pass = (health_b.circuit_state == "closed")
    if isolation_pass:
        print("✓ Échec Source A n'impacte pas Source B")
        results.append(("RES-07", "Isolation", "PASS"))
    else:
        print("✗ Isolation échouée")
        results.append(("RES-07", "Isolation", "FAIL"))

    # --- Test 4: Concurrence ---
    print("\n[RES-08] Concurrence (3 workers)")
    health.circuit_state = "open"
    health.circuit_opened_at = timezone.now() - timedelta(seconds=health.circuit_cooldown_seconds + 1)
    health.save()
    
    def try_claim(source_id):
        # Must reload to ensure clean state
        django.db.close_old_connections()
        h = ScrapingSourceHealth.objects.get(id=source_id)
        return h.is_available()
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(try_claim, health.id) for _ in range(3)]
        claims = [f.result() for f in futures]
    
    trues = claims.count(True)
    if trues == 1:
        print(f"✓ 1 seul worker a pu claim la probe (True: {trues})")
        results.append(("RES-08", "Concurrence (1 seul worker claim)", "PASS"))
    else:
        print(f"✗ Concurrence échouée, claims: {claims}")
        results.append(("RES-08", "Concurrence (1 seul worker claim)", "FAIL"))

    # --- Print Summary ---
    print("\n" + "=" * 60)
    print("  Récapitulatif")
    print("=" * 60)
    print(f"{'ID':<10} | {'Test':<40} | {'Verdict'}")
    print("-" * 65)
    for id, test, verdict in results:
        print(f"{id:<10} | {test:<40} | {verdict}")

if __name__ == "__main__":
    run_tests()
