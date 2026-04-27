import requests
from django.core.management.base import BaseCommand
from scraping.api_key_manager import api_key_manager

class Command(BaseCommand):
    help = "Test all registered API keys and display their status."

    def handle(self, *args, **options):
        for provider, keys in api_key_manager.providers.items():
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- Checking {provider.upper()} ({len(keys)} keys) ---"))
            
            for i, key in enumerate(keys):
                status = self._check_key(provider, key)
                color_func = self.style.SUCCESS if status == "active" else self.style.ERROR
                self.stdout.write(f"Key {i:02d} [...{key[-6:]}]: {color_func(status)}")

    def _check_key(self, provider, key) -> str:
        try:
            if provider == "groq":
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1
                    },
                    timeout=5
                )
            elif provider == "gemini":
                # Using a simple models.list or small completion
                resp = requests.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
                    timeout=5
                )
            elif provider == "tavily":
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={"api_key": key, "query": "test", "max_results": 1},
                    timeout=5
                )
            else:
                return "unknown_provider"

            if resp.status_code == 200:
                return "active"
            elif resp.status_code == 429:
                return "rate_limited"
            elif resp.status_code in [401, 403]:
                return "invalid"
            elif resp.status_code == 400 and "quota" in resp.text.lower():
                return "quota_exceeded"
            else:
                return f"error_{resp.status_code}"
                
        except Exception as e:
            return f"unreachable ({str(e)[:20]})"
