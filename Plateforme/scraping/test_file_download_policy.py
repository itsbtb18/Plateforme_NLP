# pyright: reportMissingImports=false

import socket
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

from QA.models import Post
from scraping.file_downloader import (
    attach_file_to_model,
    download_file,
    try_download_document,
)


class _FakeResponse:
    def __init__(self, content_type, chunks, status=200):
        self.headers = {"Content-Type": content_type}
        self._chunks = chunks
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def iter_content(self, chunk_size=8192):
        for chunk in self._chunks:
            yield chunk


@pytest.fixture
def _allow_external_dns(monkeypatch):
    def _fake_getaddrinfo(hostname, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(  # type: ignore[call-arg]
        email="download-policy@example.com",
        password="x",
        full_name_en="Policy User",
        full_name_ar="مستخدم",
    )


@pytest.mark.django_db
def test_image_policy_deterministic_filename_and_path(
    monkeypatch, tmp_path, _allow_external_dns
):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "scraping.file_downloader.requests.get",
        lambda *a, **k: _FakeResponse("image/png", [b"abc"]),
    )

    content, filename, mime = download_file(
        "https://example.com/logo.png",
        "tools",
        item_name="Arabic BERT Model",
        file_type="image",
    )

    assert content is not None
    assert mime == "image/png"
    assert filename is not None
    assert filename.startswith("scraping/tools/images/arabic-bert-model_")
    assert filename.endswith(".png")


@pytest.mark.django_db
def test_pdf_policy_skips_existing_url_hash_without_request(
    monkeypatch, tmp_path, _allow_external_dns
):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    # Existing file with same url hash suffix should prevent network fetch.
    existing_dir = Path(tmp_path) / "scraping" / "news" / "pdfs"
    existing_dir.mkdir(parents=True, exist_ok=True)
    existing_file = existing_dir / "paper_4d3f0f6a.pdf"
    existing_file.write_bytes(b"existing")

    # Force known hash by monkeypatching helper.
    monkeypatch.setattr("scraping.file_downloader._url_hash", lambda _u: "4d3f0f6a")

    calls = {"count": 0}

    def _never_called(*args, **kwargs):
        calls["count"] += 1
        return _FakeResponse("application/pdf", [b"pdf"])

    monkeypatch.setattr("scraping.file_downloader.requests.get", _never_called)

    content, filename = try_download_document(
        ["https://example.com/paper.pdf"],
        "news",
        item_name="Paper",
    )

    assert content is None
    assert filename == "scraping/news/pdfs/paper_4d3f0f6a.pdf"
    assert calls["count"] == 0


@pytest.mark.django_db
def test_image_policy_rejects_disallowed_mime(
    monkeypatch, tmp_path, _allow_external_dns
):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "scraping.file_downloader.requests.get",
        lambda *a, **k: _FakeResponse("image/svg+xml", [b"svg"]),
    )

    content, filename, mime = download_file(
        "https://example.com/logo.svg",
        "tools",
        item_name="Tool",
        file_type="image",
    )

    assert content is None
    assert filename is None
    assert mime is None


@pytest.mark.django_db
def test_pdf_policy_rejects_size_over_50mb(monkeypatch, tmp_path, _allow_external_dns):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    too_big = b"a" * (50 * 1024 * 1024 + 1)
    monkeypatch.setattr(
        "scraping.file_downloader.requests.get",
        lambda *a, **k: _FakeResponse("application/pdf", [too_big]),
    )

    content, filename, mime = download_file(
        "https://example.com/doc.pdf",
        "news",
        item_name="Doc",
        file_type="document",
    )

    assert content is None
    assert filename is None
    assert mime is None


@pytest.mark.django_db
def test_attach_file_reuses_existing_path_without_content(user):
    post = Post.objects.create(
        author=user,
        title="Policy Post",
        title_en="Policy Post",
        content="content",
        content_en="content",
        slug="policy-post",
    )

    ok = attach_file_to_model(
        post, "file", None, "scraping/news/pdfs/policy_1234abcd.pdf"
    )

    assert ok is True
    post.refresh_from_db()
    assert post.file.name == "scraping/news/pdfs/policy_1234abcd.pdf"
