"""Offline unit tests for Phase 10C Stage 2B stock image providers and pilot.

All HTTP is mocked via httpx.MockTransport — no real network, no real downloads.
DNS resolution is faked via an injected ``resolve_host`` callable, so no socket
lookups happen during tests.
"""

import json
from decimal import Decimal
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.models.entities import Category, Product, ProductImage, ProductStatus
from app.services.stock_image_providers import (
    MAX_DOWNLOAD_BYTES,
    MAX_RETRIES,
    OpenverseProvider,
    PexelsProvider,
    PixabayProvider,
    UnsplashProvider,
    UpstreamRequestError,
    WikimediaProvider,
    build_providers,
    pixabay_license_decision,
    wikimedia_license_decision,
    wikimedia_user_agent,
)
from scripts.catalog_v3_pilot import _resolve_staging_root, build_contact_sheet, ingest_manual_images, run_pilot


class FakeCategory:
    def __init__(self, name):
        self.name = name


class FakeProduct:
    def __init__(self, name, category, styles=(), colors=(), materials=()):
        self.name = name
        self.category = FakeCategory(category)
        self.styles = []
        self.colors = []
        self.materials = []


def provider_with_handler(provider_cls, handler, resolve_host=None, sleep_func=None):
    return provider_cls(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        resolve_host=resolve_host or (lambda host: ["93.184.216.34"]),
        sleep_func=sleep_func or (lambda seconds: None),
    )


def jpeg_bytes(size=(800, 800)):
    img = Image.new("RGB", size, (255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_product(db):
    category = Category(name="Sofa", slug="sofa", is_active=True)
    db.add(category)
    db.commit()
    product = Product(
        category_id=category.id,
        name="Japandi Low Sofa",
        slug="japandi-low-sofa",
        price=Decimal("100"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db.add(product)
    db.commit()
    return product


# --- provider normalization (mocked HTTP) ---

def test_pexels_normalization(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "test-pexels-key")
    payload = {
        "photos": [
            {
                "id": 101,
                "alt": "Modern cream sofa",
                "photographer": "Alice",
                "photographer_url": "https://www.pexels.com/@alice",
                "url": "https://www.pexels.com/photo/101",
                "width": 4000,
                "height": 3000,
                "src": {"original": "https://images.pexels.com/photos/101/pexels-photo-101.jpeg"},
            }
        ]
    }
    handler = lambda request: httpx.Response(200, json=payload)
    provider = provider_with_handler(PexelsProvider, handler)
    candidates = provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source"] == "pexels"
    assert c["title"] == "Modern cream sofa"
    assert c["creator"] == "Alice"
    assert c["license"] == "Pexels License"
    assert c["license_decision"] == "ACCEPTED"
    assert c["direct_image_url"].endswith("pexels-photo-101.jpeg")
    assert c["width"] == 4000 and c["height"] == 3000


def test_pixabay_normalization(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-pixabay-key")
    payload = {
        "hits": [
            {
                "id": 202,
                "tags": "sofa, furniture, modern",
                "user": "Bob",
                "user_id": 99,
                "pageURL": "https://pixabay.com/photos/202/",
                "largeImageURL": "https://pixabay.com/get/202_1280.jpg",
                "webformatURL": "https://pixabay.com/get/202_640.jpg",
                "imageWidth": 3000,
                "imageHeight": 2000,
            }
        ]
    }
    handler = lambda request: httpx.Response(200, json=payload)
    provider = provider_with_handler(PixabayProvider, handler)
    candidates = provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source"] == "pixabay"
    assert c["creator"] == "Bob"
    assert c["user_id"] == 99
    assert c["license"] == "Pixabay Content License"
    assert c["license_decision"] == "ACCEPTED"
    assert c["page_url"] == "https://pixabay.com/photos/202/"
    assert c["direct_image_url"] == "https://pixabay.com/get/202_1280.jpg"
    assert c["tags"] == ["sofa", "furniture", "modern"]


def test_unsplash_normalization(monkeypatch):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-unsplash-key")
    payload = {
        "results": [
            {
                "id": "abc123",
                "alt_description": "modern lounge chair",
                "width": 4000,
                "height": 2667,
                "urls": {"raw": "https://images.unsplash.com/photo-1", "regular": "https://images.unsplash.com/photo-1?w=1080"},
                "user": {"name": "Carol", "links": {"html": "https://unsplash.com/@carol"}},
                "links": {"html": "https://unsplash.com/photos/abc123"},
            }
        ]
    }
    handler = lambda request: httpx.Response(200, json=payload)
    provider = provider_with_handler(UnsplashProvider, handler)
    candidates = provider.search(FakeProduct("Chair", "Chair"), ["chair"])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source"] == "unsplash"
    assert c["title"] == "modern lounge chair"
    assert c["creator"] == "Carol"
    assert c["license"] == "Unsplash License"
    assert c["license_decision"] == "ACCEPTED"
    assert c["direct_image_url"] == "https://images.unsplash.com/photo-1"


def test_wikimedia_normalization_and_license():
    payload = {
        "query": {
            "pages": {
                "123": {
                    "pageid": 123,
                    "title": "File:Modern sofa.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/sofa.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Modern_sofa.jpg",
                            "thumburl": "https://upload.wikimedia.org/1280px-sofa.jpg",
                            "width": 2000,
                            "height": 1500,
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "Artist": {"value": "Jane Doe"},
                                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                            },
                        }
                    ],
                }
            }
        }
    }
    handler = lambda request: httpx.Response(200, json=payload)
    provider = provider_with_handler(WikimediaProvider, handler)
    candidates = provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source"] == "wikimedia"
    assert c["license"] == "CC BY-SA 4.0"
    assert c["license_decision"] == "ACCEPTED"
    assert c["creator"] == "Jane Doe"


@pytest.mark.parametrize(
    "license_name,expected",
    [
        ("CC0", "ACCEPTED"),
        ("Public domain", "ACCEPTED"),
        ("CC BY 4.0", "ACCEPTED"),
        ("CC BY-SA 4.0", "ACCEPTED"),
        ("CC BY-NC 2.0", "REJECTED"),
        ("CC BY-ND 4.0", "REJECTED"),
        ("CC BY-NC-SA 4.0", "REJECTED"),
        (None, "REJECTED"),
        ("", "REJECTED"),
    ],
)
def test_wikimedia_license_decision(license_name, expected):
    assert wikimedia_license_decision(license_name) == expected


def test_pixabay_license_decision():
    assert pixabay_license_decision("Pixabay Content License") == "ACCEPTED"
    assert pixabay_license_decision("CC BY-NC 2.0") == "REVIEW_REQUIRED"
    assert pixabay_license_decision(None) == "REVIEW_REQUIRED"


# --- wikimedia-only provider selection ---

def test_build_providers_wikimedia_only():
    providers = build_providers(only_names=["wikimedia"])
    assert [p.name for p in providers] == ["wikimedia"]
    assert all(isinstance(p, WikimediaProvider) for p in providers)


def test_build_providers_wikimedia_only_ignores_other_keys(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "pexels-key")
    monkeypatch.setenv("PIXABAY_API_KEY", "pixabay-key")
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "unsplash-key")

    providers = build_providers(only_names=["wikimedia"])

    assert [p.name for p in providers] == ["wikimedia"]


def test_build_providers_default_includes_all():
    providers = build_providers()
    assert [p.name for p in providers] == ["pexels", "pixabay", "unsplash", "wikimedia", "openverse"]


def test_build_providers_openverse_only():
    providers = build_providers(only_names=["openverse"])
    assert [p.name for p in providers] == ["openverse"]
    assert all(isinstance(p, OpenverseProvider) for p in providers)


def test_openverse_normalization():
    payload = {
        "results": [
            {
                "id": "abc",
                "title": "Modern sofa",
                "url": "https://live.staticflickr.com/sofa.jpg",
                "creator": "Alice",
                "creator_url": "https://www.flickr.com/photos/alice",
                "foreign_landing_url": "https://www.flickr.com/photos/alice/sofa",
                "license": "by-sa",
                "license_version": "2.0",
                "license_url": "https://creativecommons.org/licenses/by-sa/2.0/",
                "provider": "flickr",
                "source": "flickr",
                "attribution": "by Alice CC BY-SA 2.0",
                "width": 1024,
                "height": 800,
                "filetype": "jpg",
                "tags": [{"name": "sofa"}, {"name": "modern"}],
            }
        ]
    }
    handler = lambda request: httpx.Response(200, json=payload)
    provider = provider_with_handler(OpenverseProvider, handler)
    candidates = provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["source"] == "flickr"
    assert c["license_decision"] == "ACCEPTED"
    assert c["direct_image_url"] == "https://live.staticflickr.com/sofa.jpg"
    assert c["creator"] == "Alice"
    assert c["title"] == "Modern sofa"


# --- Wikimedia User-Agent / contact handling ---

def test_wikimedia_user_agent_includes_contact():
    assert wikimedia_user_agent("contact@example.org") == "ai-room-decor/0.1 (contact@example.org)"
    assert (
        wikimedia_user_agent("https://example.org/ai-room-decor")
        == "ai-room-decor/0.1 (https://example.org/ai-room-decor)"
    )


def test_wikimedia_user_agent_without_contact():
    assert wikimedia_user_agent(None) == "ai-room-decor/0.1"
    assert wikimedia_user_agent("") == "ai-room-decor/0.1"


def test_wikimedia_requires_contact(monkeypatch):
    monkeypatch.delenv("WIKIMEDIA_CONTACT", raising=False)
    monkeypatch.setattr(settings, "wikimedia_contact", None)
    provider = WikimediaProvider()
    assert provider.enabled() is False


def test_wikimedia_enabled_with_contact(monkeypatch):
    monkeypatch.setenv("WIKIMEDIA_CONTACT", "contact@example.org")
    provider = WikimediaProvider()
    assert provider.enabled() is True


def test_wikimedia_client_uses_contact_user_agent(monkeypatch):
    monkeypatch.setenv("WIKIMEDIA_CONTACT", "contact@example.org")
    provider = WikimediaProvider()
    client = provider._client()
    try:
        assert client.headers["User-Agent"] == "ai-room-decor/0.1 (contact@example.org)"
    finally:
        client.close()


# --- missing API key: provider skipped, no request, no invented credentials ---

@pytest.mark.parametrize("provider_cls,env_key", [
    (PexelsProvider, "PEXELS_API_KEY"),
    (PixabayProvider, "PIXABAY_API_KEY"),
    (UnsplashProvider, "UNSPLASH_ACCESS_KEY"),
])
def test_missing_key_skips_provider(monkeypatch, provider_cls, env_key):
    monkeypatch.delenv(env_key, raising=False)

    def exploding_factory():
        raise AssertionError("client factory must not be called when key is missing")

    provider = provider_cls(client_factory=exploding_factory)
    assert provider.enabled() is False
    assert provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"]) == []


# --- download streaming + strict 15 MB cap ---

def test_download_returns_bytes_and_content_type():
    handler = lambda request: httpx.Response(200, content=b"\xff\xd8fake", headers={"content-type": "image/jpeg"})
    provider = provider_with_handler(WikimediaProvider, handler)
    data, content_type = provider.download("https://upload.wikimedia.org/a.jpg")
    assert data == b"\xff\xd8fake"
    assert content_type == "image/jpeg"


def test_download_rejects_oversized_content_length():
    handler = lambda request: httpx.Response(
        200, content=b"x", headers={"content-length": str(MAX_DOWNLOAD_BYTES + 1)}
    )
    provider = provider_with_handler(WikimediaProvider, handler)
    with pytest.raises(ValueError):
        provider.download("https://upload.wikimedia.org/big.jpg")


# --- HTTPS, redirect, IP and credential validation (mocked HTTP, fake resolver) ---

def test_download_rejects_non_https_scheme():
    provider = provider_with_handler(WikimediaProvider, lambda request: httpx.Response(200, content=b"x"))
    with pytest.raises(ValueError, match="scheme"):
        provider.download("http://upload.wikimedia.org/a.jpg")


def test_download_rejects_embedded_credentials():
    provider = provider_with_handler(WikimediaProvider, lambda request: httpx.Response(200, content=b"x"))
    with pytest.raises(ValueError, match="credentials"):
        provider.download("https://user:pass@upload.wikimedia.org/a.jpg")


def test_download_rejects_non_allowlisted_host():
    provider = provider_with_handler(WikimediaProvider, lambda request: httpx.Response(200, content=b"x"))
    with pytest.raises(ValueError, match="host not allowed"):
        provider.download("https://evil.example.com/a.jpg")


def test_download_rejects_private_ip():
    provider = provider_with_handler(
        WikimediaProvider,
        lambda request: httpx.Response(200, content=b"x"),
        resolve_host=lambda host: ["127.0.0.1"],
    )
    with pytest.raises(ValueError, match="unsafe address"):
        provider.download("https://upload.wikimedia.org/a.jpg")


def test_download_rejects_link_local_ip():
    provider = provider_with_handler(
        WikimediaProvider,
        lambda request: httpx.Response(200, content=b"x"),
        resolve_host=lambda host: ["169.254.1.1"],
    )
    with pytest.raises(ValueError, match="unsafe address"):
        provider.download("https://upload.wikimedia.org/a.jpg")


def test_download_rejects_loopback_ip():
    provider = provider_with_handler(
        WikimediaProvider,
        lambda request: httpx.Response(200, content=b"x"),
        resolve_host=lambda host: ["::1"],
    )
    with pytest.raises(ValueError, match="unsafe address"):
        provider.download("https://upload.wikimedia.org/a.jpg")


def test_download_rejects_redirect_to_http():
    def handler(request):
        if request.url.path == "/start.jpg":
            return httpx.Response(302, headers={"location": "http://upload.wikimedia.org/final.jpg"})
        return httpx.Response(200, content=b"x")

    provider = provider_with_handler(WikimediaProvider, handler)
    with pytest.raises(ValueError, match="scheme"):
        provider.download("https://upload.wikimedia.org/start.jpg")


def test_download_rejects_redirect_to_non_allowlisted_host():
    def handler(request):
        if request.url.path == "/start.jpg":
            return httpx.Response(302, headers={"location": "https://evil.example.com/final.jpg"})
        return httpx.Response(200, content=b"x")

    provider = provider_with_handler(WikimediaProvider, handler)
    with pytest.raises(ValueError, match="host not allowed"):
        provider.download("https://upload.wikimedia.org/start.jpg")


def test_download_follows_https_redirect():
    def handler(request):
        if request.url.path == "/start.jpg":
            return httpx.Response(302, headers={"location": "https://upload.wikimedia.org/final.jpg"})
        return httpx.Response(200, content=b"\xff\xd8fake", headers={"content-type": "image/jpeg"})

    provider = provider_with_handler(WikimediaProvider, handler)
    data, content_type = provider.download("https://upload.wikimedia.org/start.jpg")
    assert data == b"\xff\xd8fake"
    assert content_type == "image/jpeg"


# --- HTTP 429: bounded retries, exponential backoff, Retry-After ---

def test_pixabay_search_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429, json={})
        return httpx.Response(200, json={"hits": []})

    provider = provider_with_handler(PixabayProvider, handler)
    result = provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert calls["count"] == 3
    assert result == []


def test_pixabay_search_exhausts_retries(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        return httpx.Response(429, json={})

    provider = provider_with_handler(PixabayProvider, handler)
    with pytest.raises(UpstreamRequestError) as exc_info:
        provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert calls["count"] == MAX_RETRIES + 1
    assert exc_info.value.status_code == 429


def test_retry_respects_retry_after(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "test-key")
    sleeps = []

    def handler(request):
        return httpx.Response(429, headers={"retry-after": "2"})

    provider = PixabayProvider(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)),
        resolve_host=lambda host: ["93.184.216.34"],
        sleep_func=sleeps.append,
    )
    with pytest.raises(UpstreamRequestError):
        provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert sleeps == [2.0, 2.0, 2.0]


def test_download_retries_on_429_then_succeeds():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(429)
        return httpx.Response(200, content=b"\xff\xd8fake", headers={"content-type": "image/jpeg"})

    provider = provider_with_handler(WikimediaProvider, handler)
    data, content_type = provider.download("https://upload.wikimedia.org/a.jpg")
    assert calls["count"] == 2
    assert data == b"\xff\xd8fake"
    assert content_type == "image/jpeg"


# --- API key protection: sanitized errors never leak the key ---

def test_pixabay_key_not_in_error_message(monkeypatch):
    monkeypatch.setenv("PIXABAY_API_KEY", "super-secret-key-123")

    def handler(request):
        return httpx.Response(401, json={})

    provider = provider_with_handler(PixabayProvider, handler)
    with pytest.raises(UpstreamRequestError) as exc_info:
        provider.search(FakeProduct("Sofa", "Sofa"), ["sofa"])
    assert "super-secret-key-123" not in str(exc_info.value)
    assert "super-secret-key-123" not in repr(exc_info.value)


# --- pilot stages candidates without touching the database ---

class FakeProvider:
    name = "fake"
    requires_key = False

    def __init__(self, candidates, downloads=None):
        self.candidates = candidates
        self.downloads = downloads or {}

    def enabled(self):
        return True

    def search(self, product, queries):
        return self.candidates

    def download(self, url):
        if url not in self.downloads:
            raise ValueError("no download")
        return self.downloads[url]


def test_pilot_is_database_read_only(tmp_path, db_session):
    product = make_product(db_session)
    db_session.add(ProductImage(product_id=product.id, image_url="/storage/products/old.jpg", is_primary=True, sort_order=0))
    db_session.commit()

    candidate = {
        "id": "1",
        "source": "fake",
        "query": "sofa",
        "title": "Modern sofa",
        "creator": "Tester",
        "creator_url": None,
        "license": "Fake License",
        "license_url": "https://example.com/license",
        "license_decision": "ACCEPTED",
        "page_url": "https://example.com/1",
        "direct_image_url": "https://img.example/sofa.jpg",
        "width": 800,
        "height": 800,
        "tags": ["sofa"],
        "attribution": "Tester",
    }
    provider = FakeProvider([candidate], downloads={"https://img.example/sofa.jpg": (jpeg_bytes(), "image/jpeg")})

    before = sorted(
        [(i.id, i.product_id, i.image_url, i.is_primary, i.sort_order) for i in db_session.query(ProductImage).all()]
    )

    manifest = run_pilot(db_session, tmp_path, [provider], product_ids=[product.id], min_side=800)

    after = sorted(
        [(i.id, i.product_id, i.image_url, i.is_primary, i.sort_order) for i in db_session.query(ProductImage).all()]
    )
    assert before == after  # exact values unchanged, not just row count

    records = manifest["candidates"]
    assert len(records) == 1
    assert records[0]["status"] == "DOWNLOADED"
    assert records[0]["semantic_decision"] == "ACCEPT"
    assert records[0]["requires_review"] is True
    assert (tmp_path / "candidates" / str(product.id) / records[0]["filename"]).exists()


def test_pilot_semantic_reject_is_not_downloaded(tmp_path, db_session):
    product = make_product(db_session)
    candidate = {
        "id": "2",
        "source": "fake",
        "query": "sofa",
        "title": "Vintage teapot",
        "creator": "Tester",
        "creator_url": None,
        "license": "Fake License",
        "license_url": "https://example.com/license",
        "license_decision": "ACCEPTED",
        "page_url": "https://example.com/2",
        "direct_image_url": "https://img.example/teapot.jpg",
        "width": 800,
        "height": 800,
        "tags": ["teapot"],
        "attribution": "Tester",
    }
    provider = FakeProvider([candidate], downloads={})  # no download available
    manifest = run_pilot(db_session, tmp_path, [provider], product_ids=[product.id], min_side=800)
    records = manifest["candidates"]
    assert len(records) == 1
    assert records[0]["status"] == "SEMANTIC_REJECT"
    assert records[0]["filename"] is None
    assert records[0]["rejection_reason"]


# --- error isolation and download limit ---

class FlakySearchProvider:
    name = "wikimedia"
    requires_key = False

    def __init__(self, fail_product_ids, candidates, downloads=None):
        self.fail_product_ids = set(fail_product_ids)
        self.candidates = candidates
        self.downloads = downloads or {}

    def enabled(self):
        return True

    def search(self, product, queries):
        if product.id in self.fail_product_ids:
            raise UpstreamRequestError(503, "commons.wikimedia.org")
        return self.candidates

    def download(self, url):
        if url not in self.downloads:
            raise ValueError("no download")
        return self.downloads[url]


def _colored_jpeg(color):
    img = Image.new("RGB", (800, 800), color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_chair_product(db):
    category = Category(name="Chair", slug="chair", is_active=True)
    db.add(category)
    db.commit()
    product = Product(
        category_id=category.id,
        name="Japandi Accent Chair",
        slug="japandi-accent-chair",
        price=Decimal("100"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db.add(product)
    db.commit()
    return product


def _candidate(i, title, url):
    return {
        "id": str(i),
        "source": "wikimedia",
        "query": "chair",
        "title": title,
        "creator": "Tester",
        "creator_url": None,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_decision": "ACCEPTED",
        "page_url": f"https://commons.wikimedia.org/wiki/File:{i}.jpg",
        "direct_image_url": url,
        "width": 800,
        "height": 800,
        "tags": ["chair"],
        "attribution": "Tester",
    }


def test_search_error_on_one_product_does_not_stop_next(tmp_path, db_session):
    sofa = make_product(db_session)
    chair = _make_chair_product(db_session)

    good = _candidate(1, "Modern accent chair", "https://upload.wikimedia.org/chair.jpg")
    provider = FlakySearchProvider(
        fail_product_ids={sofa.id},
        candidates=[good],
        downloads={"https://upload.wikimedia.org/chair.jpg": (jpeg_bytes(), "image/jpeg")},
    )

    manifest = run_pilot(db_session, tmp_path, [provider], product_ids=[sofa.id, chair.id], min_side=800)

    records = manifest["candidates"]
    assert all(r["product_id"] != sofa.id for r in records)
    assert any(r["product_id"] == chair.id and r["status"] == "DOWNLOADED" for r in records)


def test_pilot_respects_max_downloads_per_product(tmp_path, db_session):
    product = make_product(db_session)

    candidates = []
    downloads = {}
    for i in range(4):
        url = f"https://upload.wikimedia.org/sofa-{i}.jpg"
        candidates.append({
            "id": str(i),
            "source": "wikimedia",
            "query": "sofa",
            "title": "Modern sofa",
            "creator": "Tester",
            "creator_url": None,
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license_decision": "ACCEPTED",
            "page_url": f"https://commons.wikimedia.org/wiki/File:Sofa_{i}.jpg",
            "direct_image_url": url,
            "width": 800,
            "height": 800,
            "tags": ["sofa"],
            "attribution": "Tester",
        })
        downloads[url] = (_colored_jpeg((200 + i * 20, 100, 100)), "image/jpeg")

    provider = FakeProvider(candidates, downloads)

    manifest = run_pilot(db_session, tmp_path, [provider], product_ids=[product.id], min_side=800)

    records = manifest["candidates"]
    downloaded = [r for r in records if r["status"] == "DOWNLOADED"]
    limit_reached = [r for r in records if r["status"] == "LIMIT_REACHED"]
    assert len(downloaded) == 3
    assert len(limit_reached) == 1


def test_resolve_staging_root_versions_existing(tmp_path):
    base = tmp_path / "catalog-v3"
    base.mkdir()
    assert _resolve_staging_root(base) == base

    (base / "manifest.json").write_text("{}")
    resolved = _resolve_staging_root(base)
    assert resolved != base
    assert resolved.name == "catalog-v3-2"
    assert not (resolved / "manifest.json").exists()


def test_ingest_manual_images_stages_local_file(tmp_path, db_session):
    product = make_product(db_session)
    (tmp_path / "manual").mkdir(parents=True)
    image_path = tmp_path / "manual" / "sofa.jpg"
    image_path.write_bytes(jpeg_bytes())

    (tmp_path / "manual-import.json").write_text(
        json.dumps(
            {
                "images": [
                    {
                        "product_id": product.id,
                        "image_path": "manual/sofa.jpg",
                        "source_url": "https://example.com/sofa",
                        "license": "CC BY 4.0",
                        "license_url": "https://creativecommons.org/licenses/by/4.0/",
                        "attribution": "Tester",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = ingest_manual_images(db_session, tmp_path, min_side=800)

    records = manifest["candidates"]
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "DOWNLOADED"
    assert record["requires_review"] is True
    assert record["source"] == "manual"
    assert record["license"] == "CC BY 4.0"
    assert record["attribution"] == "Tester"
    assert record["page_url"] == "https://example.com/sofa"
    assert (tmp_path / "candidates" / str(product.id) / record["filename"]).exists()


def test_contact_sheet_is_written(tmp_path):
    (tmp_path / "candidates" / "1").mkdir(parents=True)
    (tmp_path / "candidates" / "1" / "candidate-001.jpg").write_bytes(jpeg_bytes())
    manifest = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "staging_directory": str(tmp_path),
        "candidates": [
            {
                "product_id": 1,
                "product_name": "Japandi Low Sofa",
                "filename": "candidate-001.jpg",
                "title": "Modern sofa",
                "semantic_decision": "ACCEPT",
                "semantic_score": 20,
                "license": "Pexels License",
                "status": "DOWNLOADED",
                "rejection_reason": None,
            }
        ],
    }
    out = tmp_path / "review.jpg"
    build_contact_sheet(manifest, tmp_path, out)
    assert out.exists()
    Image.open(out).verify()
