import re
import time
from typing import Any, Callable
from urllib.parse import quote

import httpx

from app.services.semantic_filter import derive_object_rule, semantic_assess

PREFERRED_LICENSES = {"cc0", "pdm", "by", "by-sa"}

OPENVERSE_BASE_URL = "https://api.openverse.org/v1/images/"
USER_AGENT = "ai-room-decor-academic/0.1"


def license_decision(license_code: str | None) -> str:
    code = (license_code or "").strip().lower()
    if code in PREFERRED_LICENSES:
        return "ACCEPTED"
    return "LICENSE_REVIEW_REQUIRED"


def build_openverse_queries(product: Any) -> list[str]:
    name = (product.name or "").strip()
    category = (product.category.name if product.category else "").strip()
    style = (product.styles[0].name if getattr(product, "styles", None) else "").strip()
    color = (product.colors[0].name if getattr(product, "colors", None) else "").strip()
    material = (product.materials[0].name if getattr(product, "materials", None) else "").strip()

    queries: list[str] = []

    def add(q: str) -> None:
        if q and q not in queries:
            queries.append(q)

    add(name)
    if style and category:
        add(f"{style} {category}")
    if color and category:
        add(f"{color} {category}")
    if material and category:
        add(f"{material} {category}")
    if color and category:
        add(f"{color} {category} isolated")
    return queries[:5]


def _name_tokens(name: str | None) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"[^a-z0-9]+", (name or "").lower()):
        if len(token) >= 2:
            tokens.append(token)
    return list(dict.fromkeys(tokens))


def rank_openverse_candidates(
    candidates: list[dict],
    name_tokens: list[str],
    attribute_keywords: list[str] | None = None,
) -> list[dict]:
    name_tokens = [token.lower() for token in name_tokens if token]
    attribute_keywords = [kw.lower() for kw in (attribute_keywords or []) if kw]

    for candidate in candidates:
        score = 0

        if candidate.get("semantic_decision") == "ACCEPT":
            score += candidate.get("semantic_score", 0)
        else:
            score -= 80

        if candidate["license_decision"] == "ACCEPTED":
            score += 20
        else:
            score -= 30

        width = candidate.get("width")
        height = candidate.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            if width >= 800 and height >= 800:
                score += 12
            elif width >= 400 and height >= 400:
                score += 6
            ratio = width / height
            if 0.5 <= ratio <= 2.0:
                score += 5

        text = " ".join([candidate.get("title") or "", " ".join(candidate.get("tags") or [])]).lower()
        for token in name_tokens:
            if token in text:
                score += 6
        for keyword in attribute_keywords:
            if keyword in text:
                score += 4
        for negative in ("room", "interior", "living room", "bedroom", "lifestyle", "dining room", "office"):
            if negative in text:
                score -= 3

        candidate["rank_score"] = score

    candidates.sort(key=lambda c: (-c["rank_score"], str(c.get("openverse_id") or "")))
    return candidates


class OpenverseImageSourceProvider:
    name = "openverse"

    def __init__(
        self,
        client_factory: Callable[[], Any] | None = None,
        timeout_seconds: int = 30,
        page_size: int = 5,
    ) -> None:
        self._client_factory = client_factory
        self.timeout_seconds = timeout_seconds
        self.page_size = page_size

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.Client(timeout=self.timeout_seconds, follow_redirects=True, headers={"User-Agent": USER_AGENT})

    def _close_client(self, client) -> None:
        if self._client_factory is None:
            client.close()

    def _search_api(self, query: str) -> list[dict]:
        url = f"{OPENVERSE_BASE_URL}?q={quote(query)}&page_size={self.page_size}"
        client = self._client()
        try:
            response = client.get(url)
            response.raise_for_status()
            body = response.json()
            return body.get("results") or []
        finally:
            self._close_client(client)

    def search(self, product: Any, queries: list[str] | None = None) -> list[dict]:
        queries = queries or build_openverse_queries(product)
        object_rule = derive_object_rule(product)
        name_tokens = _name_tokens(product.name)
        attribute_keywords = [s.name for s in getattr(product, "styles", None) or []]
        attribute_keywords += [c.name for c in getattr(product, "colors", None) or []]
        attribute_keywords += [m.name for m in getattr(product, "materials", None) or []]

        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        candidates: list[dict] = []
        for query in queries:
            for item in self._search_api(query):
                openverse_id = item.get("id") or ""
                direct_url = item.get("url") or ""
                if openverse_id and openverse_id in seen_ids:
                    continue
                if direct_url and direct_url in seen_urls:
                    continue
                if openverse_id:
                    seen_ids.add(openverse_id)
                if direct_url:
                    seen_urls.add(direct_url)
                candidate = self._to_candidate(query, item)
                candidate.update(semantic_assess(candidate, object_rule))
                candidates.append(candidate)
            time.sleep(1.0)

        return rank_openverse_candidates(candidates, name_tokens, attribute_keywords)

    def _to_candidate(self, query: str, item: dict) -> dict:
        license_code = item.get("license")
        return {
            "openverse_id": item.get("id"),
            "query": query,
            "title": item.get("title") or "",
            "creator": item.get("creator"),
            "creator_url": item.get("creator_url"),
            "source": item.get("source") or item.get("provider"),
            "source_page": item.get("foreign_landing_url"),
            "direct_image_url": item.get("url"),
            "thumbnail_url": item.get("thumbnail"),
            "license": license_code,
            "license_version": item.get("license_version"),
            "license_url": item.get("license_url"),
            "attribution": item.get("attribution"),
            "width": item.get("width"),
            "height": item.get("height"),
            "filetype": item.get("filetype"),
            "tags": [tag.get("name") for tag in (item.get("tags") or []) if isinstance(tag, dict)],
            "license_decision": license_decision(license_code),
            "semantic_decision": None,
            "semantic_score": 0,
            "semantic_reason": None,
            "rank_score": 0,
        }

    def download(self, url: str) -> tuple[bytes, str]:
        client = self._client()
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "")
        finally:
            self._close_client(client)
