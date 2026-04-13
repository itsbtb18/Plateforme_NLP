import scraping.extractors.core.llm_validation as llm_validation


def _configure_llm_settings(settings):
    settings.GROQ_SCRAPING_API_KEY = "groq-key"
    settings.GROQ_SCRAPING_MODEL = "llama-3.3-70b-versatile"
    settings.GROQ_SCRAPING_TIMEOUT = 30
    settings.GROQ_SCRAPING_MAX_RETRIES = 2
    settings.GEMINI_SCRAPING_API_KEY = "gemini-key"
    settings.GEMINI_SCRAPING_MODEL = "gemini-3.5-preview"
    settings.GEMINI_SCRAPING_TIMEOUT = 30
    settings.GEMINI_SCRAPING_MAX_RETRIES = 2
    settings.GEMINI_SCRAPING_MAX_RPM = 10


def test_routing_uses_primary_provider_when_healthy(settings, monkeypatch):
    _configure_llm_settings(settings)
    settings.SCRAPING_LLM_PRIMARY_PROVIDER = "gemini"
    settings.SCRAPING_LLM_FALLBACK_PROVIDER = "groq"
    settings.SCRAPING_LLM_MODE = "primary_with_fallback"

    client = llm_validation.GroqLLMClient()

    def _gemini_ok(self, system, user):
        self.last_status_code = 200
        self.last_provider_used = "gemini"
        return '{"ok": true}'

    def _groq_should_not_run(self, system, user):
        raise AssertionError("Groq fallback should not run when Gemini succeeds")

    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_gemini", _gemini_ok)
    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_groq", _groq_should_not_run)

    response = client._chat("system", "user")

    assert response == '{"ok": true}'
    assert client.last_provider_used == "gemini"


def test_routing_falls_back_to_groq_on_retryable_primary_failure(settings, monkeypatch):
    _configure_llm_settings(settings)
    settings.SCRAPING_LLM_PRIMARY_PROVIDER = "gemini"
    settings.SCRAPING_LLM_FALLBACK_PROVIDER = "groq"
    settings.SCRAPING_LLM_MODE = "primary_with_fallback"

    client = llm_validation.GroqLLMClient()

    def _gemini_rate_limited(self, system, user):
        self.last_status_code = 429
        self.last_error_message = "rate_limited"
        return None

    def _groq_ok(self, system, user):
        self.last_status_code = 200
        self.last_provider_used = "groq"
        return '{"fallback": true}'

    monkeypatch.setattr(
        llm_validation.GroqLLMClient,
        "_chat_with_gemini",
        _gemini_rate_limited,
    )
    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_groq", _groq_ok)

    response = client._chat("system", "user")

    assert response == '{"fallback": true}'
    assert client.last_provider_used == "groq"


def test_routing_respects_primary_only_mode(settings, monkeypatch):
    _configure_llm_settings(settings)
    settings.SCRAPING_LLM_PRIMARY_PROVIDER = "gemini"
    settings.SCRAPING_LLM_FALLBACK_PROVIDER = "groq"
    settings.SCRAPING_LLM_MODE = "primary_only"

    client = llm_validation.GroqLLMClient()

    def _gemini_failed(self, system, user):
        self.last_status_code = 429
        return None

    def _groq_should_not_run(self, system, user):
        raise AssertionError("Groq should not run in primary_only mode")

    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_gemini", _gemini_failed)
    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_groq", _groq_should_not_run)

    response = client._chat("system", "user")

    assert response is None


def test_routing_supports_groq_only_mode(settings, monkeypatch):
    _configure_llm_settings(settings)
    settings.SCRAPING_LLM_PRIMARY_PROVIDER = "gemini"
    settings.SCRAPING_LLM_FALLBACK_PROVIDER = "groq"
    settings.SCRAPING_LLM_MODE = "fallback_only"

    client = llm_validation.GroqLLMClient()

    def _groq_ok(self, system, user):
        self.last_status_code = 200
        self.last_provider_used = "groq"
        return '{"groq_only": true}'

    monkeypatch.setattr(llm_validation.GroqLLMClient, "_chat_with_groq", _groq_ok)

    response = client._chat("system", "user")

    assert response == '{"groq_only": true}'
    assert client.last_provider_used == "groq"
