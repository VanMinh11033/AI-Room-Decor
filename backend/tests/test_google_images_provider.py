"""Unit tests for the Google Custom Search image provider (mocked HTTP)."""

import httpx
import pytest

from app.services.google_images_provider import (
    GoogleImagesNotConfiguredError,
    GoogleImagesProvider,
    build_google_image_query,
)
from app.services.stock_image_providers import UpstreamRequestError


class FakeCategory:
    def __init__(self, name):
        self.name = name


class FakeProduct:
    def __init__(self, name, category):
        self.name = name
        self.category = FakeCategory(category)


def google_item(title, link, display_link="example.com", width=800, height=800, mime="image/jpeg", context_link="https://example.com/page"):
    return {
        "title": title,
        "link": link,
        "displayLink": display_link,
        "mime": mime,
        "image": {
            "contextLink": context_link,
            "thumbnailLink": link + "?thumb=1",
            "width": width,
            "height": height,
        },
    }


def provider_with_handler(handler, **kwargs):
    return GoogleImagesProvider(
        api_key="test-key",
        cse_id="test-cx",
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
    )


def test_build_google_image_query_is_product_specific():
    assert build_google_image_query(FakeProduct("Abstract Wall Art", "Wall Decor")) == (
        "Abstract Wall Art Wall Decor canvas painting home decor"
    )
    assert build_google_image_query(FakeProduct("Brass Floor Lamp", "Lighting")) == (
        "Brass Floor Lamp Lighting product photo"
    )
    assert build_google_image_query(FakeProduct("Japandi Low Sofa", "Sofa")) == "Japandi Low Sofa furniture"


def test_search_raises_when_not_configured():
    provider = GoogleImagesProvider(api_key=None, cse_id=None)
    with pytest.raises(GoogleImagesNotConfiguredError):
        provider.search(FakeProduct("Sofa", "Sofa"))


def test_search_parses_results_and_uses_name_based_query():
    captured = {}

    def handler(request):
        captured["q"] = request.url.params.get("q")
        captured["searchType"] = request.url.params.get("searchType")
        captured["cx"] = request.url.params.get("cx")
        return httpx.Response(200, json={"items": [google_item("Brass Floor Lamp", "https://img.example/lamp.jpg")]})

    provider = provider_with_handler(handler)
    candidates = provider.search(FakeProduct("Brass Floor Lamp", "Lighting"))

    assert captured["searchType"] == "image"
    assert captured["cx"] == "test-cx"
    assert "Brass Floor Lamp" in captured["q"]

    assert len(candidates) == 1
    c = candidates[0]
    assert c["direct_image_url"] == "https://img.example/lamp.jpg"
    assert c["source"] == "google"
    assert c["source_page"] == "https://example.com/page"
    assert c["license_decision"] == "ACCEPTED"
    assert c["semantic_decision"] == "ACCEPT"
    assert c["width"] == 800 and c["height"] == 800


def test_search_marks_irrelevant_title_as_reject():
    handler = lambda request: httpx.Response(200, json={"items": [google_item("Random unrelated object", "https://img.example/x.jpg")]})
    provider = provider_with_handler(handler)
    candidates = provider.search(FakeProduct("Brass Floor Lamp", "Lighting"))
    assert len(candidates) == 1
    assert candidates[0]["semantic_decision"] == "REJECT"
    assert "does not mention" in candidates[0]["semantic_reason"]


def test_search_raises_clear_error_on_upstream_failure():
    handler = lambda request: httpx.Response(403, json={"error": {"message": "forbidden"}})
    provider = provider_with_handler(handler)
    with pytest.raises(UpstreamRequestError):
        provider.search(FakeProduct("Sofa", "Sofa"))
