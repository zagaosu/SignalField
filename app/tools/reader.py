from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import Settings
from ..security import quick_url_check, safe_public_url
from .base import PageReader, ReadResult

DATE_PATTERNS = [
    re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"),
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
]


def _parse_datetime(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.date().isoformat()
    except ValueError:
        pass
    for pattern in DATE_PATTERNS:
        match = pattern.search(raw)
        if match:
            try:
                return datetime(
                    int(match.group(1)), int(match.group(2)), int(match.group(3))
                ).date().isoformat()
            except ValueError:
                continue
    return None


def _meta(soup: BeautifulSoup, *, prop: str | None = None, name: str | None = None) -> str | None:
    attrs = {}
    if prop:
        attrs["property"] = prop
    if name:
        attrs["name"] = name
    tag = soup.find("meta", attrs=attrs)
    return str(tag.get("content")).strip() if tag and tag.get("content") else None


def _extract_jsonld_date(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"})[:8]:
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        queue = data if isinstance(data, list) else [data]
        for item in queue[:12]:
            if not isinstance(item, dict):
                continue
            if item.get("@graph"):
                queue.extend(item["@graph"] if isinstance(item["@graph"], list) else [])
            date_value = item.get("datePublished") or item.get("dateCreated")
            parsed = _parse_datetime(str(date_value) if date_value else None)
            if parsed:
                return parsed
    return None


def _extract_published(soup: BeautifulSoup) -> str | None:
    candidates = [
        _meta(soup, prop="article:published_time"),
        _meta(soup, prop="og:published_time"),
        _meta(soup, name="date"),
        _meta(soup, name="pubdate"),
        _meta(soup, name="publishdate"),
        _meta(soup, name="DC.date"),
    ]
    for tag in soup.find_all("time", limit=6):
        candidates.append(tag.get("datetime") or tag.get_text(" ", strip=True))
    candidates.append(_extract_jsonld_date(soup))
    for candidate in candidates:
        parsed = _parse_datetime(candidate)
        if parsed:
            return parsed
    return None


def _extract_title(soup: BeautifulSoup) -> str:
    for finder in (
        lambda: _meta(soup, prop="og:title"),
        lambda: _meta(soup, name="twitter:title"),
        lambda: soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else None,
        lambda: soup.title.get_text(" ", strip=True) if soup.title else None,
    ):
        try:
            value = finder()
        except AttributeError:
            value = None
        if value and len(str(value).strip()) >= 2:
            return re.sub(r"\s+", " ", str(value)).strip()[:300]
    return ""


def _extract_content(soup: BeautifulSoup) -> str:
    for tag in soup(
        ["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header", "form", "aside"]
    ):
        tag.decompose()
    candidates = []
    for selector in ("article", "main", "[role=main]", "#content", ".article-content", ".post-content"):
        candidates.extend(soup.select(selector))
    candidates.append(soup.body or soup)
    best = ""
    for node in candidates:
        paragraphs = []
        seen = set()
        for block in node.find_all(["h1", "h2", "h3", "p", "li", "blockquote", "pre"]):
            text = block.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) < 18 or text in seen:
                continue
            seen.add(text)
            paragraphs.append(text)
        text = "\n".join(paragraphs).strip()
        if not text:
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if len(text) > len(best):
            best = text
    return best[:24000]


def _decode_html(raw: bytes, response: httpx.Response) -> str:
    encodings = []
    content_type = response.headers.get("content-type", "")
    match = re.search(r"charset=([\w-]+)", content_type, re.I)
    if match:
        encodings.append(match.group(1))
    head = raw[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(r"<meta[^>]+charset=[\"']?([\w-]+)", head, re.I)
    if meta_match:
        encodings.append(meta_match.group(1))
    encodings.extend(["utf-8", "gb18030"])
    for encoding in dict.fromkeys(encodings):
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


class SafePageReader(PageReader):
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._client = httpx.Client(
            timeout=httpx.Timeout(settings.page_timeout_seconds, connect=6.0),
            follow_redirects=False,
            headers={
                "User-Agent": "SignalField/0.1 (local research reader; evidence checker)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
            },
            transport=transport,
        )

    def read(self, url: str, *, timeout_seconds: float | None = None) -> ReadResult:
        ok, reason = quick_url_check(url)
        if not ok:
            return ReadResult(ok=False, url=url, error=reason)
        current = url
        timeout = timeout_seconds or self.settings.page_timeout_seconds
        try:
            client = self._client
            for _ in range(4):
                ok, reason = safe_public_url(current)
                if not ok:
                    return ReadResult(ok=False, url=url, final_url=current, error=reason)
                with client.stream(
                    "GET", current, timeout=httpx.Timeout(timeout, connect=min(6.0, timeout))
                ) as response:
                        if response.is_redirect:
                            location = response.headers.get("location")
                            if not location:
                                return ReadResult(ok=False, url=url, error="重定向缺少目标地址")
                            current = urljoin(current, location)
                            continue
                        if response.status_code == 401 or response.status_code == 403:
                            return ReadResult(ok=False, url=url, final_url=current, error="来源拒绝访问")
                        if response.status_code == 404:
                            return ReadResult(ok=False, url=url, final_url=current, error="页面不存在（404）")
                        if response.status_code >= 400:
                            return ReadResult(
                                ok=False,
                                url=url,
                                final_url=current,
                                error=f"页面返回 HTTP {response.status_code}",
                            )
                        content_type = response.headers.get("content-type", "").lower()
                        allowed = (
                            "text/html",
                            "application/xhtml+xml",
                            "text/plain",
                            "application/xml",
                            "text/xml",
                        )
                        if content_type and not any(kind in content_type for kind in allowed):
                            return ReadResult(
                                ok=False,
                                url=url,
                                final_url=current,
                                error="来源不是可读的文本网页",
                                content_type=content_type,
                            )
                        chunks = []
                        total = 0
                        for chunk in response.iter_bytes():
                            total += len(chunk)
                            if total > self.settings.page_max_bytes:
                                return ReadResult(
                                    ok=False,
                                    url=url,
                                    final_url=current,
                                    error="页面超过正文读取大小上限",
                                )
                            chunks.append(chunk)
                        raw = b"".join(chunks)
                        if not raw:
                            return ReadResult(ok=False, url=url, final_url=current, error="页面正文为空")
                        if "text/plain" in content_type:
                            text = raw.decode("utf-8", errors="replace")
                            title = urlparse(current).path.rsplit("/", 1)[-1] or current
                            published = None
                        else:
                            html = _decode_html(raw, response)
                            soup = BeautifulSoup(html, "lxml")
                            title = _extract_title(soup) or urlparse(current).hostname or current
                            published = _extract_published(soup)
                            text = _extract_content(soup)
                        text = re.sub(r"\n{3,}", "\n\n", text).strip()
                        if len(text) < 80:
                            return ReadResult(
                                ok=False,
                                url=url,
                                final_url=current,
                                title=title,
                                error="没有提取到足够正文（可能需要 JavaScript）",
                                content_type=content_type,
                                byte_size=total,
                            )
                        lang = soup.get("lang", "") if "soup" in locals() else ""
                        return ReadResult(
                            ok=True,
                            url=url,
                            final_url=current,
                            title=title,
                            content=text,
                            published_at=published,
                            language=str(lang)[:20],
                            content_type=content_type,
                            byte_size=total,
                        )
                return ReadResult(ok=False, url=url, final_url=current, error="重定向次数过多")
        except httpx.TimeoutException:
            return ReadResult(ok=False, url=url, final_url=current, error="读取超时")
        except httpx.HTTPError:
            return ReadResult(ok=False, url=url, final_url=current, error="网络读取失败")
        except Exception:
            return ReadResult(ok=False, url=url, final_url=current, error="正文解析失败")

    def close(self) -> None:
        self._client.close()
