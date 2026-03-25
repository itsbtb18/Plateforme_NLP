from pathlib import Path

import pytest
import responses

from scraping.file_downloader import download_file


pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def test_download_success_returns_metadata(media_root, mocked_http, allow_external_dns):
    url = "https://files.example.org/paper.pdf"
    body = b"%PDF-1.4\nMock content"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=body,
        status=200,
        content_type="application/pdf",
    )

    content, filename, mime = download_file(url, category="news", file_type="document")

    assert content is not None
    assert mime == "application/pdf"
    assert filename is not None
    assert filename.endswith(".pdf")


def test_download_rejects_disallowed_mime(media_root, mocked_http, allow_external_dns):
    url = "https://files.example.org/binary.exe"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=b"MZ...",
        status=200,
        content_type="application/x-msdownload",
    )

    assert download_file(url, category="news", file_type="document") == (
        None,
        None,
        None,
    )


def test_download_rejects_private_ssrf(media_root, mocked_http, monkeypatch):
    def _private_ip(*args, **kwargs):
        return [
            (
                2,
                1,
                6,
                "",
                ("127.0.0.1", 0),
            )
        ]

    monkeypatch.setattr("socket.getaddrinfo", _private_ip)

    url = "https://files.example.org/private.pdf"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=b"x",
        status=200,
        content_type="application/pdf",
    )

    from scraping.file_downloader import SSRFViolationError

    with pytest.raises(SSRFViolationError):
        download_file(url, category="news", file_type="document")


def test_download_rejects_file_too_large(
    media_root, mocked_http, allow_external_dns, monkeypatch
):
    monkeypatch.setattr("scraping.file_downloader.MAX_DOCUMENT_SIZE_MB", 0)
    url = "https://files.example.org/too-large.pdf"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=b"0123456789",
        status=200,
        content_type="application/pdf",
    )

    assert download_file(url, category="news", file_type="document") == (
        None,
        None,
        None,
    )


def test_download_skips_when_url_already_seen(
    media_root, mocked_http, allow_external_dns
):
    url = "https://files.example.org/seen.pdf"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=b"%PDF-first",
        status=200,
        content_type="application/pdf",
    )
    first = download_file(url, category="news", file_type="document")
    assert first[0] is not None

    # Simulate previously saved file on storage path to trigger hash-based skip.
    existing_name = first[1]
    existing_path = Path(media_root) / existing_name
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_bytes(b"cached")

    second = download_file(url, category="news", file_type="document")
    assert second[0] is None
    assert second[1] is not None


def test_download_handles_404(media_root, mocked_http, allow_external_dns):
    url = "https://files.example.org/missing.pdf"
    mocked_http.add(
        method=responses.GET,
        url=url,
        body=b"not found",
        status=404,
        content_type="text/plain",
    )

    assert download_file(url, category="news", file_type="document") == (
        None,
        None,
        None,
    )
