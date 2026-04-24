__all__ = ["EnrichmentEngine"]


def __getattr__(name):
    if name == "EnrichmentEngine":
        from scraping.enrichment_engine import EnrichmentEngine

        return EnrichmentEngine
    raise AttributeError(name)
