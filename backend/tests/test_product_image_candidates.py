"""Offline unit tests for the admin product-image candidate review flow.

Openverse search and downloads are faked; DNS is faked via an injected resolver,
so no network or external API is touched.
"""

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from app.api.routes.product_image_candidates import _serialize
from app.core.config import settings
from app.models.entities import Category, Product, ProductImage, ProductImageCandidate, ProductStatus
from app.services.product_image_candidate_service import (
    PROJECT_ROOT,
    ProductImageCandidateService,
    _public_url,
)
from app.services.stock_image_providers import OpenverseProvider


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


def jpeg_bytes(size=(600, 600), color=(255, 255, 255)):
    img = Image.new("RGB", size, color)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class FakeOpenverseProvider:
    def __init__(self, candidates, downloads):
        self.candidates = candidates
        self.downloads = downloads

    def search(self, product, queries):
        return self.candidates

    def download(self, url):
        if url not in self.downloads:
            raise ValueError("no download")
        return self.downloads[url]


def make_candidate(url="https://example.com/sofa.jpg"):
    return {
        "direct_image_url": url,
        "semantic_decision": "ACCEPT",
        "license_decision": "ACCEPTED",
        "license": "by",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "by Tester",
        "creator": "Tester",
        "source": "flickr",
        "source_page": "https://flickr.com/sofa",
        "title": "Modern sofa",
        "tags": ["sofa"],
    }


def test_search_and_stage_creates_pending_candidate(tmp_path, db_session):
    product = make_product(db_session)
    provider = FakeOpenverseProvider(
        [make_candidate()],
        {"https://example.com/sofa.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = ProductImageCandidateService(db_session, staging_root=tmp_path, provider=provider, min_side=400)

    result = service.search_and_stage(product.id, max_images=3)

    assert result == {"product_id": product.id, "staged": 1, "skipped": 0}
    rows = db_session.query(ProductImageCandidate).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "PENDING"
    assert row.product_id == product.id
    assert row.license == "by"
    assert row.creator == "Tester"
    assert row.local_path.endswith("candidate-001.jpg")
    assert (tmp_path / str(product.id) / "candidate-001.jpg").exists()


def test_search_and_stage_dedups_by_url(tmp_path, db_session):
    product = make_product(db_session)
    provider = FakeOpenverseProvider(
        [make_candidate()],
        {"https://example.com/sofa.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = ProductImageCandidateService(db_session, staging_root=tmp_path, provider=provider, min_side=400)

    first = service.search_and_stage(product.id, max_images=3)
    second = service.search_and_stage(product.id, max_images=3)

    assert first["staged"] == 1
    assert second["staged"] == 0
    assert second["skipped"] == 1
    assert db_session.query(ProductImageCandidate).count() == 1


def test_approve_candidate_creates_product_image(tmp_path, db_session):
    product = make_product(db_session)
    provider = FakeOpenverseProvider(
        [make_candidate()],
        {"https://example.com/sofa.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = ProductImageCandidateService(db_session, staging_root=tmp_path, provider=provider, min_side=400)
    service.search_and_stage(product.id, max_images=3)

    candidate = db_session.query(ProductImageCandidate).one()
    approved = service.approve_candidate(candidate.id)

    assert approved.status == "APPROVED"
    images = db_session.query(ProductImage).filter(ProductImage.product_id == product.id).all()
    assert len(images) == 1
    assert images[0].image_url == f"/storage/products/candidate-staging/{product.id}/candidate-001.jpg"
    assert images[0].is_primary is True


def test_reject_candidate_does_not_create_product_image(tmp_path, db_session):
    product = make_product(db_session)
    provider = FakeOpenverseProvider(
        [make_candidate()],
        {"https://example.com/sofa.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = ProductImageCandidateService(db_session, staging_root=tmp_path, provider=provider, min_side=400)
    service.search_and_stage(product.id, max_images=3)

    candidate = db_session.query(ProductImageCandidate).one()
    rejected = service.reject_candidate(candidate.id)

    assert rejected.status == "REJECTED"
    assert db_session.query(ProductImage).count() == 0


def test_openverse_download_rejects_private_ip():
    provider = OpenverseProvider(
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x"))
        ),
        resolve_host=lambda host: ["127.0.0.1"],
        sleep_func=lambda seconds: None,
    )
    with pytest.raises(ValueError, match="unsafe address"):
        provider.download("https://example.com/a.jpg")


def test_public_url_local_mode_when_file_exists(monkeypatch, tmp_path):
    # When file exists locally, it returns the local /storage/... path
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test_cloud")
    test_file = PROJECT_ROOT / "storage" / "products" / "test-exists.jpg"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_bytes(b"dummy")
    try:
        url = _public_url("products/test-exists.jpg")
        assert url == "/storage/products/test-exists.jpg"
    finally:
        if test_file.exists():
            test_file.unlink()


def test_public_url_cloudinary_fallback_when_file_missing(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test_cloud_name")
    monkeypatch.setattr(settings, "cloudinary_folder", "ai_room_decor")
    missing_rel = "products/candidate-staging/999/candidate-missing.jpg"
    url = _public_url(missing_rel)
    assert url == "https://res.cloudinary.com/test_cloud_name/image/upload/ai_room_decor/products/candidate-staging/999/candidate-missing.jpg"


def test_public_url_empty_and_http_passthrough(monkeypatch):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test_cloud_name")
    assert _public_url("") == ""
    assert _public_url(None) == ""
    assert _public_url("https://res.cloudinary.com/demo/image.jpg") == "https://res.cloudinary.com/demo/image.jpg"
    assert _public_url("http://example.com/img.png") == "http://example.com/img.png"


def test_serialize_candidate_uses_cloudinary_fallback(monkeypatch, db_session):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test_cloud_name")
    monkeypatch.setattr(settings, "cloudinary_folder", "ai_room_decor")
    product = make_product(db_session)
    candidate = ProductImageCandidate(
        product_id=product.id,
        source="google",
        image_url="https://example.com/candidate.jpg",
        local_path="products/candidate-staging/9999/candidate-serialized.jpg",
        status="PENDING",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    serialized = _serialize(candidate)
    assert serialized.public_url == "https://res.cloudinary.com/test_cloud_name/image/upload/ai_room_decor/products/candidate-staging/9999/candidate-serialized.jpg"


def test_approve_candidate_with_cloudinary_fallback(monkeypatch, tmp_path, db_session):
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test_cloud_name")
    monkeypatch.setattr(settings, "cloudinary_folder", "ai_room_decor")

    product = make_product(db_session)
    provider = FakeOpenverseProvider(
        [make_candidate()],
        {"https://example.com/sofa.jpg": (jpeg_bytes(), "image/jpeg")},
    )
    service = ProductImageCandidateService(db_session, staging_root=tmp_path, provider=provider, min_side=400)
    service.search_and_stage(product.id, max_images=3)

    candidate = db_session.query(ProductImageCandidate).one()
    # Point candidate to a path that does NOT exist in PROJECT_ROOT/storage to simulate container
    candidate.local_path = "products/candidate-staging/9999/candidate-cloud.jpg"
    db_session.commit()

    approved = service.approve_candidate(candidate.id)

    assert approved.status == "APPROVED"
    # candidate.local_path must remain intact
    assert approved.local_path == "products/candidate-staging/9999/candidate-cloud.jpg"

    # ProductImage gets the Cloudinary HTTPS URL
    images = db_session.query(ProductImage).filter(ProductImage.product_id == product.id).all()
    assert len(images) == 1
    expected_url = "https://res.cloudinary.com/test_cloud_name/image/upload/ai_room_decor/products/candidate-staging/9999/candidate-cloud.jpg"
    assert images[0].image_url == expected_url
