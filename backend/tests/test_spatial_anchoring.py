import pytest
from unittest.mock import MagicMock

from app.ai.image.prompt_builder import (
    MAX_SAFE_PROMPT_CHARS,
    PROMPT_VERSION,
    _resolve_window_state,
    build_design_generation_prompt,
    extract_spatial_anchors,
)


class DummyCategory:
    def __init__(self, name: str, slug: str):
        self.name = name
        self.slug = slug


class DummyAttribute:
    def __init__(self, name: str):
        self.name = name


class DummyProduct:
    def __init__(
        self,
        id: int,
        name: str,
        category_name: str,
        category_slug: str,
        price: float = 1000000.0,
        width: float | None = 80.0,
        height: float | None = 70.0,
        depth: float | None = 60.0,
        materials: list[str] | None = None,
        styles: list[str] | None = None,
        colors: list[str] | None = None,
    ):
        self.id = id
        self.name = name
        self.category = DummyCategory(category_name, category_slug)
        self.price = price
        self.width = width
        self.height = height
        self.depth = depth
        self.materials = [DummyAttribute(m) for m in (materials or ["Wood"])]
        self.styles = [DummyAttribute(s) for s in (styles or ["Modern"])]
        self.colors = [DummyAttribute(c) for c in (colors or ["Cream"])]
        self.images = []


def make_dummy_project(title: str = "Test Room"):
    proj = MagicMock()
    proj.title = title
    proj.room_type = "empty_room"
    proj.room_image_path = "1/1/source.jpg"
    return proj


def make_dummy_preference():
    pref = MagicMock()
    pref.budget_min = 5000000
    pref.budget_max = 10000000
    pref.purpose = "Living"
    pref.styles = [DummyAttribute("Japandi")]
    pref.colors = [DummyAttribute("Beige"), DummyAttribute("White")]
    pref.materials = [DummyAttribute("Wood"), DummyAttribute("Linen")]
    pref.categories = [DummyCategory("Sofa", "sofa"), DummyCategory("Table", "table")]
    pref.notes = "Simple clean aesthetic"
    return pref


class MockAnalysis:
    def __init__(
        self,
        layout_summary: str | None = None,
        empty_areas: list | None = None,
        existing_objects: list | None = None,
        lighting: dict | None = None,
        provider: str = "gemini",
        room_type: str = "empty_room",
    ):
        self.layout_summary = layout_summary
        self.empty_areas = empty_areas
        self.existing_objects = existing_objects
        self.lighting = lighting or {"type": "natural light", "level": "bright"}
        self.provider = provider
        self.room_type = room_type


# 1. Window on the right (Project #21 real pattern)
def test_spatial_anchor_window_on_right():
    analysis = MockAnalysis(
        layout_summary=(
            "An empty room featuring light wood flooring, white painted walls with crown molding, "
            "and a large window on the right side providing ample bright natural light."
        ),
        empty_areas=[
            {"location": "center floor", "description": "Large open area with light wood flooring"},
            {"location": "back wall", "description": "Blank white accent or main wall"},
            {"location": "left wall", "description": "Blank white side wall"},
        ],
        existing_objects=[{"name": "window", "confidence": 0.98}, {"name": "hardwood floor", "confidence": 0.99}],
    )

    state = _resolve_window_state(analysis)
    assert state == "right"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "strictly located on the RIGHT wall" in combined
    assert "LEFT wall must remain free of windows" in combined
    assert "Do not mirror or flip the room horizontally" in combined
    assert "Maintain natural light direction entering from the RIGHT-side window" in combined
    assert "Keep all existing windows and doors on their original walls" in combined
    assert "Preserve camera orientation, viewpoint, and perspective" in combined
    assert "Do not mirror, invert, or horizontally flip the room layout" in combined


# 2. Window on the left (Project #16 real pattern)
def test_spatial_anchor_window_on_left():
    analysis = MockAnalysis(
        layout_summary="An empty room featuring light wooden plank floors, clean white walls, and a large multi-pane window filling the room with natural light.",
        empty_areas=[
            {"location": "left wall area", "description": "Wall area adjacent to the large window"},
            {"location": "back wall", "description": "Empty plain white wall on the right side"},
        ],
        existing_objects=[{"name": "multi-pane window", "confidence": 0.98}],
    )

    state = _resolve_window_state(analysis)
    assert state == "left"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "strictly located on the LEFT wall" in combined
    assert "RIGHT wall must remain free of windows" in combined
    assert "Do not mirror or flip the room horizontally" in combined
    assert "Maintain natural light direction entering from the LEFT-side window" in combined


# 3. Window in the center / back wall (Project #17 real pattern)
def test_spatial_anchor_window_in_center():
    analysis = MockAnalysis(
        layout_summary="An empty rectangular room featuring dark wood flooring, plain off-white walls, and a large multi-pane black-framed window providing ample daylight.",
        empty_areas=[
            {"location": "center floor", "description": "Spacious main floor area"},
            {"location": "right wall", "description": "Large blank neutral wall area"},
            {"location": "area below window", "description": "Low wall section beneath the central window frame"},
        ],
    )

    state = _resolve_window_state(analysis)
    assert state == "center"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "strictly located on the CENTER back wall" in combined
    assert "Do not relocate the window to side walls or mirror the room" in combined
    assert "Maintain natural light entering from the center back window" in combined


# 4. Multiple windows / windows on both sides
def test_spatial_anchor_multiple_windows():
    analysis = MockAnalysis(
        layout_summary="A sunlit corner room with windows on both the left and right walls providing expansive panoramic views.",
        empty_areas=[{"location": "center floor", "description": "Open area"}],
    )

    state = _resolve_window_state(analysis)
    assert state == "multiple"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "Multiple windows are present on their original walls" in combined
    assert "Maintain all window openings without repositioning or mirroring" in combined


# 5. Windowless room / no windows
def test_spatial_anchor_no_windows():
    analysis = MockAnalysis(
        layout_summary="An enclosed interior basement home theater with no windows, painted dark grey walls, and recessed lighting.",
        empty_areas=[{"location": "center floor", "description": "Open area"}],
    )

    state = _resolve_window_state(analysis)
    assert state == "none"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "The room has no windows as shown in REFERENCE 0" in combined
    assert "Do not add or fabricate any windows or exterior openings" in combined


# 6. Missing / empty spatial data
def test_spatial_anchor_missing_data():
    # analysis is None
    anchors_none = extract_spatial_anchors(None)
    combined_none = "\n".join(anchors_none)
    assert "Preserve the exact positions of existing windows, doors and architectural elements visible in the source image" in combined_none
    assert "Do not mirror or flip the room" in combined_none

    # analysis has empty fields
    analysis_empty = MockAnalysis(layout_summary=None, empty_areas=None, existing_objects=None)
    assert _resolve_window_state(analysis_empty) == "neutral"
    anchors_empty = extract_spatial_anchors(analysis_empty)
    combined_empty = "\n".join(anchors_empty)
    assert "Preserve the exact positions of existing windows, doors and architectural elements visible in the source image" in combined_empty


# 7. Conflicting analysis data (e.g. single window with both left and right indicators)
def test_spatial_anchor_conflicting_data():
    analysis = MockAnalysis(
        layout_summary="An empty bedroom with a window on the right wall.",
        empty_areas=[{"location": "left wall", "description": "window on the left wall"}],
    )

    state = _resolve_window_state(analysis)
    # Detected both left and right without multiple window phrasing -> conflict -> fallback to neutral
    assert state == "neutral"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)
    assert "Preserve the exact positions of existing windows, doors and architectural elements visible in the source image" in combined
    assert "Do not mirror or flip the room" in combined


# 8. LocalFallbackProvider analysis
def test_spatial_anchor_local_fallback_provider():
    analysis = MockAnalysis(
        layout_summary="Local fallback analysis (554x554, square). No AI inference performed; objects and style were not detected.",
        empty_areas=[],
        existing_objects=[],
        provider="local_fallback",
    )

    state = _resolve_window_state(analysis)
    assert state == "neutral"

    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)
    assert "Preserve the exact positions of existing windows, doors and architectural elements visible in the source image" in combined
    assert "Do not mirror or flip the room" in combined


# 9. Prompt length budget verification (guarantees < 4096 with Cloudflare wrapper)
def test_prompt_length_within_safe_limits():
    project = make_dummy_project("P0-D.5 Budget Check")
    analysis = MockAnalysis(
        layout_summary=(
            "An empty room featuring light wood flooring, white painted walls with crown molding, "
            "and a large window on the right side providing ample bright natural light."
        ),
        empty_areas=[
            {"location": "center floor", "description": "Large open area with light wood flooring", "suitable_for_decor": True},
            {"location": "back wall", "description": "Blank white accent or main wall", "suitable_for_decor": True},
            {"location": "left wall", "description": "Blank white side wall", "suitable_for_decor": True},
        ],
    )
    preference = make_dummy_preference()
    p1 = DummyProduct(1, "Japandi Low Sofa", "Sofa", "sofa")
    p7 = DummyProduct(7, "Rattan Bedside Table", "Table", "table")
    p8 = DummyProduct(8, "Minimal Desk", "Table", "table")
    products = [p1, p7, p8]
    ref_mapping = [(1, p1), (2, p7), (3, p8)]

    prompt = build_design_generation_prompt(
        project=project,
        analysis=analysis,
        preference=preference,
        products=products,
        reference_mapping=ref_mapping,
    )

    # Prompt returned by builder must stay under MAX_SAFE_PROMPT_CHARS (3580)
    assert len(prompt) <= MAX_SAFE_PROMPT_CHARS

    # When combined with Cloudflare's editing wrapper (~504 characters), total is strictly <= 4096
    cloudflare_wrapper_len = 504
    assert len(prompt) + cloudflare_wrapper_len <= 4096


# 10. Regression check: P0-D.2 reference priority and section structure remains intact
def test_prompt_preserves_p0d2_priority_and_structure():
    project = make_dummy_project("P0-D.2 Regression Check")
    analysis = MockAnalysis(
        layout_summary="An empty room with a large window on the right side.",
        empty_areas=[{"location": "left wall", "description": "Blank white wall"}],
    )
    preference = make_dummy_preference()

    p1 = DummyProduct(1, "Japandi Low Sofa", "Sofa", "sofa")
    p6 = DummyProduct(6, "Glass Side Table", "Table", "table")
    p7 = DummyProduct(7, "Rattan Bedside Table", "Table", "table")
    p9 = DummyProduct(9, "Brass Floor Lamp", "Lighting", "lighting")

    products = [p1, p6, p7, p9]
    # Products 1, 6, 7 have reference images; Product 9 is text-only
    ref_mapping = [(1, p1), (2, p6), (3, p7)]

    prompt = build_design_generation_prompt(
        project=project,
        analysis=analysis,
        preference=preference,
        products=products,
        reference_mapping=ref_mapping,
    )

    # References section
    assert "REFERENCE 0: original room image." in prompt
    assert "REFERENCE 1: Product ID 1; name Japandi Low Sofa; category Sofa." in prompt
    assert "REFERENCE 2: Product ID 6; name Glass Side Table; category Table." in prompt
    assert "REFERENCE 3: Product ID 7; name Rattan Bedside Table; category Table." in prompt

    # Primary referenced products section
    assert "Primary products with visual reference images (prioritize visual fidelity to reference photos):" in prompt
    assert "REFERENCE 1 -> Product ID 1: Japandi Low Sofa" in prompt
    assert "Fidelity: maintain silhouette, contour, color, and finish" in prompt

    # Supplementary text-only products section
    assert "Supplementary selected products (text-guided placement only, no reference image):" in prompt
    assert "Product ID 9: Brass Floor Lamp; category Lighting" in prompt

    # Spatial architectural lock section
    assert "Spatial architectural locks (anti-mirroring directives):" in prompt
    assert "Architectural lock: The window is strictly located on the RIGHT wall" in prompt
    assert "Lighting anchor: Maintain natural light direction entering from the RIGHT-side window" in prompt

    # Version check
    assert PROMPT_VERSION == "v2"


# 11. P0-D.8 Physical grounding directives
def test_physical_grounding_directives_present():
    analysis = MockAnalysis(layout_summary="A room with a window on the right.")
    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "Physical grounding: All floor-standing furniture (sofas, tables, cabinets, chairs) must rest firmly on the floor" in combined
    assert "legs/bases grounded" in combined


# 12. P0-D.8 Anti-floating cabinet and layout safety directives
def test_layout_safety_anti_floating_cabinets():
    analysis = MockAnalysis(layout_summary="A room with a window on the right.")
    anchors = extract_spatial_anchors(analysis)
    combined = "\n".join(anchors)

    assert "Never place cabinets on sofa backs or suspend them in mid-air" in combined
    assert "respect realistic depth, scale, and object occlusion" in combined
    assert "Mount only wall art, mirrors, or sconces on walls" in combined
    assert "all storage, tables, and seating must stand on the floor" in combined


# 13. P0-D.8 Separation of Floor zones from Wall zones in empty areas
def test_wall_vs_floor_zone_separation():
    from app.ai.image.prompt_builder import _format_empty_areas

    areas = [
        {"location": "center floor", "description": "Spacious oak floor"},
        {"location": "back wall", "description": "Blank accent wall"},
        {"location": "left wall", "description": "White partition"},
    ]
    formatted = _format_empty_areas(areas)

    assert "Floor zones (freestanding furniture): center floor" in formatted
    assert "Wall zones (wall decor only): back wall" in formatted
    assert "left wall" in formatted


# 14. P0-D.8 Room with many objects and limited floor space keeps prompt length within limit
def test_room_with_many_objects_and_limited_space():
    project = make_dummy_project("Compact Studio")
    analysis = MockAnalysis(
        layout_summary="A small compact room with dark flooring and a single window on the left side.",
        empty_areas=[
            {"location": "narrow floor space", "description": "Limited open floor"},
            {"location": "main wall", "description": "Small blank wall"},
        ],
    )
    preference = make_dummy_preference()
    p1 = DummyProduct(1, "Compact Sofa", "Sofa", "sofa")
    p2 = DummyProduct(2, "Coffee Table", "Table", "table")
    p3 = DummyProduct(3, "Bookshelf Cabinet", "Storage", "storage")
    p4 = DummyProduct(4, "Desk Lamp", "Lighting", "lighting")

    products = [p1, p2, p3, p4]
    ref_mapping = [(1, p1), (2, p2), (3, p3)]

    prompt = build_design_generation_prompt(
        project=project,
        analysis=analysis,
        preference=preference,
        products=products,
        reference_mapping=ref_mapping,
    )

    assert "Physical grounding: All floor-standing furniture" in prompt
    assert "Never place cabinets on sofa backs" in prompt
    assert "Floor zones (freestanding furniture): narrow floor space" in prompt
    assert "Wall zones (wall decor only): main wall" in prompt
    assert len(prompt) <= MAX_SAFE_PROMPT_CHARS
    assert len(prompt) + 504 <= 4096

