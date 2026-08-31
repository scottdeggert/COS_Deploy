"""Allowlisted HTTP fetch. Not wired to the router or any handler."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from tools.logger import log_event

# Confirm with operator before merge. May need to expand.
ALLOWED_DOMAIN_SUFFIX = "brightworkrealty.com"
MAX_CONTENT_CHARS = 50_000
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_REDIRECTS = 5

_RAW_EXTENSIONS = {".json", ".txt"}
_HTML_EXTENSIONS = {".html", ".htm"}
_SKIP_HTML_TAGS = {"script", "style"}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_HTML_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_HTML_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._chunks).split())


def _log(status: str, url: str, byte_count: int = 0, extra: str = "") -> None:
    detail = f"url={url} bytes={byte_count}"
    if extra:
        detail = f"{detail} {extra}"
    log_event(
        "web_fetch",
        "fetch_url",
        status,
        detail=detail,
        file=__file__,
        function="fetch_url",
    )


def _host_allowed(hostname: str) -> bool:
    host = hostname.lower().rstrip(".")
    if not host:
        return False
    return host == ALLOWED_DOMAIN_SUFFIX or host.endswith("." + ALLOWED_DOMAIN_SUFFIX)


def _reject_url(url: str) -> str | None:
    """Return an error string if the URL must not be requested, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return (
            "Error: only http and https URLs can be fetched. "
            f"Rejected: {url}"
        )
    if parsed.username or parsed.password:
        return f"Error: URLs with embedded credentials are not allowed. Rejected: {url}"
    host = parsed.hostname or ""
    if not _host_allowed(host):
        return (
            "Error: domain not allowed. Only URLs on "
            f"{ALLOWED_DOMAIN_SUFFIX} can be fetched. Rejected: {url}"
        )
    return None


def _path_extension(url: str) -> str:
    path = urlparse(url).path.lower()
    if "." not in path.rsplit("/", 1)[-1]:
        return ""
    return "." + path.rsplit(".", 1)[-1]


def _should_strip_html(url: str, content_type: str) -> bool:
    ext = _path_extension(url)
    if ext in _RAW_EXTENSIONS:
        return False
    if ext in _HTML_EXTENSIONS:
        return True
    ct = (content_type or "").lower()
    if "json" in ct or ct.startswith("text/plain"):
        return False
    if "html" in ct:
        return True
    return False


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:
        return " ".join(html.split())
    return extractor.text()


def _cap(text: str) -> str:
    if len(text) <= MAX_CONTENT_CHARS:
        return text
    note = f"\n[truncated: content exceeded {MAX_CONTENT_CHARS} characters]"
    return text[:MAX_CONTENT_CHARS] + note


def fetch_url(url: str) -> str:
    """Fetch an allowlisted URL and return text, or a clear error string."""
    _log("start", url)

    rejected = _reject_url(url)
    if rejected:
        _log("failure", url, extra="rejected")
        return rejected

    current = url
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            response = None
            for _ in range(MAX_REDIRECTS + 1):
                rejected = _reject_url(current)
                if rejected:
                    _log("failure", url, extra=f"redirect_rejected dest={current}")
                    return rejected
                response = client.get(current)
                if response.is_redirect:
                    location = response.headers.get("location", "").strip()
                    if not location:
                        message = f"Error: HTTP {response.status_code} redirect with no Location header."
                        _log("failure", url, extra=message)
                        return message
                    current = urljoin(str(response.url), location)
                    continue
                break
            else:
                message = f"Error: exceeded {MAX_REDIRECTS} redirects."
                _log("failure", url, extra=message)
                return message
    except httpx.TimeoutException:
        message = f"Error: request timed out after {int(REQUEST_TIMEOUT_SECONDS)} seconds."
        _log("failure", url, extra=message)
        return message
    except httpx.HTTPError as exc:
        message = f"Error: request failed ({exc.__class__.__name__})."
        _log("failure", url, extra=str(exc))
        return message

    byte_count = len(response.content or b"")
    if response.status_code >= 400:
        message = f"Error: HTTP {response.status_code} fetching {url}"
        _log("failure", url, byte_count, extra=message)
        return message

    content_type = response.headers.get("content-type", "")
    body = response.text or ""
    if _should_strip_html(str(response.url) if response.url else current, content_type):
        body = _strip_html(body)

    result = _cap(body)
    _log("success", url, byte_count)
    return result
