import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.models.entities import Category, Product, ProductImage, ProductStatus
from app.services.product_reference_service import ProductReferencePreparationService
from app.services.reference_image_processing import (
    analyze_reference_image,
    cap_dimensions,
    estimate_background_color,
    remove_uniform_background,
)
from app.services.storage_service import ProductImageStorageService


def write_image(path, size=(200, 200), bg=(255, 255, 255), fg=(200, 50, 50), box=None):
    img = Image.new("RGB", size, bg)
    if box is None:
        box = (size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4)
    ImageDraw.Draw(img).rectangle(box, fill=fg)
    img.save(path)
    return path


def write_rgba_image(path, size=(200, 200), fg=(200, 50, 50, 255), box=None):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    if box is None:
        box = (size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4)
    ImageDraw.Draw(img).rectangle(box, fill=fg)
    img.save(path)
    return path


def write_non_uniform_image(path, size=(200, 200)):
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    w, h = size
    d.rectangle((0, 0, w // 2, h // 2), fill=(255, 0, 0))
    d.rectangle((w // 2, 0, w, h // 2), fill=(0, 255, 0))
    d.rectangle((0, h // 2, w // 2, h), fill=(0, 0, 255))
    d.rectangle((w // 2, h // 2, w, h), fill=(255, 255, 0))
    d.rectangle((w // 4, h // 4, 3 * w // 4, 3 * h // 4), fill=(120, 120, 120))
    img.save(path)
    return path


def make_category(db):
    category = Category(name="Sofa", slug="sofa", is_active=True)
    db.add(category)
    db.commit()
    return category


def make_product(db, category, images):
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
    db.flush()
    for image in images:
        db.add(ProductImage(product_id=product.id, **image))
    db.commit()
    return product


# --- path resolution ---

def test_resolve_flat_image_url(tmp_path):
    storage = ProductImageStorageService(storage_root=str(tmp_path))
    (tmp_path / "abc.jpg").write_bytes(b"x")
    assert storage.resolve("/storage/products/abc.jpg") == (tmp_path / "abc.jpg").resolve()


def test_resolve_generated_demo_subdirectory(tmp_path):
    storage = ProductImageStorageService(storage_root=str(tmp_path))
    (tmp_path / "generated-demo").mkdir()
    (tmp_path / "generated-demo" / "13-thing.png").write_bytes(b"x")
    assert storage.resolve("/storage/products/generated-demo/13-thing.png") == (tmp_path / "generated-demo" / "13-thing.png").resolve()


@pytest.mark.parametrize(
    "url",
    [
        "/storage/products/../../etc/passwd",
        "/storage/products/../secret.png",
        "/storage/products/a/../../b.png",
        "/storage/products/..",
    ],
)
def test_resolve_rejects_path_traversal(tmp_path, url):
    storage = ProductImageStorageService(storage_root=str(tmp_path))
    with pytest.raises(HTTPException):
        storage.resolve(url)


# --- analyzer ---

def test_analyze_rgba_already_transparent(tmp_path):
    path = write_rgba_image(tmp_path / "transparent.png")
    result = analyze_reference_image(path)
    assert result["decodable"] is True
    assert result["has_alpha"] is True
    assert result["has_transparency"] is True
    assert result["background_removal_candidate"] is True
    assert result["reason"] == "already transparent"


def test_analyze_uniform_white_background_candidate(tmp_path):
    path = write_image(tmp_path / "white.jpg", bg=(255, 255, 255), fg=(200, 50, 50))
    result = analyze_reference_image(path)
    assert result["decodable"] is True
    assert result["background_removal_candidate"] is True


def test_analyze_uniform_non_white_background_candidate(tmp_path):
    path = write_image(tmp_path / "green.jpg", bg=(0, 200, 0), fg=(200, 50, 50))
    result = analyze_reference_image(path)
    assert result["background_removal_candidate"] is True


def test_analyze_non_uniform_background_rejected(tmp_path):
    path = write_non_uniform_image(tmp_path / "lifestyle.jpg")
    result = analyze_reference_image(path)
    assert result["decodable"] is True
    assert result["background_removal_candidate"] is False
    assert result["reason"] == "non-uniform background"


def test_analyze_detects_mislabeled_format(tmp_path):
    path = write_image(tmp_path / "photo.jpg", bg=(255, 255, 255))
    path.replace(tmp_path / "photo.png")
    result = analyze_reference_image(tmp_path / "photo.png")
    assert result["detected_format"] == "JPEG"
    assert result["extension_matches_format"] is False


# --- background removal ---

def test_remove_uniform_background_produces_transparent_output(tmp_path):
    path = write_image(tmp_path / "white.jpg", bg=(255, 255, 255), fg=(200, 50, 50))
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
        bg = estimate_background_color(rgba)
        removed = remove_uniform_background(rgba, bg)
        alpha = removed.getchannel("A")
        assert alpha.getextrema()[0] == 0
        assert removed.getpixel((100, 100))[3] == 255


def test_cap_dimensions_preserves_aspect_ratio():
    image = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    capped = cap_dimensions(image, max_side=100)
    assert capped.size == (100, 50)


def test_cap_dimensions_does_not_upscale():
    image = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    capped = cap_dimensions(image, max_side=1024)
    assert capped.size == (50, 50)


# --- source selection / provenance / manifest ---

def test_source_selection_prefers_real_catalog(tmp_path, db_session):
    product_root = tmp_path / "products"
    reference_root = tmp_path / "references"
    product_root.mkdir(parents=True)
    storage = ProductImageStorageService(storage_root=str(product_root))
    write_rgba_image(product_root / "real.png")

    category = make_category(db_session)
    make_product(db_session, category, [{"image_url": "/storage/products/real.png", "is_primary": True, "sort_order": 0}])

    service = ProductReferencePreparationService(db_session, reference_root=reference_root, product_storage=storage)
    results = service.prepare_all()

    assert len(results) == 1
    assert results[0]["suitability_status"] == "PREPARED"
    assert results[0]["source_type"] == "REAL_CATALOG"
    assert (reference_root / "1.png").exists()


def test_source_selection_falls_back_to_generated_demo(tmp_path, db_session):
    product_root = tmp_path / "products"
    reference_root = tmp_path / "references"
    (product_root / "generated-demo").mkdir(parents=True)
    storage = ProductImageStorageService(storage_root=str(product_root))
    write_non_uniform_image(product_root / "real.jpg")
    write_image(product_root / "generated-demo" / "1-demo.png", bg=(255, 255, 255), fg=(100, 100, 200))

    category = make_category(db_session)
    make_product(
        db_session,
        category,
        [
            {"image_url": "/storage/products/real.jpg", "is_primary": True, "sort_order": 0},
            {"image_url": "/storage/products/generated-demo/1-demo.png", "is_primary": False, "sort_order": 1},
        ],
    )

    service = ProductReferencePreparationService(db_session, reference_root=reference_root, product_storage=storage)
    results = service.prepare_all()

    assert results[0]["suitability_status"] == "PREPARED"
    assert results[0]["source_type"] == "GENERATED_DEMO"
    assert "/generated-demo/" in results[0]["source_image_url"]


def test_unsuitable_product_reported_without_output(tmp_path, db_session):
    product_root = tmp_path / "products"
    reference_root = tmp_path / "references"
    product_root.mkdir(parents=True)
    storage = ProductImageStorageService(storage_root=str(product_root))
    write_non_uniform_image(product_root / "real.jpg")

    category = make_category(db_session)
    make_product(db_session, category, [{"image_url": "/storage/products/real.jpg", "is_primary": True, "sort_order": 0}])

    service = ProductReferencePreparationService(db_session, reference_root=reference_root, product_storage=storage)
    results = service.prepare_all()

    assert results[0]["suitability_status"] == "UNSUITABLE"
    assert results[0]["output_path"] is None
    assert not (reference_root / "1.png").exists()


def test_prepare_all_writes_manifest_and_preserves_originals(tmp_path, db_session):
    product_root = tmp_path / "products"
    reference_root = tmp_path / "references"
    (product_root / "generated-demo").mkdir(parents=True)
    storage = ProductImageStorageService(storage_root=str(product_root))
    demo_path = write_image(product_root / "generated-demo" / "1-demo.png", bg=(255, 255, 255), fg=(100, 100, 200))
    original_bytes = demo_path.read_bytes()

    category = make_category(db_session)
    make_product(db_session, category, [{"image_url": "/storage/products/generated-demo/1-demo.png", "is_primary": True, "sort_order": 0}])

    service = ProductReferencePreparationService(db_session, reference_root=reference_root, product_storage=storage)
    results = service.prepare_all()

    manifest = json.loads((reference_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_products"] == 1
    assert manifest["products"][0]["source_type"] == "GENERATED_DEMO"
    assert manifest["products"][0]["has_alpha"] is True
    assert demo_path.read_bytes() == original_bytes
    assert len(results) == 1
    assert (reference_root / "1.png").exists()
