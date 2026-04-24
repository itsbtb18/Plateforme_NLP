"""HTTP-related BaseScraper mixin."""


class HttpMixin:
    def _rotate_user_agent(self):
        return super()._rotate_user_agent()

    def _notify_skip(self, name: str, url: str, reason: str):
        return super()._notify_skip(name, url, reason)

    def fetch(self, url: str, source_name: str = ""):
        return super().fetch(url, source_name=source_name)

    def safe_request(
        self, url: str, method: str = "GET", source_name: str | None = None, **kwargs
    ):
        return super().safe_request(
            url, method=method, source_name=source_name, **kwargs
        )

    def _get_health(self, source_name: str, base_url: str = ""):
        return super()._get_health(source_name, base_url)

    def check_source(self, source_name: str, base_url: str = "") -> bool:
        return super().check_source(source_name, base_url)

    def report_success(
        self, source_name: str, base_url: str = "", response_time: float | None = None
    ):
        return super().report_success(source_name, base_url, response_time)

    def report_failure(self, source_name: str, base_url: str = "", error: str = ""):
        return super().report_failure(source_name, base_url, error)
