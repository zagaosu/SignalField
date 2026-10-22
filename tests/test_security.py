from __future__ import annotations

from app.security import canonical_url, quick_url_check, safe_public_url


def test_rejects_loopback_private_and_non_http_urls():
    bad_urls = [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.4/",
        "http://192.168.1.5/",
        "file:///C:/Windows/win.ini",
        "http://user:pass@example.com/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://printer.local/",
    ]
    for url in bad_urls:
        ok, _ = quick_url_check(url)
        assert not ok, url


def test_accepts_normal_public_url():
    ok, reason = quick_url_check("https://example.com/a/b?x=1")
    assert ok, reason


def test_canonical_url_removes_tracking_and_fragment():
    url = "https://Example.com:443/news/a/?utm_source=x&utm_medium=y&id=7#comments"
    assert canonical_url(url) == "https://example.com/news/a?id=7"


def test_dns_resolution_rejects_localhost():
    ok, reason = safe_public_url("http://localhost/")
    assert not ok
    assert "本机" in reason or "内网" in reason
