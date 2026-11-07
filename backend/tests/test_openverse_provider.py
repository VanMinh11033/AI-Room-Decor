from decimal import Decimal
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.models.entities import Category, Product, ProductStatus
from app.services.openverse_provider import (
    OpenverseImageSourceProvider,
    build_openverse_queries,
    license_decision,
    rank_openverse_candidates,
)
from app.services.product_image_collector import CollectionService


class FakeCategory:
    def __init__(self, name):
        self.name = name


class FakeNamed:
    def __init__(self, name):
        self.name = name


class FakeProduct:
    def __init__(self, name, category, styles=(), colors=(), materials=()):
        self.name = name
        self.category = FakeCategory(category)
        self.styles = [FakeNamed(s) for s in styles]
        self.colors = [FakeNamed(c) for c in colors]
        self.materials = [FakeNamed(m) for m in materials]


def openverse_item(oid, title, url, license_code, license_version="4.0", source="flickr", tags=(), width=1024, height=768):
    return {
        "id": oid,
        "title": title,
        "foreign_landing_url": f"https://example.com/page/{oid}",
        "url": url,
        "creator": f"Creator {oid}",
        "creator_url": f"https://example.com/creator/{oid}",
        "license": license_code,
        "license_version": license_version,
        "license_url": f"https://creativecommons.org/licenses/{license_code}/{license_version}/",
        "provider": source,
        "source": source,
        "filetype": "jpg",
        "tags": [{"name": t} for t in tags],
        "attribution": f"attribution {oid}",
        "width": width,
        "height": height,
        "thumbnail": f"https://api.openverse.org/thumb/{oid}",
    }


def provider_with_handler(handler):
    return OpenverseImageSourceProvider(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )


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


def jpeg_bytes(size=(400, 300)):
    img = Image.new("RGB", size, (255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- query generation / license / ranking (pure) ---

def test_build_openverse_queries():
    product = FakeProduct("Japandi Low Sofa", "Sofa", styles=["Japandi"], colors=["Oak"], materials=["Wood"])
    queries = build_openverse_queries(product)
    assert queries[0] == "Japandi Low Sofa"
    assert "Japandi Sofa" in queries
    assert "Oak Sofa" in queries
    assert "Wood Sofa" in queries
    assert "Oak Sofa isolated" in queries


def test_license_decision_preferred():
    for code in ("cc0", "pdm", "by", "by-sa"):
        assert license_decision(code) == "ACCEPTED"


def test_license_decision_non_preferred_and_missing():
    assert license_decision("by-nc") == "LICENSE_REVIEW_REQUIRED"
    assert license_decision("by-nd") == "LICENSE_REVIEW_REQUIRED"
    assert license_decision(None) == "LICENSE_REVIEW_REQUIRED"
    assert license_decision("") == "LICENSE_REVIEW_REQUIRED"


def test_rank_openverse_candidates_prefers_license_and_resolution():
    candidates = [
        {"openverse_id": "a", "title": "", "tags": [], "license_decision": "ACCEPTED", "width": 100, "height": 100},
        {"openverse_id": "b", "title": "", "tags": [], "license_decision": "LICENSE_REVIEW_REQUIRED", "width": 2000, "height": 2000},
        {"openverse_id": "c", "title": "", "tags": [], "license_decision": "ACCEPTED", "width": 2000, "height": 2000},
    ]
    ranked = rank_openverse_candidates(candidates, ["sofa"])
    assert ranked[0]["openverse_id"] == "c"
    assert ranked[-1]["openverse_id"] == "b"


# --- provider search / download (mocked HTTP) ---

def test_search_returns_provenance_candidates():
    item = openverse_item("id-1", "Japandi sofa", "https://img.example/sofa.jpg", "by", tags=["sofa", "japandi"])
    handler = lambda request: httpx.Response(200, json={"results": [item]}, headers={"content-type": "application/json"})
    provider = provider_with_handler(handler)

    product = FakeProduct("Japandi Low Sofa", "Sofa", styles=["Japandi"], colors=["Oak"], materials=["Wood"])
    candidates = provider.search(product)

    assert len(candidates) == 1
    c = candidates[0]
    assert c["openverse_id"] == "id-1"
    assert c["direct_image_url"] == "https://img.example/sofa.jpg"
    assert c["source_page"] == "https://example.com/page/id-1"
    assert c["license"] == "by"
    assert c["license_decision"] == "ACCEPTED"
    assert c["creator"] == "Creator id-1"
    assert c["attribution"]


def test_search_deduplicates_by_id_and_url():
    item1 = openverse_item("id-1", "sofa", "https://img.example/a.jpg", "by")
    item2 = openverse_item("id-2", "sofa", "https://img.example/b.jpg", "cc0")
    duplicate = openverse_item("id-1", "sofa", "https://img.example/a.jpg", "by")

    def handler(request):
        q = request.url.params.get("q", "")
        results = {"q1": [item1, item2], "q2": [duplicate, item2]}[q]
        return httpx.Response(200, json={"results": results}, headers={"content-type": "application/json"})

    provider = provider_with_handler(handler)
    product = FakeProduct("Sofa", "Sofa")
    candidates = provider.search(product, queries=["q1", "q2"])

    ids = {c["openverse_id"] for c in candidates}
    assert ids == {"id-1", "id-2"}
    assert len(candidates) == 2


def test_search_raises_on_api_failure():
    handler = lambda request: httpx.Response(500, json={"detail": "boom"})
    provider = provider_with_handler(handler)
    with pytest.raises(httpx.HTTPStatusError):
        provider.search(FakeProduct("Sofa", "Sofa"))


def test_search_raises_on_429():
    handler = lambda request: httpx.Response(429, json={"detail": "rate limited"})
    provider = provider_with_handler(handler)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        provider.search(FakeProduct("Sofa", "Sofa"))
    assert exc_info.value.response.status_code == 429


def test_download_returns_bytes_and_content_type():
    handler = lambda request: httpx.Response(200, content=b"\xff\xd8fake", headers={"content-type": "image/jpeg"})
    provider = provider_with_handler(handler)
    data, content_type = provider.download("https://img.example/a.jpg")
    assert data == b"\xff\xd8fake"
    assert content_type == "image/jpeg"


def test_download_raises_on_404():
    handler = lambda request: httpx.Response(404, content=b"not found")
    provider = provider_with_handler(handler)
    with pytest.raises(httpx.HTTPStatusError):
        provider.download("https://img.example/missing.jpg")


# --- collector integration (fake openverse provider + real DB) ---

class FakeOpenverseProvider:
    name = "openverse"

    def __init__(self, candidates, downloads=None):
        self.candidates = candidates
        self.downloads = downloads or {}

    def search(self, product):
        return self.candidates

    def download(self, url):
        if url not in self.downloads:
            raise ValueError("no download")
        return self.downloads[url]


def candidate(oid, url, license_decision_value="ACCEPTED", **extra):
    base = {
        "openverse_id": oid,
        "direct_image_url": url,
        "license_decision": license_decision_value,
        "query": "sofa",
        "title": f"title {oid}",
        "creator": f"creator {oid}",
        "creator_url": f"https://example.com/creator/{oid}",
        "source": "flickr",
        "source_page": f"https://example.com/page/{oid}",
        "license": "by",
        "license_version": "4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": f"attribution {oid}",
        "thumbnail_url": f"https://thumb/{oid}",
        "filetype": "jpg",
        "rank_score": 10,
        "width": 1024,
        "height": 768,
    }
    base.update(extra)
    return base


def test_collect_openverse_records_review_and_downloads(tmp_path, db_session):
    product = make_product(db_session)
    accepted = candidate("a1", "https://img.example/a.jpg")
    review = candidate("r1", "https://img.example/r.jpg", license_decision_value="LICENSE_REVIEW_REQUIRED", license="by-nc")
    provider = FakeOpenverseProvider(
        [review, accepted],
        downloads={"https://img.example/a.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=1)
    service.validate_candidates()

    records = service.list_candidates()
    statuses = {r["status"] for r in records}
    assert "LICENSE_REVIEW_REQUIRED" in statuses
    assert "VALIDATED" in statuses


def test_collect_openverse_retains_provenance(tmp_path, db_session):
    product = make_product(db_session)
    accepted = candidate("a1", "https://img.example/a.jpg", license="by", attribution="(c) someone")
    provider = FakeOpenverseProvider([accepted], downloads={"https://img.example/a.jpg": (jpeg_bytes(), "image/jpeg")})
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=1)
    record = service.list_candidates()[0]

    assert record["openverse_id"] == "a1"
    assert record["source_page_url"] == "https://example.com/page/a1"
    assert record["source_name"] == "openverse"
    assert record["license"] == "by"
    assert record["attribution"] == "(c) someone"


def test_collect_openverse_invalid_image_download_rejected(tmp_path, db_session):
    product = make_product(db_session)
    accepted = candidate("a1", "https://img.example/notimage.jpg")
    provider = FakeOpenverseProvider([accepted], downloads={"https://img.example/notimage.jpg": (b"<html>not image</html>", "text/html")})
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=1)
    service.validate_candidates()

    record = service.list_candidates()[0]
    assert record["status"] == "REJECTED"
    assert record["validation_reason"] == "non-image content-type"
