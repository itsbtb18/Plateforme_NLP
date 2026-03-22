import socket

import pytest

from scraping.file_downloader import SSRFViolation, validate_url_safety


def _fake_getaddrinfo_factory(mapping):
    def _fake_getaddrinfo(hostname, port):
        ip = mapping.get(hostname)
        if ip is None:
            raise socket.gaierror(f"Unknown host for test: {hostname}")
        return [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (ip, 0),
            )
        ]

    return _fake_getaddrinfo


def test_validate_url_safety_blocks_localhost(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"localhost": "127.0.0.1"}),
    )

    with pytest.raises(SSRFViolation) as exc:
        validate_url_safety("http://localhost/test")

    assert exc.value.offending_ip == "127.0.0.1"


def test_validate_url_safety_blocks_rfc1918_10_range(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"internal.example": "10.0.0.1"}),
    )

    with pytest.raises(SSRFViolation) as exc:
        validate_url_safety("http://internal.example/file.pdf")

    assert exc.value.offending_ip == "10.0.0.1"


def test_validate_url_safety_blocks_metadata_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"metadata.aws": "169.254.169.254"}),
    )

    with pytest.raises(SSRFViolation) as exc:
        validate_url_safety("http://metadata.aws/latest/meta-data")

    assert exc.value.offending_ip == "169.254.169.254"


def test_validate_url_safety_allows_external_domain(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory({"example.com": "93.184.216.34"}),
    )

    assert validate_url_safety("https://example.com/file.pdf") is True


def test_validate_url_safety_allowed_domains_allowlist(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        _fake_getaddrinfo_factory(
            {
                "files.example.com": "93.184.216.34",
                "evil.com": "93.184.216.35",
            }
        ),
    )

    # Allowed host passes
    assert (
        validate_url_safety(
            "https://files.example.com/doc.pdf",
            allowed_domains=["example.com"],
        )
        is True
    )

    # Disallowed host fails even with external IP
    with pytest.raises(SSRFViolation):
        validate_url_safety(
            "https://evil.com/doc.pdf",
            allowed_domains=["example.com"],
        )
