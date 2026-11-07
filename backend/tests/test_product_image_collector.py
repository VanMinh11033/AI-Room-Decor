import json
from decimal import Decimal
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from app.models.entities import Category, Product, ProductImage, ProductStatus
from app.services.product_image_collector import (
    CollectionService,
    ManualUrlProvider,
    build_search_phrase,
    validate_image_bytes,
)


def jpeg_bytes(size=(400, 300), bg=(255, 255, 255), fg=(200, 50, 50)):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    d.rectangle((size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4), fill=fg)
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def png_rgb_bytes(size=(400, 300), bg=(255, 255, 255), fg=(100, 100, 200)):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    d.rectangle((size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4), fill=fg)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def png_transparent_bytes(size=(400, 300)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4), fill=(200, 50, 50, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def webp_bytes(size=(400, 300)):
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4), fill=(90, 160, 90))
    buf = BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def mock_provider(handler):
    return ManualUrlProvider(
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")
    )


def make_product(db):
    category = Category(name="Sofa", slug="sofa", is_active=True)
    db.add(category)
    db.commit()
    product = Product(
        category_id=category.id,
        name="Test Sofa",
        slug="test-sofa",
        price=Decimal("100"),
        stock_quantity=10,
        status=ProductStatus.ACTIVE,
        is_active=True,
    )
    db.add(product)
    db.commit()
    return product


# --- provider + validation (no DB) ---

def test_manual_url_provider_downloads_valid_jpeg():
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    data, content_type = provider.download("http://test/ok.jpg")
    assert data.startswith(b"\xff\xd8")
    assert content_type == "image/jpeg"


def test_validate_valid_jpeg():
    result = validate_image_bytes(jpeg_bytes(), "image/jpeg", "http://test/ok.jpg")
    assert result["status"] == "VALIDATED"
    assert result["detected_format"] == "JPEG"
    assert result["extension_matches_format"] is True


def test_validate_valid_png():
    result = validate_image_bytes(png_rgb_bytes(), "image/png", "http://test/ok.png")
    assert result["status"] == "VALIDATED"
    assert result["detected_format"] == "PNG"


def test_validate_transparent_png():
    result = validate_image_bytes(png_transparent_bytes(), "image/png", "http://test/ok.png")
    assert result["status"] == "VALIDATED"


def test_validate_html_rejected():
    result = validate_image_bytes(b"<html>not an image</html>", "text/html", "http://test/page")
    assert result["status"] == "REJECTED"
    assert result["reason"] == "non-image content-type"


def test_validate_corrupt_image_rejected():
    result = validate_image_bytes(b"not a real image at all", "image/jpeg", "http://test/ok.jpg")
    assert result["status"] == "REJECTED"
    assert "undecodable" in result["reason"] or "corrupt" in result["reason"]


def test_validate_tiny_image_rejected():
    result = validate_image_bytes(jpeg_bytes(size=(50, 50)), "image/jpeg", "http://test/tiny.jpg")
    assert result["status"] == "REJECTED"
    assert "too small" in result["reason"]


def test_validate_format_mismatch_flagged():
    result = validate_image_bytes(webp_bytes(), "image/webp", "http://test/photo.jpg")
    assert result["status"] == "VALIDATED"
    assert result["detected_format"] == "WEBP"
    assert result["extension_matches_format"] is False


# --- service flow (DB + mocked HTTP) ---

def test_add_manual_candidate_stores_provenance(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    record = service.add_manual_candidate(product.id, "http://test/ok.jpg", source_name="manual", source_page_url="http://test/page")

    assert record["status"] == "DOWNLOADED"
    assert record["product_id"] == product.id
    assert record["product_name"] == "Test Sofa"
    assert record["source_name"] == "manual"
    assert record["source_page_url"] == "http://test/page"
    assert record["direct_image_url"] == "http://test/ok.jpg"
    assert record["file_hash"]
    assert (tmp_path / str(product.id) / record["filename"]).exists()


def test_duplicate_hash_rejected(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg")
    duplicate = service.add_manual_candidate(product.id, "http://test/ok.jpg")

    assert duplicate["status"] == "REJECTED"
    assert duplicate["validation_reason"] == "duplicate image hash"


def test_validate_then_preprocess_flow(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg")
    service.validate_candidates()
    candidates = service.preprocess_candidates()

    assert candidates[0]["status"] == "SUITABLE"
    assert candidates[0]["processed_path"] == f"{product.id}/candidate-001.clean.png"
    assert (tmp_path / str(product.id) / "candidate-001.clean.png").exists()
    clean = Image.open(tmp_path / str(product.id) / "candidate-001.clean.png")
    assert "A" in clean.getbands()


def test_approve_workflow(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg")
    service.validate_candidates()
    service.preprocess_candidates()
    record = service.approve_candidate(f"{product.id}/candidate-001.jpg")

    assert record["status"] == "APPROVED"


def test_collector_does_not_modify_product_image_db(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg")
    service.validate_candidates()
    service.preprocess_candidates()

    assert db_session.query(ProductImage).count() == 0


def test_collector_does_not_overwrite_reference(tmp_path, db_session):
    reference_root = tmp_path / "product-references"
    reference_root.mkdir()
    reference_file = reference_root / "1.png"
    reference_file.write_bytes(b"existing phase10a reference")

    staging_root = tmp_path / "product-collected"
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=staging_root, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg")
    service.validate_candidates()
    service.preprocess_candidates()

    assert reference_file.read_bytes() == b"existing phase10a reference"
    assert (staging_root / str(product.id) / "candidate-001.clean.png").exists()


def test_manifest_provenance_and_storage_isolation(tmp_path, db_session):
    product = make_product(db_session)
    provider = mock_provider(lambda request: httpx.Response(200, content=jpeg_bytes(), headers={"content-type": "image/jpeg"}))
    service = CollectionService(db_session, staging_root=tmp_path, provider=provider)

    service.add_manual_candidate(product.id, "http://test/ok.jpg", source_name="manual", source_page_url="http://test/page")
    service.validate_candidates()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["staging_directory"] == str(tmp_path)
    entry = manifest["candidates"][0]
    assert entry["source_name"] == "manual"
    assert entry["source_page_url"] == "http://test/page"
    assert entry["status"] == "VALIDATED"
    assert entry["detected_format"] == "JPEG"


def test_build_search_phrase_includes_metadata():
    category = Category(name="Sofa", slug="sofa", is_active=True)
    product = Product(category_id=1, name="Japandi Low Sofa", slug="japandi-low-sofa", price=Decimal("100"), stock_quantity=1, status=ProductStatus.ACTIVE, is_active=True)
    product.category = category
    product.styles = []
    product.colors = []
    product.materials = []
    phrase = build_search_phrase(product)
    assert phrase.startswith("Japandi Low Sofa")
    assert "isolated product" in phrase
    assert "white background" in phrase
