"""Category enrichment mixin wrappers."""


class CategoryEnrichmentMixin:
    def _run_category_enrichment(self, item, category):
        return super()._run_category_enrichment(item, category)

    def _enrich_events(self, item):
        return super()._enrich_events(item)

    def _enrich_tools(self, item):
        return super()._enrich_tools(item)

    def _enrich_news(self, item):
        return super()._enrich_news(item)

    def _enrich_courses(self, item):
        return super()._enrich_courses(item)

    def _enrich_institutions(self, item):
        return super()._enrich_institutions(item)
