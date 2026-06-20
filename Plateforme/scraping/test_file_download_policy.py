# pyright: reportMissingImports=false

import json
import socket
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from feed.models import Post

from scraping.file_downloader import (
    DownloadResult,
    SSRFViolationError,
    attach_file_to_model,
    download_file,
    try_download_document,
)

# ── Fake HTTP helpers ───────────────────────────────────────────────


def _fake_head_result(content_type="application/pdf", content_length=100):
    """Minimal stand-in for downloader HEAD preflight helper."""
    return content_type, content_length


def _fake_get_result(content_type, chunks):
    """Minimal stand-in for downloader GET helper."""
    payload = b"".join(chunks)
    return content_type, payload, len(payload)


@pytest.fixture
def _allow_external_dns(monkeypatch):
    def _fake_getaddrinfo(hostname, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)


@pytest.fixture
def user(db):
    user_model = get_user_model()
    return user_model.objects.create_user(  # type: ignore[call-arg]
        email="download-policy@example.com",
        password="x",
        full_name_en="Policy User",
        full_name_ar="مستخدم",
    )


# ====================================================================
# Existing tests — updated for DownloadResult return signature
# ====================================================================


@pytest.mark.django_db
def test_image_policy_deterministic_filename_and_path(
    monkeypatch, tmp_path, _allow_external_dns
):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("image/png", 3),
    )
    monkeypatch.setattr(
        "scraping.file_downloader._download_via_get",
        lambda *a, **k: _fake_get_result("image/png", [b"abc"]),
    )

    content, filename, result = download_file(
        "https://example.com/logo.png",
        "tools",
        item_name="Arabic BERT Model",
        file_type="image",
    )

    assert content is not None
    assert result == DownloadResult.SUCCESS
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

    calls = {"head": 0, "get": 0}

    def _head_never_called(*args, **kwargs):
        calls["head"] += 1
        return _fake_head_result()

    def _get_never_called(*args, **kwargs):
        calls["get"] += 1
        return _fake_get_result("application/pdf", [b"pdf"])

    monkeypatch.setattr("scraping.file_downloader._head_preflight", _head_never_called)
    monkeypatch.setattr("scraping.file_downloader._download_via_get", _get_never_called)

    content, filename = try_download_document(
        ["https://example.com/paper.pdf"],
        "news",
        item_name="Paper",
    )

    assert content is None
    assert filename == "scraping/news/pdfs/paper_4d3f0f6a.pdf"
    assert calls["head"] == 0
    assert calls["get"] == 0


@pytest.mark.django_db
def test_image_policy_rejects_disallowed_mime(
    monkeypatch, tmp_path, _allow_external_dns
):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("image/svg+xml", 10),
    )
    monkeypatch.setattr(
        "scraping.file_downloader._download_via_get",
        lambda *a, **k: _fake_get_result("image/svg+xml", [b"svg"]),
    )

    content, filename, result = download_file(
        "https://example.com/logo.svg",
        "tools",
        item_name="Tool",
        file_type="image",
    )

    assert content is None
    assert filename is None
    assert result == DownloadResult.FAIL_MIME


@pytest.mark.django_db
def test_pdf_policy_rejects_size_over_50mb(monkeypatch, tmp_path, _allow_external_dns):
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    huge_size = 50 * 1024 * 1024 + 1
    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("application/pdf", huge_size),
    )

    too_big = b"a" * huge_size
    monkeypatch.setattr(
        "scraping.file_downloader._download_via_get",
        lambda *a, **k: _fake_get_result("application/pdf", [too_big]),
    )

    content, filename, result = download_file(
        "https://example.com/doc.pdf",
        "news",
        item_name="Doc",
        file_type="document",
    )

    assert content is None
    assert filename is None
    assert result == DownloadResult.FAIL_SIZE


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


# ====================================================================
# NEW TESTS — HEAD preflight, sidecar .meta.json, result codes
# ====================================================================


@pytest.mark.django_db
def test_head_wrong_mime_blocks_get(monkeypatch, tmp_path, _allow_external_dns):
    """HEAD returns wrong MIME → assert GET never called."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("text/html", 500),
    )

    get_calls = {"count": 0}

    def _counting_get(*args, **kwargs):
        get_calls["count"] += 1
        return _fake_get_result("text/html", [b"<html></html>"])

    monkeypatch.setattr("scraping.file_downloader._download_via_get", _counting_get)

    content, filename, result = download_file(
        "https://example.com/page.html",
        "tools",
        item_name="Tool",
        file_type="document",
    )

    assert content is None
    assert filename is None
    assert result == DownloadResult.FAIL_MIME
    assert get_calls["count"] == 0, "GET must never be called when HEAD rejects MIME"


@pytest.mark.django_db
def test_head_timeout_returns_fail_head(monkeypatch, tmp_path, _allow_external_dns):
    """HEAD timeout → FAIL_HEAD returned, GET never called."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    def _head_timeout(*args, **kwargs):
        raise TimeoutError("HEAD timed out")

    monkeypatch.setattr("scraping.file_downloader._head_preflight", _head_timeout)

    get_calls = {"count": 0}

    def _counting_get(*args, **kwargs):
        get_calls["count"] += 1
        return _fake_get_result("application/pdf", [b"pdf"])

    monkeypatch.setattr("scraping.file_downloader._download_via_get", _counting_get)

    content, filename, result = download_file(
        "https://example.com/doc.pdf",
        "news",
        item_name="Doc",
        file_type="document",
    )

    assert content is None
    assert filename is None
    assert result == DownloadResult.FAIL_HEAD
    assert get_calls["count"] == 0, "GET must never be called when HEAD times out"


@pytest.mark.django_db
def test_head_content_length_over_limit_returns_fail_size(
    monkeypatch, tmp_path, _allow_external_dns
):
    """HEAD Content-Length > limit → FAIL_SIZE, GET never called."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    over_limit = 11 * 1024 * 1024  # > 10 MB image limit
    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("image/png", over_limit),
    )

    get_calls = {"count": 0}

    def _counting_get(*args, **kwargs):
        get_calls["count"] += 1
        return _fake_get_result("image/png", [b"\x89PNG"])

    monkeypatch.setattr("scraping.file_downloader._download_via_get", _counting_get)

    content, filename, result = download_file(
        "https://example.com/huge.png",
        "tools",
        item_name="HugeTool",
        file_type="image",
    )

    assert content is None
    assert filename is None
    assert result == DownloadResult.FAIL_SIZE
    assert get_calls["count"] == 0, "GET must never be called when HEAD says too large"


@pytest.mark.django_db
def test_successful_download_writes_meta_json(
    monkeypatch, tmp_path, _allow_external_dns
):
    """Successful download writes .meta.json with all required fields."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("application/pdf", 100),
    )
    monkeypatch.setattr(
        "scraping.file_downloader._download_via_get",
        lambda *a, **k: _fake_get_result("application/pdf", [b"%PDF-1.4 content"]),
    )

    content, filename, result = download_file(
        "https://example.com/paper.pdf",
        "news",
        item_name="My Paper",
        file_type="document",
    )

    assert result == DownloadResult.SUCCESS
    assert filename is not None

    # Locate the .meta.json sidecar
    media_root = Path(tmp_path)
    meta_files = list((media_root / "scraping" / "news" / "pdfs").glob("*.meta.json"))
    assert len(meta_files) == 1, f"Expected 1 .meta.json, found {len(meta_files)}"

    with open(meta_files[0], encoding="utf-8") as f:
        meta = json.load(f)

    required_fields = {
        "original_url",
        "downloaded_at",
        "content_type",
        "file_size_bytes",
        "sha256",
        "category",
        "item_name",
    }
    assert required_fields.issubset(meta.keys()), (
        f"Missing fields: {required_fields - meta.keys()}"
    )
    assert meta["original_url"] == "https://example.com/paper.pdf"
    assert meta["content_type"] == "application/pdf"
    assert meta["category"] == "news"
    assert meta["item_name"] == "My Paper"
    assert meta["file_size_bytes"] > 0
    assert len(meta["sha256"]) == 64  # full SHA-256 hex


@pytest.mark.django_db
def test_sidecar_url_match_returns_skip_exists(
    monkeypatch, tmp_path, _allow_external_dns
):
    """Second call with same URL reads sidecar → SKIP_EXISTS, no HTTP."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    # --- First call: normal download ---
    monkeypatch.setattr(
        "scraping.file_downloader._head_preflight",
        lambda *a, **k: _fake_head_result("application/pdf", 50),
    )
    monkeypatch.setattr(
        "scraping.file_downloader._download_via_get",
        lambda *a, **k: _fake_get_result("application/pdf", [b"%PDF"]),
    )

    url = "https://example.com/unique-paper.pdf"
    content1, filename1, result1 = download_file(
        url, "news", item_name="UniPaper", file_type="document"
    )
    assert result1 == DownloadResult.SUCCESS

    # Write the actual asset file so the sidecar check finds it
    asset_path = Path(tmp_path) / filename1
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"%PDF")

    # --- Second call: no HTTP should happen ---
    http_calls = {"head": 0, "get": 0}

    def _no_head(*a, **k):
        http_calls["head"] += 1
        return _fake_head_result()

    def _no_get(*a, **k):
        http_calls["get"] += 1
        return _fake_get_result("application/pdf", [b"x"])

    monkeypatch.setattr("scraping.file_downloader._head_preflight", _no_head)
    monkeypatch.setattr("scraping.file_downloader._download_via_get", _no_get)

    content2, filename2, result2 = download_file(
        url, "news", item_name="UniPaper", file_type="document"
    )

    assert result2 == DownloadResult.SKIP_EXISTS
    assert filename2 is not None
    assert content2 is None
    assert http_calls["head"] == 0, "HEAD must not be called for sidecar hit"
    assert http_calls["get"] == 0, "GET must not be called for sidecar hit"


@pytest.mark.django_db
def test_ssrf_blocked_url_raises(monkeypatch, tmp_path):
    """SSRF blocked URL → SSRFViolationError raised (FAIL_SSRF handled by caller)."""
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path), raising=False)

    def _loopback_dns(hostname, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _loopback_dns)

    with pytest.raises(SSRFViolationError) as exc:
        download_file(
            "http://localhost/evil.pdf",
            "news",
            item_name="Evil",
            file_type="document",
        )

    assert exc.value.offending_ip == "127.0.0.1"


@pytest.mark.django_db
def test_all_download_result_codes_are_strings():
    """All DownloadResult codes are non-empty strings."""
    codes = [
        DownloadResult.SUCCESS,
        DownloadResult.SKIP_EXISTS,
        DownloadResult.FAIL_MIME,
        DownloadResult.FAIL_SIZE,
        DownloadResult.FAIL_SSRF,
        DownloadResult.FAIL_HEAD,
        DownloadResult.FAIL_NETWORK,
        DownloadResult.FAIL_WRITE,
    ]
    for code in codes:
        assert isinstance(code, str)
        assert len(code) > 0

    # All codes must be unique
    assert len(set(codes)) == len(codes), "DownloadResult codes must be unique"
