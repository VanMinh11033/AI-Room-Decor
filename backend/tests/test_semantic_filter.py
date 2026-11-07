from decimal import Decimal
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.models.entities import Category, Product, ProductStatus
from app.services.openverse_provider import OpenverseImageSourceProvider
from app.services.product_image_collector import CollectionService
from app.services.semantic_filter import derive_object_rule, semantic_assess


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


def assess(title, product_name, category, tags=()):
    product = FakeProduct(product_name, category)
    rule = derive_object_rule(product)
    return semantic_assess({"title": title, "tags": list(tags)}, rule)


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


# --- semantic_assess: required REJECT cases ---

def test_semantic_reject_sofa_without_sofa_evidence():
    result = assess("Vintage demitasse set for tea or Turkish coffees", "Japandi Low Sofa", "Sofa")
    assert result["semantic_decision"] == "REJECT"
    assert result["semantic_score"] == 0
    assert "no sofa/couch term" in result["semantic_reason"]


def test_semantic_reject_chair_illustration():
    result = assess("Liberty Bell - Illustration", "Scandinavian Lounge Chair", "Chair")
    assert result["semantic_decision"] == "REJECT"
    assert "illustration" in result["semantic_reason"]


def test_semantic_reject_floor_lamp_without_floor_evidence():
    result = assess("Modern Lighting", "Brass Floor Lamp", "Lighting")
    assert result["semantic_decision"] == "REJECT"
    assert "floor" in result["semantic_reason"]


def test_semantic_reject_rug_background_only():
    result = assess("Background", "Woven Jute Rug", "Rug", tags=["texture"])
    assert result["semantic_decision"] == "REJECT"
    assert "rug/carpet" in result["semantic_reason"]


# --- semantic_assess: required ACCEPT cases ---

def test_semantic_accept_sofa():
    result = assess("Japandi Low Sofa", "Japandi Low Sofa", "Sofa")
    assert result["semantic_decision"] == "ACCEPT"
    assert result["semantic_score"] > 0


def test_semantic_accept_chair():
    result = assess("Scandinavian Lounge Chair", "Scandinavian Lounge Chair", "Chair")
    assert result["semantic_decision"] == "ACCEPT"
    assert result["semantic_score"] > 0


def test_semantic_accept_floor_lamp():
    result = assess("Brass Floor Lamp", "Brass Floor Lamp", "Lighting")
    assert result["semantic_decision"] == "ACCEPT"
    assert result["semantic_score"] > 0


def test_semantic_accept_rug():
    result = assess("Woven Jute Rug", "Woven Jute Rug", "Rug")
    assert result["semantic_decision"] == "ACCEPT"
    assert result["semantic_score"] > 0


# --- provider search sets semantic_decision (mocked HTTP) ---

def openverse_item(oid, title, url, license_code="by", tags=()):
    return {
        "id": oid,
        "title": title,
        "foreign_landing_url": f"https://example.com/page/{oid}",
        "url": url,
        "creator": f"Creator {oid}",
        "creator_url": f"https://example.com/creator/{oid}",
        "license": license_code,
        "license_version": "4.0",
        "license_url": f"https://creativecommons.org/licenses/{license_code}/4.0/",
        "provider": "flickr",
        "source": "flickr",
        "filetype": "jpg",
        "tags": [{"name": t} for t in tags],
        "attribution": f"attribution {oid}",
        "width": 1024,
        "height": 768,
        "thumbnail": f"https://api.openverse.org/thumb/{oid}",
    }


def test_search_marks_semantic_reject():
    item = openverse_item("id-1", "Vintage demitasse set for tea or Turkish coffees", "https://img.example/a.jpg")
    handler = lambda request: httpx.Response(200, json={"results": [item]}, headers={"content-type": "application/json"})
    provider = OpenverseImageSourceProvider(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    product = FakeProduct("Japandi Low Sofa", "Sofa")
    candidates = provider.search(product)
    assert len(candidates) == 1
    assert candidates[0]["semantic_decision"] == "REJECT"


def test_search_marks_semantic_accept():
    item = openverse_item("id-1", "Japandi Low Sofa", "https://img.example/a.jpg", tags=["sofa"])
    handler = lambda request: httpx.Response(200, json={"results": [item]}, headers={"content-type": "application/json"})
    provider = OpenverseImageSourceProvider(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    product = FakeProduct("Japandi Low Sofa", "Sofa")
    candidates = provider.search(product)
    assert len(candidates) == 1
    assert candidates[0]["semantic_decision"] == "ACCEPT"


# --- collector: semantic REJECT is never downloaded ---

def test_collect_openverse_semantic_reject_not_downloaded(tmp_path, db_session):
    product = make_product(db_session)
    rejected = candidate(
        "r1",
        "https://img.example/r.jpg",
        semantic_decision="REJECT",
        semantic_score=0,
        semantic_reason="no sofa/couch term",
    )
    provider = FakeOpenverseProvider([rejected], downloads={})
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=3)

    records = service.list_candidates()
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "REJECTED"
    assert record["filename"] is None
    assert record["file_hash"] is None
    assert record["semantic_decision"] == "REJECT"
    assert record["semantic_reason"] == "no sofa/couch term"


def test_collect_openverse_semantic_accept_downloads(tmp_path, db_session):
    product = make_product(db_session)
    accepted = candidate(
        "a1",
        "https://img.example/a.jpg",
        semantic_decision="ACCEPT",
        semantic_score=20,
        semantic_reason="matched: sofa",
    )
    provider = FakeOpenverseProvider(
        [accepted],
        downloads={"https://img.example/a.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=1)
    service.validate_candidates()

    records = service.list_candidates()
    assert len(records) == 1
    record = records[0]
    assert record["status"] == "VALIDATED"
    assert record["filename"] is not None
    assert record["semantic_decision"] == "ACCEPT"
    assert record["semantic_score"] == 20
    assert record["semantic_reason"] == "matched: sofa"


def test_collect_openverse_persists_semantic_fields(tmp_path, db_session):
    product = make_product(db_session)
    rejected = candidate(
        "r1",
        "https://img.example/r.jpg",
        license_decision_value="LICENSE_REVIEW_REQUIRED",
        license="by-nc",
        semantic_decision="ACCEPT",
        semantic_score=12,
        semantic_reason="matched: sofa",
    )
    provider = FakeOpenverseProvider([rejected], downloads={})
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=3)

    record = service.list_candidates()[0]
    assert record["status"] == "LICENSE_REVIEW_REQUIRED"
    assert record["semantic_decision"] == "ACCEPT"
    assert record["semantic_score"] == 12
    assert record["semantic_reason"] == "matched: sofa"


def test_collect_openverse_license_rules_still_work(tmp_path, db_session):
    product = make_product(db_session)
    review = candidate(
        "r1",
        "https://img.example/r.jpg",
        license_decision_value="LICENSE_REVIEW_REQUIRED",
        license="by-nc",
        semantic_decision="ACCEPT",
        semantic_score=12,
        semantic_reason="matched: sofa",
    )
    accepted = candidate(
        "a1",
        "https://img.example/a.jpg",
        semantic_decision="ACCEPT",
        semantic_score=20,
        semantic_reason="matched: sofa",
    )
    provider = FakeOpenverseProvider(
        [review, accepted],
        downloads={"https://img.example/a.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=1)

    records = service.list_candidates()
    statuses = {r["status"] for r in records}
    assert "LICENSE_REVIEW_REQUIRED" in statuses
    assert "DOWNLOADED" in statuses


def test_collect_openverse_duplicate_detection_still_works(tmp_path, db_session):
    product = make_product(db_session)
    same_bytes = jpeg_bytes()
    first = candidate(
        "a1",
        "https://img.example/a.jpg",
        semantic_decision="ACCEPT",
        semantic_score=20,
        semantic_reason="matched: sofa",
    )
    second = candidate(
        "a2",
        "https://img.example/b.jpg",
        semantic_decision="ACCEPT",
        semantic_score=20,
        semantic_reason="matched: sofa",
    )
    provider = FakeOpenverseProvider(
        [first, second],
        downloads={
            "https://img.example/a.jpg": (same_bytes, "image/jpeg"),
            "https://img.example/b.jpg": (same_bytes, "image/jpeg"),
        },
    )
    service = CollectionService(db_session, staging_root=tmp_path, openverse_provider=provider)

    service.collect_openverse(product.id, max_downloads=2)

    records = service.list_candidates()
    assert len(records) == 2
    assert records[0]["status"] == "DOWNLOADED"
    assert records[1]["status"] == "REJECTED"
    assert records[1]["validation_reason"] == "duplicate image hash"
