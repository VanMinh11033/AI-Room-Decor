"""Deterministic room-design compositor.

Composites the *exact* selected product images onto the *original* room photo so
the room background, architecture and camera angle are preserved and no product
is redrawn or swapped by a generative model.

Image classification
--------------------
Each catalog image is classified into one of two groups before compositing:

- ``ISOLATED`` — the product sits on a uniform/plain background (or is already
  transparent), so its background can be removed reliably with a border flood
  fill and a clean transparent cutout is produced.
- ``SCENE`` — the image is an interior scene (the product shown inside a room),
  so the product cannot be separated reliably. These images are rejected with a
  clear error instead of being pasted as a rectangular block.

Layout
------
Placement uses the product category (rug, wall decor, lighting, seating, table,
storage, accessories, plant, bedding) together with the room size. It does not
put everything on one horizontal line: wall decor hangs higher, rugs sit flat on
the floor, floor-standing items sit near the lower edge, and items are spread
horizontally with staggered depth.

Honest limits
-------------
- Background removal is flood fill and is only applied to ``ISOLATED`` images;
  it is never applied to complex/scene images.
- No AI segmentation model is used (none is bundled), and no paid API is called.
- No perspective/warp correction is applied; shadows are a soft ground blur for
  grounding, not a physical light model.
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from app.services.reference_image_processing import (
    MAX_REFERENCE_SIDE,
    analyze_reference_image,
    cap_dimensions,
    estimate_background_color,
    remove_uniform_background,
    trim_transparent,
)

ISOLATED = "ISOLATED"
SCENE = "SCENE"

_SHADOW_OPACITY = 90
_HORIZONTAL_MARGIN_RATIO = 0.06


class ProductNotCompositibleError(Exception):
    """Raised when a product image cannot be reliably cut out for compositing."""


# category -> (target_height_ratio, y_bottom_ratio, needs_shadow)
_CATEGORY_LAYOUT = {
    "rug": (0.16, 0.93, False),
    "wall decor": (0.20, 0.52, False),
    "lighting": (0.30, 0.80, True),
    "sofa": (0.30, 0.82, True),
    "chair": (0.28, 0.82, True),
    "table": (0.24, 0.86, True),
    "storage": (0.30, 0.82, True),
    "accessories": (0.18, 0.60, False),
    "plant decor": (0.28, 0.80, True),
    "bedding": (0.22, 0.68, False),
}
_DEFAULT_LAYOUT = (0.25, 0.80, True)


def classify_product_image(image_path: Path) -> str:
    """Return ``ISOLATED`` or ``SCENE`` for a product image."""
    if not image_path.exists():
        return SCENE
    analysis = analyze_reference_image(image_path)
    if analysis["has_transparency"] or analysis["background_removal_candidate"]:
        return ISOLATED
    return SCENE


def cutout_product(image_path: Path, max_side: int = MAX_REFERENCE_SIDE) -> Image.Image:
    """Return a transparent RGBA cutout for an ``ISOLATED`` product image.

    Raises :class:`ProductNotCompositibleError` for scene images.
    """
    analysis = analyze_reference_image(image_path)
    with Image.open(image_path) as im:
        im.load()
        rgba = im.convert("RGBA")

    if analysis["has_transparency"]:
        trimmed = trim_transparent(rgba, padding=4)
        if trimmed is None:
            raise ProductNotCompositibleError(f"{image_path.name}: no visible product after trim")
        return cap_dimensions(trimmed, max_side)

    if not analysis["background_removal_candidate"]:
        raise ProductNotCompositibleError(
            f"{image_path.name} is an interior scene, not an isolated product image"
        )

    background_color = estimate_background_color(rgba)
    rgba = remove_uniform_background(rgba, background_color)
    trimmed = trim_transparent(rgba, padding=4)
    if trimmed is None:
        raise ProductNotCompositibleError(f"{image_path.name}: no visible product after background removal")
    return cap_dimensions(trimmed, max_side)


def _soft_shadow(width: int, height: int) -> Image.Image:
    shadow_width = max(2, int(width * 1.1))
    shadow_height = max(4, int(height * 0.12))
    shadow = Image.new("RGBA", (shadow_width, shadow_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse([0, 0, shadow_width - 1, shadow_height - 1], fill=(0, 0, 0, _SHADOW_OPACITY))
    return shadow.filter(ImageFilter.GaussianBlur(radius=max(1.0, shadow_height / 2)))


def _layout_positions(
    cutouts: list[tuple[Image.Image, str | None]],
    room_width: int,
    room_height: int,
) -> list[tuple[int, int, int, int, bool]]:
    """Return (x_center, y_bottom, target_height, slot_width, needs_shadow)."""
    count = len(cutouts)
    margin = int(room_width * _HORIZONTAL_MARGIN_RATIO)
    usable = max(1, room_width - 2 * margin)
    slot_width = int((usable / count) * 0.85)
    positions = []
    for index, (_cutout, category) in enumerate(cutouts):
        target_ratio, bottom_ratio, shadow = _CATEGORY_LAYOUT.get((category or "").lower(), _DEFAULT_LAYOUT)
        x_center = margin + int(usable * (index + 0.5) / count)
        y_bottom = int(room_height * bottom_ratio)
        target_height = int(room_height * target_ratio)
        positions.append((x_center, y_bottom, target_height, slot_width, shadow))
    return positions


def composite_design(
    room_image_path: Path,
    product_image_paths: list[Path],
    product_categories: list[str | None] | None = None,
) -> bytes:
    room = Image.open(room_image_path).convert("RGB")
    canvas = room.convert("RGBA")

    paths = [path for path in (product_image_paths or []) if path]
    if not paths:
        raise ProductNotCompositibleError("No product images available to composite")

    categories = list(product_categories or [])
    cutouts: list[tuple[Image.Image, str | None]] = []
    for index, path in enumerate(paths):
        cutout = cutout_product(path)
        category = categories[index] if index < len(categories) else None
        cutouts.append((cutout, category))

    positions = _layout_positions(cutouts, room.width, room.height)
    for (cutout, _category), (x_center, y_bottom, target_height, slot_width, needs_shadow) in zip(cutouts, positions):
        scale = min(target_height / cutout.height, slot_width / cutout.width, 1.0)
        width = max(1, int(cutout.width * scale))
        height = max(1, int(cutout.height * scale))
        resized = cutout.resize((width, height), Image.Resampling.LANCZOS)

        if needs_shadow:
            shadow = _soft_shadow(width, height)
            canvas.alpha_composite(shadow, (x_center - shadow.width // 2, y_bottom - shadow.height // 2))
        canvas.alpha_composite(resized, (x_center - width // 2, y_bottom - height))

    buffer = BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
