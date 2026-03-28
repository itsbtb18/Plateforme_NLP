"""Media-related BaseScraper mixin."""


class MediaMixin:
    def _is_download_enabled(self) -> bool:
        return super()._is_download_enabled()

    def _max_concurrent_downloads(self) -> int:
        return super()._max_concurrent_downloads()

    @staticmethod
    def _coerce_url_list(value) -> list[str]:
        return [] if value is None else BaseMediaCompat._coerce_url_list_fallback(value)

    @staticmethod
    def _is_probable_pdf_url(url: str) -> bool:
        return BaseMediaCompat._is_probable_pdf_url_fallback(url)

    def _collect_page_media_urls(self, page_url: str, category: str) -> dict:
        return super()._collect_page_media_urls(page_url, category)

    def _resolve_media_candidates(self, item_data: dict, category: str) -> dict:
        return super()._resolve_media_candidates(item_data, category)

    def _download_media(self, item_data: dict, category: str) -> dict:
        return super()._download_media(item_data, category)


class BaseMediaCompat:
    @staticmethod
    def _coerce_url_list_fallback(value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            urls = [str(v).strip() for v in value if str(v).strip()]
        else:
            text = str(value).strip()
            urls = [text] if text else []
        deduped = []
        seen = set()
        for url in urls:
            if not url:
                continue
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    @staticmethod
    def _is_probable_pdf_url_fallback(url: str) -> bool:
        from scraping.constants import PDF_URL_PATTERNS
        lower = (url or "").lower()
        return any(p in lower for p in PDF_URL_PATTERNS)
