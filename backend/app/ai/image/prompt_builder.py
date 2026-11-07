import re
from typing import Any

from app.models.entities import Product, RoomAnalysis, RoomPreference, RoomProject

PROMPT_VERSION = "v2"

# Maximum character threshold for the generated prompt to guarantee that Cloudflare's
# outer editing wrapper (~504 characters) never pushes total length over the 4096 limit.
MAX_SAFE_PROMPT_CHARS = 3580

WINDOW_NO_WINDOW_PATTERN = re.compile(
    r"\b(no\s+windows?|windowless|without\s+windows?|zero\s+windows?)\b",
    re.IGNORECASE,
)

WINDOW_MULTIPLE_PATTERN = re.compile(
    r"\b(windows?\s+on\s+both|windows?\s+on\s+(?:the\s+)?(?:left\s+and\s+right|right\s+and\s+left)|multiple\s+windows|windows?\s+on\s+each\s+side|windows?\s+on\s+opposite)\b",
    re.IGNORECASE,
)

WINDOW_RIGHT_PATTERNS = [
    re.compile(
        r"\bwindows?\b[^.!?\n]{0,80}\b(?:on\s+(?:the\s+)?right|to\s+(?:the\s+)?right|along\s+(?:the\s+)?right|at\s+(?:the\s+)?right)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:right-side|right\s+wall|right\s+hand)\b[^.!?\n]{0,80}\bwindows?\b", re.IGNORECASE),
]

WINDOW_LEFT_PATTERNS = [
    re.compile(
        r"\bwindows?\b[^.!?\n]{0,80}\b(?:on\s+(?:the\s+)?left|to\s+(?:the\s+)?left|along\s+(?:the\s+)?left|at\s+(?:the\s+)?left)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:left-side|left\s+wall|left\s+hand)\b[^.!?\n]{0,80}\bwindows?\b", re.IGNORECASE),
]

WINDOW_CENTER_PATTERNS = [
    re.compile(
        r"\b(?:central\s+window|window\s+in\s+(?:the\s+)?(?:center|middle)|window\s+on\s+(?:the\s+)?(?:back|rear)\s+wall|beneath\s+(?:the\s+)?(?:central\s+)?window)\b",
        re.IGNORECASE,
    ),
]

_COMMON_ARCHITECTURAL_INVARIANTS = [
    "- Keep all existing windows and doors on their original walls as shown in REFERENCE 0.",
    "- Preserve camera orientation, viewpoint, and perspective of REFERENCE 0.",
    "- Do not mirror, invert, or horizontally flip the room layout, walls, or lighting.",
    "- Maintain original flooring patterns, materials, and architectural details.",
    "- Physical grounding: All floor-standing furniture (sofas, tables, cabinets, chairs) must rest firmly on the floor with legs/bases grounded.",
    "- Layout safety: Never place cabinets on sofa backs or suspend them in mid-air; respect realistic depth, scale, and object occlusion.",
    "- Wall vs floor: Mount only wall art, mirrors, or sconces on walls; all storage, tables, and seating must stand on the floor.",
]


def _format_dimensions(product: Product) -> str:
    """Format dimension guidance without asserting known mock placeholders (e.g. 80x70x60 cm)."""
    w = getattr(product, "width", None)
    h = getattr(product, "height", None)
    d = getattr(product, "depth", None)
    if w is None or h is None or d is None:
        return "standard proportion"
    try:
        if abs(float(w) - 80.0) < 0.01 and abs(float(h) - 70.0) < 0.01 and abs(float(d) - 60.0) < 0.01:
            return "standard proportion"
        return f"{w} x {h} x {d} cm (guide only)"
    except (TypeError, ValueError):
        return "standard proportion"


def _format_materials(product: Product) -> str:
    materials = [item.name for item in getattr(product, "materials", [])]
    return ", ".join(materials) if materials else "unspecified"


def _format_colors(product: Product) -> str:
    colors = [item.name for item in getattr(product, "colors", [])]
    return ", ".join(colors) if colors else "unspecified"


def _format_styles(product: Product) -> str:
    styles = [item.name for item in getattr(product, "styles", [])]
    return ", ".join(styles) if styles else "unspecified"


def _format_empty_areas(empty_areas: Any, compact: bool = False) -> str:
    """Format empty areas separating floor-standing zones from wall-mounted zones."""
    if not empty_areas:
        return "Floor: open floor areas; Walls: blank wall surfaces"
    if isinstance(empty_areas, list):
        floor_items: list[str] = []
        wall_items: list[str] = []
        for area in empty_areas:
            if isinstance(area, dict):
                loc = str(area.get("location", "")).strip()
                desc = str(area.get("description", "")).strip()
                label = loc if (compact or not desc) else f"{loc} ({desc})"
                if any(w in loc.lower() for w in ["wall", "accent"]):
                    wall_items.append(label)
                else:
                    floor_items.append(label)
            elif isinstance(area, str):
                s = area.strip()
                if any(w in s.lower() for w in ["wall", "accent"]):
                    wall_items.append(s)
                else:
                    floor_items.append(s)
        parts: list[str] = []
        if floor_items:
            parts.append(f"Floor zones (freestanding furniture): {'; '.join(floor_items)}")
        if wall_items:
            parts.append(f"Wall zones (wall decor only): {'; '.join(wall_items)}")
        return " | ".join(parts) if parts else "open floor zones"
    return str(empty_areas)


def _format_lighting(lighting: Any) -> str:
    if not lighting:
        return "unspecified"
    if isinstance(lighting, dict):
        parts = [f"{k}: {v}" for k, v in lighting.items() if v]
        return ", ".join(parts) if parts else "unspecified"
    return str(lighting)


def _format_preference_summary(preference: RoomPreference, compact: bool = False) -> str:
    parts: list[str] = []
    styles = [item.name for item in getattr(preference, "styles", [])]
    if styles:
        parts.append(f"styles: {', '.join(styles)}")
    colors = [item.name for item in getattr(preference, "colors", [])]
    if colors:
        parts.append(f"colors: {', '.join(colors)}")
    materials = [item.name for item in getattr(preference, "materials", [])]
    if materials:
        parts.append(f"materials: {', '.join(materials)}")
    if getattr(preference, "purpose", None):
        parts.append(f"purpose: {preference.purpose}")
    if not compact:
        categories = [item.name for item in getattr(preference, "categories", [])]
        if categories:
            parts.append(f"target categories: {', '.join(categories)}")
        if getattr(preference, "notes", None):
            parts.append(f"notes: {preference.notes.strip()}")
    return "; ".join(parts) if parts else "none specified"


def _collect_analysis_texts(analysis: RoomAnalysis | None) -> list[str]:
    if analysis is None:
        return []
    texts: list[str] = []
    layout = getattr(analysis, "layout_summary", None)
    if layout:
        texts.append(layout)
    empty_areas = getattr(analysis, "empty_areas", None)
    if isinstance(empty_areas, list):
        for area in empty_areas:
            if isinstance(area, dict):
                loc = area.get("location", "")
                desc = area.get("description", "")
                if loc and desc:
                    texts.append(f"{loc}: {desc}")
                elif loc:
                    texts.append(str(loc))
                elif desc:
                    texts.append(str(desc))
    existing_objects = getattr(analysis, "existing_objects", None)
    if isinstance(existing_objects, list):
        for obj in existing_objects:
            if isinstance(obj, dict):
                name = obj.get("name", "")
                if name:
                    texts.append(str(name))
    return texts


def _resolve_window_state(analysis: RoomAnalysis | None) -> str:
    """Classify window spatial position from verified RoomAnalysis data.

    Returns: 'right', 'left', 'center', 'multiple', 'none', or 'neutral'.
    """
    if analysis is None:
        return "neutral"
    provider = getattr(analysis, "provider", None)
    if provider == "local_fallback":
        return "neutral"
    layout = getattr(analysis, "layout_summary", None) or ""
    if "local fallback" in layout.lower():
        return "neutral"

    texts = _collect_analysis_texts(analysis)
    if not texts:
        return "neutral"

    full_text = " \n ".join(texts)

    if any(WINDOW_NO_WINDOW_PATTERN.search(t) for t in texts):
        return "none"

    if any(WINDOW_MULTIPLE_PATTERN.search(t) for t in texts):
        return "multiple"

    has_right = any(p.search(full_text) for p in WINDOW_RIGHT_PATTERNS)
    has_left = any(p.search(full_text) for p in WINDOW_LEFT_PATTERNS)
    has_center = any(p.search(full_text) for p in WINDOW_CENTER_PATTERNS)

    # Check for ambiguous or conflicting indicators
    match_count = sum([has_right, has_left, has_center])
    if match_count > 1:
        return "neutral"  # Conflicting signals -> fall back safely to neutral preservation
    if has_right:
        return "right"
    if has_left:
        return "left"
    if has_center:
        return "center"

    return "neutral"


def extract_spatial_anchors(analysis: RoomAnalysis | None) -> list[str]:
    """Dynamically determine architectural locks from verified RoomAnalysis data.

    Only makes explicit LEFT/RIGHT assertions when confirmed by reliable analysis data.
    If data is missing, ambiguous, conflicting, or from fallback provider,
    returns neutral architectural preservation directives without asserting specific walls.
    """
    state = _resolve_window_state(analysis)
    anchors: list[str] = []

    if state == "right":
        anchors.append(
            "- Architectural lock: The window is strictly located on the RIGHT wall as shown in REFERENCE 0. "
            "The LEFT wall must remain free of windows. Do not mirror or flip the room horizontally."
        )
        anchors.append("- Lighting anchor: Maintain natural light direction entering from the RIGHT-side window.")
    elif state == "left":
        anchors.append(
            "- Architectural lock: The window is strictly located on the LEFT wall as shown in REFERENCE 0. "
            "The RIGHT wall must remain free of windows. Do not mirror or flip the room horizontally."
        )
        anchors.append("- Lighting anchor: Maintain natural light direction entering from the LEFT-side window.")
    elif state == "center":
        anchors.append(
            "- Architectural lock: The window is strictly located on the CENTER back wall as shown in REFERENCE 0. "
            "Do not relocate the window to side walls or mirror the room."
        )
        anchors.append("- Lighting anchor: Maintain natural light entering from the center back window.")
    elif state == "multiple":
        anchors.append(
            "- Architectural lock: Multiple windows are present on their original walls as shown in REFERENCE 0. "
            "Maintain all window openings without repositioning or mirroring."
        )
    elif state == "none":
        anchors.append(
            "- Architectural lock: The room has no windows as shown in REFERENCE 0. "
            "Do not add or fabricate any windows or exterior openings."
        )
    else:  # 'neutral' fallback for missing, ambiguous, conflicting, or fallback analysis
        anchors.append(
            "- Architectural lock: Preserve the exact positions of existing windows, doors and architectural elements "
            "visible in the source image. Do not mirror or flip the room."
        )

    anchors.extend(_COMMON_ARCHITECTURAL_INVARIANTS)
    return anchors


def build_design_generation_prompt(
    project: RoomProject,
    analysis: RoomAnalysis,
    preference: RoomPreference,
    products: list[Product],
    reference_mapping: list[tuple[int, Product]] | None = None,
) -> str:
    reference_mapping = reference_mapping or []
    ref_by_product_id = {product.id: index for index, product in reference_mapping}

    referenced_products = [product for product in products if product.id in ref_by_product_id]
    text_only_products = [product for product in products if product.id not in ref_by_product_id]

    reference_lines = ["REFERENCE 0: original room image."]
    reference_lines.extend(
        f"REFERENCE {index}: Product ID {product.id}; name {product.name}; category {product.category.name}."
        for index, product in reference_mapping
    )

    referenced_lines = [
        (
            f"- REFERENCE {ref_by_product_id[product.id]} -> Product ID {product.id}: {product.name}; "
            f"category {product.category.name}; style {_format_styles(product)}; "
            f"descriptive colors {_format_colors(product)}; descriptive materials {_format_materials(product)}; "
            f"scale: {_format_dimensions(product)}."
        )
        for product in referenced_products
    ]

    text_only_lines = [
        (
            f"- Product ID {product.id}: {product.name}; category {product.category.name}; "
            f"style {_format_styles(product)}; descriptive colors {_format_colors(product)}; "
            f"descriptive materials {_format_materials(product)}; scale: {_format_dimensions(product)}."
        )
        for product in text_only_products
    ]

    fidelity_rules = [
        "Visual reference directives:",
        "- For products with visual references (REFERENCE 1..N), the reference image is the primary visual authority.",
        "- Fidelity: maintain silhouette, contour, color, and finish as shown in each product reference image.",
        "- Do not fabricate conflicting parts (such as unwanted wooden frames or mismatched legs) if not visible in the reference image.",
        "- Do not replace a selected product with unrelated furniture.",
        "- Integrate lighting and shadows naturally.",
        "Visual references improve similarity but do not guarantee exact pixel reproduction of products.",
    ]

    spatial_anchors = extract_spatial_anchors(analysis)
    room_type = getattr(analysis, "room_type", None) or getattr(project, "room_type", None) or "unknown"
    layout_summary = getattr(analysis, "layout_summary", None) or "not available"

    def _assemble(compact: bool) -> str:
        sections = [
            "Generate one realistic decorated room image from the uploaded source room photo.",
            "Preserve source room architecture; add only selected catalog decor and furniture.",
            "Spatial architectural locks (anti-mirroring directives):",
            *spatial_anchors,
            "Visual reference images:",
            *reference_lines,
            *fidelity_rules,
            f"Project title: {project.title}",
            f"Detected room type: {room_type}",
            f"Layout summary: {layout_summary}",
            f"Empty areas suitable for decor: {_format_empty_areas(getattr(analysis, 'empty_areas', None), compact=compact)}",
            f"Lighting: {_format_lighting(getattr(analysis, 'lighting', None))}",
            f"User preferences: {_format_preference_summary(preference, compact=compact)}",
        ]

        if referenced_lines:
            sections.append("Primary products with visual reference images (prioritize visual fidelity to reference photos):")
            sections.extend(referenced_lines)

        if text_only_lines:
            sections.append("Supplementary selected products (text-guided placement only, no reference image):")
            sections.extend(text_only_lines)

        sections.append("Output: photorealistic interior decor preview, cohesive composition, realistic scale, no text, no watermark.")
        return "\n".join(sections)

    prompt = _assemble(compact=False)
    if len(prompt) > MAX_SAFE_PROMPT_CHARS:
        prompt = _assemble(compact=True)

    return prompt
