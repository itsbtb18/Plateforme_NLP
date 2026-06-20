import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def scraping_fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def saved_html_loader(scraping_fixtures_dir):
    raw_html_dir = scraping_fixtures_dir / "raw_html"

    def _load(category: str) -> str:
        file_path = raw_html_dir / f"{category}.html"
        return file_path.read_text(encoding="utf-8")

    return _load


@pytest.fixture(scope="session")
def ground_truth(scraping_fixtures_dir):
    gt_dir = scraping_fixtures_dir / "ground_truth"
    payload = {}
    for file_path in sorted(gt_dir.glob("*_gt.json")):
        category = file_path.stem.replace("_gt", "")
        payload[category] = json.loads(file_path.read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def mocked_http_session(saved_html_loader):
    class _MockResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

    class _MockSession:
        def get(self, url, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            category = kwargs.pop("category", "news")
            return _MockResponse(saved_html_loader(category))

    return _MockSession()
