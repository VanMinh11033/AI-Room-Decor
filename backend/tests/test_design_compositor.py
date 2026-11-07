"""Unit tests for the deterministic room-design compositor (no network/API)."""

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.ai.image.base import ImageProviderError
from app.ai.image.composite_provider import CompositeImageProvider
from app.services.design_compositor import (
    ISOLATED,
    SCENE,
    ProductNotCompositibleError,
    classify_product_image,
    composite_design,
    cutout_product,
)


def make_white_product(tmp_path, name="product.png", size=(200, 200), box=(60, 60, 140, 140)):
    image = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle(box, fill=(200, 30, 30))
    path = tmp_path / name
    image.save(path, format="PNG")
    return path


def make_scene_image(tmp_path, name="scene.png", size=(200, 200)):
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 200, 110], fill=(200, 180, 160))  # wall
    draw.rectangle([0, 110, 200, 200], fill=(120, 90, 70))  # floor
    draw.rectangle([60, 60, 140, 140], fill=(30, 60, 30))  # dark object
    path = tmp_path / name
    image.save(path, format="PNG")
    return path


def test_classify_product_image_detects_isolated_and_scene(tmp_path):
    assert classify_product_image(make_white_product(tmp_path, "isolated.png")) == ISOLATED
    assert classify_product_image(make_scene_image(tmp_path, "scene.png")) == SCENE


def test_cutout_product_removes_uniform_background(tmp_path):
    cutout = cutout_product(make_white_product(tmp_path))

    assert cutout.mode == "RGBA"
    bbox = cutout.getchannel("A").getbbox()
    assert bbox is not None
    # White background removed: the opaque region is smaller than the full frame.
    assert (bbox[2] - bbox[0]) < cutout.width
    assert (bbox[3] - bbox[1]) < cutout.height


def test_cutout_product_rejects_scene_image(tmp_path):
    with pytest.raises(ProductNotCompositibleError):
        cutout_product(make_scene_image(tmp_path))


def test_composite_design_returns_png_and_preserves_room_size(tmp_path):
    room = Image.new("RGB", (400, 300), (240, 235, 225))
    room_path = tmp_path / "room.jpg"
    room.save(room_path, format="JPEG")

    data = composite_design(room_path, [make_white_product(tmp_path)])

    assert data.startswith(b"\x89PNG")
    assert Image.open(BytesIO(data)).size == (400, 300)


def test_composite_design_rejects_scene_image(tmp_path):
    room = Image.new("RGB", (400, 300), (240, 235, 225))
    room_path = tmp_path / "room.jpg"
    room.save(room_path, format="JPEG")

    with pytest.raises(ProductNotCompositibleError):
        composite_design(room_path, [make_scene_image(tmp_path)])


def test_composite_design_with_no_products_raises(tmp_path):
    room = Image.new("RGB", (300, 200), (10, 20, 30))
    room_path = tmp_path / "room.png"
    room.save(room_path, format="PNG")

    with pytest.raises(ProductNotCompositibleError):
        composite_design(room_path, [])


def test_composite_provider_generates_png(tmp_path):
    room = Image.new("RGB", (400, 300), (200, 200, 200))
    room_path = tmp_path / "room.png"
    room.save(room_path, format="PNG")

    provider = CompositeImageProvider()
    result = provider.generate_design(room_path, "prompt", [make_white_product(tmp_path)], ["wall decor"])

    assert result.content_type == "image/png"
    assert result.data.startswith(b"\x89PNG")
    assert provider.MAX_INPUT_IMAGES == 5


def test_composite_provider_raises_for_scene(tmp_path):
    room = Image.new("RGB", (400, 300), (200, 200, 200))
    room_path = tmp_path / "room.png"
    room.save(room_path, format="PNG")

    provider = CompositeImageProvider()
    with pytest.raises(ImageProviderError) as exc_info:
        provider.generate_design(room_path, "prompt", [make_scene_image(tmp_path)])

    assert exc_info.value.code == "PRODUCT_IMAGE_NOT_COMPOSITIBLE"
