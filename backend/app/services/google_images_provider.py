"""Google Custom Search JSON API image provider (ToS-compliant image search).

Searches Google Images via the Programmable Search Engine (Custom Search JSON
API). This is the supported programmatic interface to Google Images and does not
scrape google.com, so it does not bypass CAPTCHA or anti-bot protections.

Requirements (both required, otherwise the provider is disabled and reports a
clear error instead of silently returning nothing or falling back to another
source):

  - ``GOOGLE_API_KEY``: a Google Cloud API key with the "Custom Search API"
    enabled.
  - ``GOOGLE_CSE_ID``: a Programmable Search Engine ID (``cx``) configured to
    search the entire web with "Image search" enabled.

Cost: the Custom Search JSON API includes 100 free queries per day; additional
queries are billed by Google Cloud ($5 per 1,000 queries).

Relevance filtering here is keyword-based (product name tokens vs. the result
title and source host) and is *not* a visual verification of image contents.
"""

import re
from typing import Any, Callable

import httpx

from app.services.stock_image_providers import MAX_DOWNLOAD_BYTES, StockImageProvider

GOOGLE_CSE_BASE = "https://www.googleapis.com/customsearch/v1"
USER_AGENT = "ai-room-decor/0.1"

# Category -> context suffix appended to the product name so every product gets
# a distinct, relevant query rather than one generic keyword.
_CATEGORY_CONTEXT = {
    "sofa": "furniture",
    "chair": "furniture",
    "table": "furniture",
    "lighting": "product photo",
    "rug": "rug",
    "wall decor": "canvas painting home decor",
    "storage": "furniture",
    "accessories": "home decor",
    "plant decor": "plant decor",
    "bedding": "bedding",
}


class GoogleImagesNotConfiguredError(RuntimeError):
    """Raised when Google Custom Search credentials are missing."""


def build_google_image_query(product: Any) -> str:
    name = (product.name or "").strip()
    category = (product.category.name if getattr(product, "category", None) else "").strip()
    parts = [name]
    if category and category.lower() not in name.lower():
        parts.append(category)
    context = _CATEGORY_CONTEXT.get(category.lower(), "")
    if context and context.lower() not in name.lower():
        parts.append(context)
    return " ".join(part for part in parts if part)


def _name_tokens(name: str | None) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"[^a-z0-9]+", (name or "").lower()):
        if len(token) >= 3:
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def _title_relevance(title: str, source_host: str, name_tokens: list[str]) -> tuple[bool, str]:
    if not name_tokens:
        return True, "no name tokens to match"
    text = f"{title or ''} {source_host or ''}".lower()
    matched = next((token for token in name_tokens if token in text), None)
    if matched is None:
        return False, "title/source does not mention the product name"
    return True, f"matched product token: {matched}"


class GoogleImagesProvider(StockImageProvider):
    name = "google"
    requires_key = True

    def __init__(
        self,
        api_key: str | None = None,
        cse_id: str | None = None,
        client_factory: Callable[[], Any] | None = None,
        timeout_seconds: int = 30,
        resolve_host: Callable[[str], list[str]] | None = None,
        sleep_func: Callable[[float], None] | None = None,
        page_size: int = 10,
    ) -> None:
        super().__init__(client_factory, timeout_seconds, resolve_host, sleep_func)
        from app.core.config import settings

        self._api_key = api_key if api_key is not None else settings.google_api_key
        self._cse_id = cse_id if cse_id is not None else settings.google_cse_id
        self.page_size = page_size

    def enabled(self) -> bool:
        return bool((self._api_key or "").strip()) and bool((self._cse_id or "").strip())

    def _ensure_enabled(self) -> None:
        if not self.enabled():
            raise GoogleImagesNotConfiguredError(
                "Google image search is not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID "
                "in the backend environment, then restart the backend."
            )

    def search(self, product: Any, queries: list[str] | None = None, per_page: int = 10) -> list[dict]:
        self._ensure_enabled()

        if queries:
            query_strings = queries if isinstance(queries, (list, tuple)) else [queries]
        else:
            query_strings = [build_google_image_query(product)]

        name_tokens = _name_tokens(product.name)
        candidates: list[dict] = []
        seen_urls: set[str] = set()

        for query in query_strings:
            params = {
                "key": self._api_key,
                "cx": self._cse_id,
                "q": query,
                "searchType": "image",
                "num": min(per_page or 10, 10),
                "safe": "active",
            }
            client = self._client()
            try:
                response = self._get_with_retry(client, GOOGLE_CSE_BASE, params=params)
                body = response.json()
            finally:
                self._close_client(client)

            for item in body.get("items") or []:
                candidate = self._to_candidate(query, item, name_tokens)
                direct_url = candidate.get("direct_image_url")
                if direct_url and direct_url in seen_urls:
                    continue
                if direct_url:
                    seen_urls.add(direct_url)
                candidates.append(candidate)

        # Most relevant first so the first few accepted candidates win.
        candidates.sort(key=lambda c: (-int(c.get("relevance_score") or 0), str(c.get("title") or "")))
        return candidates

    def download(self, url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[bytes, str]:
        return self.download_public(url, max_bytes)

    def _to_candidate(self, query: str, item: dict, name_tokens: list[str]) -> dict:
        image = item.get("image") or {}
        title = item.get("title") or ""
        context_link = image.get("contextLink")
        display_link = item.get("displayLink") or ""
        direct_url = item.get("link") or ""

        relevant, reason = _title_relevance(title, display_link, name_tokens)
        text = f"{title} {display_link}".lower()
        relevance_score = sum(1 for token in name_tokens if token in text)

        return {
            "query": query,
            "title": title,
            "creator": None,
            "creator_url": None,
            "source": "google",
            "source_page": context_link,
            "page_url": context_link,
            "direct_image_url": direct_url,
            "thumbnail_url": image.get("thumbnailLink"),
            "license": None,
            "license_version": None,
            "license_url": None,
            "attribution": None,
            "width": image.get("width"),
            "height": image.get("height"),
            "filetype": item.get("mime"),
            "license_decision": "ACCEPTED",
            "semantic_decision": "ACCEPT" if relevant else "REJECT",
            "semantic_score": relevance_score,
            "semantic_reason": reason,
            "relevance_score": relevance_score,
        }
