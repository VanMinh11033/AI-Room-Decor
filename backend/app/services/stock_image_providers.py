"""Stock image providers for the Phase 10C modern catalog pilot.

Provides a common interface over Pexels, Pixabay, Unsplash and Wikimedia Commons
so the pilot can source modern furniture photography without Openverse.

Safety:
  - Providers with a missing API key are "disabled" and return no results; no
    credentials are ever invented, printed or logged.
  - `download` requires HTTPS, restricts to approved CDN hostnames, disables
    automatic redirects and validates every redirect hop (scheme, hostname and
    resolved IP). Private, loopback, link-local and other unsafe addresses are
    rejected, as are URLs with embedded credentials.
  - Downloads stream in bounded chunks and enforce a strict 15 MB maximum.
  - Upstream HTTP errors (including 429) are retried a bounded number of times
    with exponential backoff; error messages never expose the request URL, so
    the Pixabay API key cannot leak through exceptions or logs.
  - Wikimedia Commons license is evaluated per file and NC/ND/unknown rejected.
"""

import ipaddress
import os
import re
import socket
import time
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlparse

import httpx

MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB strict cap

MAX_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 30.0
MAX_RETRY_AFTER_SECONDS = 60.0
MAX_REDIRECTS = 5

DOWNLOAD_HOST_ALLOWLIST = {
    "images.pexels.com",
    "pexels.com",
    "pixabay.com",
    "cdn.pixabay.com",
    "images.unsplash.com",
    "unsplash.com",
    "upload.wikimedia.org",
    "commons.wikimedia.org",
}

PIXABAY_CONTENT_LICENSE = "Pixabay Content License"
PIXABAY_LICENSE_URL = "https://pixabay.com/service/terms/"

PEXELS_BASE = "https://api.pexels.com/v1/search"
PIXABAY_BASE = "https://pixabay.com/api/"
UNSPLASH_BASE = "https://api.unsplash.com/search/photos"
WIKIMEDIA_BASE = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = "ai-room-decor/0.1 (Phase 10C catalog pilot)"

_TAG_RE = re.compile(r"<[^>]+>")


def _env(key: str) -> str | None:
    value = os.environ.get(key)
    return value.strip() if value else None


def _wikimedia_contact() -> str | None:
    """Contact info (email or URL) for the Wikimedia User-Agent.

    Prefers the process environment variable ``WIKIMEDIA_CONTACT`` and falls back
    to ``settings.wikimedia_contact`` so a value in ``.env`` is also honoured.
    """
    value = _env("WIKIMEDIA_CONTACT")
    if value:
        return value
    try:
        from app.core.config import settings

        value = settings.wikimedia_contact
    except Exception:
        value = None
    return (value or "").strip() or None


def wikimedia_user_agent(contact: str | None) -> str:
    """Build a Wikimedia-compliant User-Agent from the configured contact info."""
    if contact:
        return f"ai-room-decor/0.1 ({contact})"
    return "ai-room-decor/0.1"


def _strip_html(text: str | None) -> str:
    return _TAG_RE.sub("", text or "").strip()


def _ext_value(ext: dict, key: str) -> str:
    node = ext.get(key) or {}
    return (node.get("value") or "").strip()


class UpstreamRequestError(Exception):
    """An upstream HTTP failure, reported without the request URL or key."""

    def __init__(self, status_code: int, host: str) -> None:
        self.status_code = status_code
        self.host = host
        super().__init__(f"upstream request failed with status {status_code} (host: {host})")


def wikimedia_license_decision(license_short_name: str | None) -> str:
    """Return 'ACCEPTED' only for licenses safe for commercial reuse."""
    s = (license_short_name or "").lower().strip()
    if not s:
        return "REJECTED"
    if "cc0" in s or "public domain" in s or s in {"pd", "public domain"}:
        return "ACCEPTED"
    if "by" in s and "nc" not in s and "nd" not in s:
        return "ACCEPTED"
    return "REJECTED"


def pixabay_license_decision(license_name: str | None) -> str:
    """Return 'ACCEPTED' only for the known Pixabay Content License."""
    if (license_name or "").strip() == PIXABAY_CONTENT_LICENSE:
        return "ACCEPTED"
    return "REVIEW_REQUIRED"


def _is_allowed_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    for allowed in DOWNLOAD_HOST_ALLOWLIST:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _is_unsafe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_host_ips(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    return sorted({info[4][0] for info in infos})


def _assert_no_unsafe_ips(host: str, resolve_host: Callable[[str], list[str]]) -> None:
    try:
        ips = resolve_host(host)
    except Exception as exc:
        raise ValueError(f"could not resolve download host {host}") from exc
    for ip in ips:
        if _is_unsafe_ip(ip):
            raise ValueError(f"download host {host} resolves to unsafe address {ip}")


def assert_safe_download_url(
    url: str,
    resolve_host: Callable[[str], list[str]] = resolve_host_ips,
    allow_hosts: bool = True,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"unsafe download scheme: {parsed.scheme or '(none)'}")
    if parsed.username or parsed.password:
        raise ValueError("download URL contains embedded credentials")
    host = parsed.hostname
    if not host:
        raise ValueError("download URL is missing a host")
    host = host.lower()
    if allow_hosts and not _is_allowed_host(host):
        raise ValueError(f"download host not allowed: {host}")
    _assert_no_unsafe_ips(host, resolve_host)


def _retry_after_seconds(response) -> float | None:
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class StockImageProvider:
    name = "stock"
    requires_key = False

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        timeout_seconds: int = 30,
        resolve_host: Callable[[str], list[str]] | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self.timeout_seconds = timeout_seconds
        self._resolve_host = resolve_host or resolve_host_ips
        self._sleep = sleep_func or time.sleep

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def _close_client(self, client) -> None:
        if self._client_factory is None:
            client.close()

    def _backoff_seconds(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None and retry_after > 0:
            return min(retry_after, MAX_RETRY_AFTER_SECONDS)
        return min(BASE_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS)

    def _raise_http_error(self, status_code: int, url: str) -> None:
        host = urlparse(url).hostname or "unknown-host"
        raise UpstreamRequestError(status_code, host) from None

    def _get_with_retry(self, client, url: str, **kwargs):
        response = None
        for attempt in range(MAX_RETRIES + 1):
            response = client.get(url, **kwargs)
            if response.status_code in RETRY_STATUS_CODES:
                if attempt < MAX_RETRIES:
                    self._sleep(self._backoff_seconds(attempt, _retry_after_seconds(response)))
                    continue
                break
            if response.status_code >= 400:
                self._raise_http_error(response.status_code, url)
            return response
        self._raise_http_error(response.status_code, url)

    def _read_stream(self, response, max_bytes: int) -> tuple[bytes, str]:
        content_type = response.headers.get("content-type", "")
        length = response.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_bytes:
            raise ValueError(f"image exceeds {max_bytes} bytes (content-length {length})")
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"image exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks), content_type

    def _stream_with_retry(self, client, url: str, max_bytes: int) -> tuple[bytes | None, str | None, str | None]:
        for attempt in range(MAX_RETRIES + 1):
            with client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code in RETRY_STATUS_CODES:
                    if attempt < MAX_RETRIES:
                        self._sleep(self._backoff_seconds(attempt, _retry_after_seconds(response)))
                        continue
                    self._raise_http_error(response.status_code, url)
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        self._raise_http_error(response.status_code, url)
                    return None, None, urljoin(url, location)
                if response.status_code >= 400:
                    self._raise_http_error(response.status_code, url)
                data, content_type = self._read_stream(response, max_bytes)
                return data, content_type, None
        raise AssertionError("unreachable: retry loop exhausted")

    def _download_following_redirects(self, client, url: str, max_bytes: int, allow_hosts: bool = True) -> tuple[bytes, str]:
        current_url = url
        for _hop in range(MAX_REDIRECTS + 1):
            assert_safe_download_url(current_url, self._resolve_host, allow_hosts=allow_hosts)
            data, content_type, redirect_to = self._stream_with_retry(client, current_url, max_bytes)
            if redirect_to is not None:
                current_url = redirect_to
                continue
            return data, content_type
        raise ValueError("too many redirects")

    def enabled(self) -> bool:
        return True

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        return []

    def download(self, url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str]:
        """Download an image over HTTPS, validating every redirect hop."""
        client = self._client()
        try:
            return self._download_following_redirects(client, url, max_bytes)
        finally:
            self._close_client(client)

    def download_public(self, url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str]:
        """Download over HTTPS with SSRF/IP and size checks but no host allowlist.

        Used for trusted sources such as Openverse whose image URLs point to many
        different CDN hosts.
        """
        client = self._client()
        try:
            return self._download_following_redirects(client, url, max_bytes, allow_hosts=False)
        finally:
            self._close_client(client)


class PexelsProvider(StockImageProvider):
    name = "pexels"
    requires_key = True

    def _key(self) -> str | None:
        return _env("PEXELS_API_KEY")

    def enabled(self) -> bool:
        return self._key() is not None

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        key = self._key()
        if not key:
            return []
        client = self._client()
        candidates: list[dict] = []
        try:
            for query in queries:
                url = f"{PEXELS_BASE}?query={quote(query)}&per_page={per_page}"
                response = self._get_with_retry(client, url, headers={"Authorization": key})
                for photo in response.json().get("photos") or []:
                    candidates.append(self._to_candidate(query, photo))
        finally:
            self._close_client(client)
        return candidates

    def _to_candidate(self, query: str, photo: dict) -> dict:
        src = photo.get("src") or {}
        return {
            "id": str(photo.get("id")),
            "source": self.name,
            "query": query,
            "title": photo.get("alt") or "",
            "creator": photo.get("photographer") or "",
            "creator_url": photo.get("photographer_url"),
            "license": "Pexels License",
            "license_url": "https://www.pexels.com/license/",
            "license_decision": "ACCEPTED",
            "page_url": photo.get("url"),
            "direct_image_url": src.get("original") or src.get("large"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "tags": [],
            "attribution": photo.get("photographer") or "",
        }


class PixabayProvider(StockImageProvider):
    name = "pixabay"
    requires_key = True

    def _key(self) -> str | None:
        return _env("PIXABAY_API_KEY")

    def enabled(self) -> bool:
        return self._key() is not None

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        key = self._key()
        if not key:
            return []
        client = self._client()
        candidates: list[dict] = []
        try:
            for query in queries:
                params = {
                    "key": key,
                    "q": query,
                    "image_type": "photo",
                    "safesearch": "true",
                    "per_page": str(per_page),
                }
                response = self._get_with_retry(client, PIXABAY_BASE, params=params)
                for hit in response.json().get("hits") or []:
                    candidates.append(self._to_candidate(query, hit))
        finally:
            self._close_client(client)
        return candidates

    def _to_candidate(self, query: str, hit: dict) -> dict:
        tags = (hit.get("tags") or "").split(", ")
        return {
            "id": str(hit.get("id")),
            "source": self.name,
            "query": query,
            "title": ", ".join(tags) or "",
            "creator": hit.get("user") or "",
            "creator_url": None,
            "user_id": hit.get("user_id"),
            "license": PIXABAY_CONTENT_LICENSE,
            "license_url": PIXABAY_LICENSE_URL,
            "license_decision": pixabay_license_decision(PIXABAY_CONTENT_LICENSE),
            "page_url": hit.get("pageURL"),
            "direct_image_url": hit.get("largeImageURL") or hit.get("webformatURL"),
            "width": hit.get("imageWidth"),
            "height": hit.get("imageHeight"),
            "tags": tags,
            "attribution": hit.get("user") or "",
        }


class UnsplashProvider(StockImageProvider):
    name = "unsplash"
    requires_key = True

    def _key(self) -> str | None:
        return _env("UNSPLASH_ACCESS_KEY")

    def enabled(self) -> bool:
        return self._key() is not None

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        key = self._key()
        if not key:
            return []
        client = self._client()
        candidates: list[dict] = []
        try:
            for query in queries:
                url = f"{UNSPLASH_BASE}?query={quote(query)}&per_page={per_page}"
                response = self._get_with_retry(client, url, headers={"Authorization": f"Client-ID {key}"})
                for photo in response.json().get("results") or []:
                    candidates.append(self._to_candidate(query, photo))
        finally:
            self._close_client(client)
        return candidates

    def _to_candidate(self, query: str, photo: dict) -> dict:
        urls = photo.get("urls") or {}
        user = photo.get("user") or {}
        links = photo.get("links") or {}
        return {
            "id": photo.get("id"),
            "source": self.name,
            "query": query,
            "title": photo.get("alt_description") or photo.get("description") or "",
            "creator": user.get("name") or "",
            "creator_url": (user.get("links") or {}).get("html"),
            "license": "Unsplash License",
            "license_url": "https://unsplash.com/license",
            "license_decision": "ACCEPTED",
            "page_url": links.get("html"),
            "direct_image_url": urls.get("raw") or urls.get("full") or urls.get("regular"),
            "width": photo.get("width"),
            "height": photo.get("height"),
            "tags": [],
            "attribution": user.get("name") or "",
        }


class WikimediaProvider(StockImageProvider):
    name = "wikimedia"
    requires_key = False

    def enabled(self) -> bool:
        return _wikimedia_contact() is not None

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": wikimedia_user_agent(_wikimedia_contact())},
        )

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        client = self._client()
        candidates: list[dict] = []
        try:
            for query in queries:
                params = {
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"filetype:bitmap {query}",
                    "gsrnamespace": "6",
                    "gsrlimit": str(per_page),
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata|size",
                    "iiurlwidth": "1280",
                    "format": "json",
                }
                response = self._get_with_retry(client, WIKIMEDIA_BASE, params=params)
                body = response.json()
                pages = (body.get("query") or {}).get("pages") or {}
                for page in pages.values():
                    imageinfo = (page.get("imageinfo") or [None])[0]
                    if not imageinfo:
                        continue
                    candidates.append(self._to_candidate(query, page, imageinfo))
        finally:
            self._close_client(client)
        return candidates

    def _to_candidate(self, query: str, page: dict, imageinfo: dict) -> dict:
        ext = imageinfo.get("extmetadata") or {}
        license_short = _ext_value(ext, "LicenseShortName")
        artist = _strip_html(_ext_value(ext, "Artist"))
        return {
            "id": str(page.get("pageid")),
            "source": self.name,
            "query": query,
            "title": page.get("title") or "",
            "creator": artist,
            "creator_url": None,
            "license": license_short,
            "license_url": _ext_value(ext, "LicenseUrl"),
            "license_decision": wikimedia_license_decision(license_short),
            "page_url": imageinfo.get("descriptionurl"),
            "direct_image_url": imageinfo.get("thumburl") or imageinfo.get("url"),
            "width": imageinfo.get("width"),
            "height": imageinfo.get("height"),
            "tags": [],
            "attribution": artist,
        }


class OpenverseProvider(StockImageProvider):
    name = "openverse"
    requires_key = False

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        timeout_seconds: int = 30,
        resolve_host: Callable[[str], list[str]] | None = None,
        sleep_func: Callable[[float], None] | None = None,
        page_size: int = 20,
    ) -> None:
        super().__init__(client_factory, timeout_seconds, resolve_host, sleep_func)
        from app.services.openverse_provider import OpenverseImageSourceProvider

        self._openverse = OpenverseImageSourceProvider(
            client_factory=client_factory,
            timeout_seconds=timeout_seconds,
            page_size=page_size,
        )

    def search(self, product: Any, queries: list[str], per_page: int = 20) -> list[dict]:
        return self._openverse.search(product, queries)

    def download(self, url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str]:
        return self.download_public(url, max_bytes)


ALL_PROVIDER_CLASSES: tuple[type[StockImageProvider], ...] = (
    PexelsProvider,
    PixabayProvider,
    UnsplashProvider,
    WikimediaProvider,
    OpenverseProvider,
)


def build_providers(only_names: list[str] | None = None) -> list[StockImageProvider]:
    """Build stock image providers, optionally restricted to a named subset.

    ``only_names`` matches each provider's ``name`` attribute (for example
    ``["wikimedia"]``). When omitted, every provider is built.
    """
    allowed = {name.strip().lower() for name in only_names} if only_names is not None else None
    providers: list[StockImageProvider] = []
    for cls in ALL_PROVIDER_CLASSES:
        if allowed is not None and cls.name not in allowed:
            continue
        providers.append(cls())
    return providers
