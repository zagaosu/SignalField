from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".home.arpa",
    ".lan",
    ".intranet",
)
BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "spm",
    "ref",
    "ref_src",
}


def quick_url_check(url: str) -> tuple[bool, str]:
    """Cheap validation used before a page read; DNS validation happens later."""
    if not isinstance(url, str) or len(url) > 2048:
        return False, "URL 过长或格式无效"
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "URL 无法解析"
    if parsed.scheme not in {"http", "https"}:
        return False, "仅允许 http/https 链接"
    if not parsed.hostname:
        return False, "链接缺少主机名"
    if parsed.username or parsed.password:
        return False, "不允许带凭据的链接"
    host = parsed.hostname.lower().rstrip(".")
    if host in BLOCKED_HOSTS or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        return False, "链接指向本机或内网域名"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        return False, "链接指向非公网地址"
    return True, ""


def resolve_public_host(hostname: str) -> tuple[bool, str]:
    host = hostname.lower().rstrip(".")
    if host in BLOCKED_HOSTS or any(host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES):
        return False, "链接指向本机或内网域名"
    try:
        ip = ipaddress.ip_address(host)
        addresses = [ip]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return False, "域名无法解析"
        addresses = []
        for info in infos:
            raw = info[4][0].split("%", 1)[0]
            try:
                addresses.append(ipaddress.ip_address(raw))
            except ValueError:
                return False, "域名解析结果无效"
    if not addresses:
        return False, "域名没有可用地址"
    for address in addresses:
        if not address.is_global:
            return False, "域名解析到本机、内网或保留地址"
    return True, ""


def safe_public_url(url: str) -> tuple[bool, str]:
    ok, reason = quick_url_check(url)
    if not ok:
        return False, reason
    host = urlparse(url).hostname or ""
    return resolve_public_host(host)


def canonical_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if (scheme == "http" and netloc.endswith(":80")) or (
        scheme == "https" and netloc.endswith(":443")
    ):
        netloc = netloc.rsplit(":", 1)[0]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    return urlunparse((scheme, netloc, path, "", urlencode(query, doseq=True), ""))


def display_domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def is_demo_domain(domain: str | None) -> bool:
    if not domain:
        return False
    return domain.endswith(".invalid") or domain.endswith(".example")
