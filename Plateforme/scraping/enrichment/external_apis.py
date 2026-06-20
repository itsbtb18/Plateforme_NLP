"""External API enrichment mixin wrappers."""


class ExternalAPIsMixin:
    def _enrich_tool_github(self, item):
        return super()._enrich_tool_github(item)

    def _enrich_tool_paper_link(self, item):
        return super()._enrich_tool_paper_link(item)

    def _enrich_arxiv_metadata(self, item):
        return super()._enrich_arxiv_metadata(item)

    def _enrich_news_citations(self, item):
        return super()._enrich_news_citations(item)

    def _enrich_institution_openalex(self, item):
        return super()._enrich_institution_openalex(item)

    def _enrich_institution_contact(self, item):
        return super()._enrich_institution_contact(item)

    def _fetch_json(self, url, headers=None, params=None):
        return super()._fetch_json(url, headers=headers, params=params)

    def _fetch_text(self, url):
        return super()._fetch_text(url)

    def _parse_github_repo(self, github_url):
        return super()._parse_github_repo(github_url)
