"""Prompt Adapter for AI Room Decor Skill Bridge (V1.0 & V1.5 PRO).

Implements the Skill prompt contract:
1. System prompt grounding (architecture_lock.md, catalog_fidelity.md).
2. Two-tier personalization grounding (purpose, styles, colors, materials, budget context, notes).
3. Reference 0: Base room photograph only (Immutable architecture).
4. Reference 1..N: Real catalog products with immutable Product IDs and audited traits.
5. Spatial layout intelligence: Translates 2D layout planning into natural language spatial placement.
6. Robust user notes sanitization preventing prompt injection attacks.
7. Safe length enforcement (< 3580 chars) for Cloudflare Workers AI FLUX.2 Dev.
"""

from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

from app.models.entities import Product, RoomAnalysis, RoomPreference, RoomProject
from app.recommendation.functional_planner import ProductRole, get_product_role
from app.recommendation.resolver import EffectivePreference

# Distinctive traits for the 30 catalog products from the audited catalog images on disk
CATALOG_TRAITS: dict[int, str] = {
    1: "low-profile floor sofa, textured off-white cream boucle fabric, curved organic backrest, floor-seated base with no exposed legs, two square cushions and two spherical ball throw pillows",
    2: "modern low-profile modular L-shape sectional sofa, off-white cream corduroy ribbed fabric, channel-tufted square grid seat cushions, burnt orange and white accent pillows",
    3: "Scandinavian lounge armchair, visible natural light oak wood frame, woven paper cord back and seat, draped fluffy sheepskin fleece throw, angled legs",
    4: "industrial barstool, round rustic brown wood seat with perimeter metal studs, low curved wood backrest on black metal bracket, matte black steel legs with circular footrest ring",
    5: "low rectangular coffee table, thick solid natural light oak wood slab tabletop, two wide flat wood plank slab panel legs set inward",
    6: "modern smoky dark amber-brown tinted glass side table, semicircular curved glass top, vertical smoked dark glass panel pedestal base",
    7: "bedside nightstand cabinet, natural light oak wood frame, open upper cubby shelf, single lower drawer with woven cane rattan mesh front, round wooden knob, four round wooden legs",
    8: "natural light honey wood writing desk with integrated top hutch organizer tiers (three shelf compartments and one small white drawer), tapered wooden legs",
    9: "tall slender floor lamp, vertical straight brushed brass metal stem, right-angle horizontal top support arm, downward conical brass shade, flat round circular disk base",
    10: "hanging natural bamboo pendant lamp, rounded drum open-mesh woven wicker cage shade, visible warm glowing Edison bulb, ceiling drop cord",
    11: "architectural task desk lamp, matte black metal finish, articulated spring-tension adjustable angled arms, flared metal bell shade, weighted round base",
    12: "rectangular natural jute area rug, striped braided ribbed loop woven organic texture, natural tan and sandy fiber tones",
    13: "rectangular area rug, bold high-contrast black-and-white optical illusion concentric geometric pyramid step tunnel pattern",
    14: "traditional vintage Persian oriental area rug, vibrant cerulean turquoise blue field, rich terracotta rust floral border, central ornate medallion",
    15: "vertical framed canvas wall art, monochromatic off-white 3D plaster relief, raised sculptural parallel arched curving ridges",
    16: "tall arched wall mirror with flat bottom, natural light rattan reed frame with tightly wrapped horizontal ribbed texture",
    17: "tall 5-tier vertical open bookshelf, warm walnut wood finish, alternating asymmetrical vertical box divider cubbies, open ladder frame",
    18: "medium-height 2-door storage cabinet, smooth matte white finish, two hinged doors with curved vertical silver bow handles, solid plinth base",
    19: "rectangular natural brown polished marble catchall tray with white veining, deeply scalloped fluted wavy outer rim edges",
    20: "rounded ceramic planter pot, deep mottled cobalt ocean-blue glossy glaze, holding a vibrant green potted indoor palm plant",
    21: "tall indoor potted Monstera Deliciosa plant, large perforated split fenestrated deep green leaves, aerial roots, small black nursery pot",
    22: "relaxed washed linen bedding duvet and pillow set, deep earthy olive moss green tone, soft crinkled linen texture",
    23: "rectangular lumbar accent throw pillow, diagonal wide striped panels of rich chocolate brown and copper dusty rose plush velvet",
    24: "pair of 2-tier industrial floating wall shelves, thick rustic solid dark wood planks, matte black iron plumbing pipe brackets and wall flanges",
    25: "round rustic live-edge wood dining table, turquoise translucent resin river inlay through center, heavy black metal X-base pedestal legs",
    26: "mid-century modern dining chair, curved solid walnut wood backrest, off-white cream cushioned seat, tapered walnut wood legs",
    27: "low floor futon fold-out sofa cushion, dusty slate blue corduroy fabric, deeply tufted button indentations, relaxed floor seating",
    28: "vertical architectural room divider screen, evenly spaced vertical round natural bamboo wood slats spanning floor to ceiling",
    29: "tall modular wardrobe closet, flat matte white doors with natural oak perimeter wood framing, vertical recessed cutout wood handles, tapered legs",
    30: "clear tempered glass waterfall console table, transparent glass bridge frame with suspended interior walnut wood two-drawer unit",
}

MAX_SAFE_PROMPT_CHARS = 3580


def sanitize_user_notes(notes: str | None) -> str:
    """Sanitize user notes to prevent prompt injection or constraint override."""
    if not notes:
        return ""
    cleaned = notes.strip()
    # Strip dangerous directives and control keywords
    patterns = [
        r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+instructions\b",
        r"(?i)\bsystem\s*:\s*",
        r"(?i)\bdeveloper\s*mode\b",
        r"(?i)\badmin\s*override\b",
        r"(?i)\bdisregard\b",
        r"(?i)\bprompt\s*injection\b",
        r"(?i)\bdo\s+not\s+follow\b",
    ]
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned)
    # Strip system delimiter tokens like ```, <|...|>, etc.
    cleaned = re.sub(r"[`<>{}\[\]|\\]", "", cleaned)
    # Truncate to safe length
    return cleaned[:200].strip()


def build_spatial_layout_guidance(selected_products: list[Product], analysis: RoomAnalysis | None) -> list[str]:
    """Generate natural language spatial placement instructions derived from V2 layout intelligence."""
    guidance: list[str] = []
    has_anchor = False
    
    for product in selected_products:
        role = get_product_role(product)
        cat_slug = getattr(product.category, "slug", "").lower() if getattr(product, "category", None) else ""
        name = product.name

        if role == ProductRole.ANCHOR:
            has_anchor = True
            if "sofa" in cat_slug or "cushion" in cat_slug:
                guidance.append(f"Anchor '{name}' firmly on the central floor area facing camera perspective, maintaining 0.6m walking clearance.")
            elif "table" in cat_slug:
                guidance.append(f"Center dining table '{name}' within the open room zone with ample chair pull-out clearance.")
            elif "desk" in cat_slug:
                guidance.append(f"Position workspace desk '{name}' adjacent to natural light while keeping door circulation unobstructed.")
            elif "bedding" in cat_slug:
                guidance.append(f"Position bed area with '{name}' resting along the primary interior wall.")
            else:
                guidance.append(f"Anchor primary piece '{name}' centrally on the floor with balanced clearance.")

        elif role == ProductRole.FUNCTIONAL:
            if "table" in cat_slug:
                if has_anchor:
                    guidance.append(f"Place '{name}' directly in front of or immediately adjacent to the anchor seating.")
                else:
                    guidance.append(f"Position '{name}' along the lateral living zone.")
            elif "storage" in cat_slug:
                guidance.append(f"Place cabinet/bookshelf '{name}' flush against the side wall perimeter without obstructing windows.")
            elif "chair" in cat_slug:
                guidance.append(f"Arrange chair '{name}' angled toward the primary seating cluster.")
            else:
                guidance.append(f"Situate functional piece '{name}' naturally along the secondary utility area.")

        else:  # ACCENT
            if "lighting" in cat_slug:
                guidance.append(f"Position lighting '{name}' on the right or left room corner flank to provide warm localized illumination.")
            elif "rug" in cat_slug:
                guidance.append(f"Spread area rug '{name}' completely flat on the floor underneath the front legs of the seating.")
            elif "wall-decor" in cat_slug:
                guidance.append(f"Hang/mount wall decor '{name}' at eye level centered on the main visible wall plane.")
            elif "plant-decor" in cat_slug:
                guidance.append(f"Place potted plant '{name}' in an empty floor corner near daylight ingress.")
            elif "accessories" in cat_slug and "divider" in name.lower():
                guidance.append(f"Erect room divider '{name}' vertically to zone the space without blocking paths.")
            else:
                guidance.append(f"Place accent item '{name}' thoughtfully to enhance aesthetic balance.")

    return guidance


def build_skill_manifest(
    room_image_path: str,
    selected_products: list[Product],
    reference_image_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Build an ordered reference manifest adhering to Skill V1.0 specifications."""
    manifest: list[dict[str, Any]] = [
        {
            "index": 0,
            "role": "room",
            "asset": str(room_image_path),
            "description": "Base room photograph with immutable architecture, camera perspective, and lighting.",
        }
    ]

    ref_paths = reference_image_paths or []
    for idx, product in enumerate(selected_products):
        ref_path_str = str(ref_paths[idx]) if idx < len(ref_paths) else ""
        manifest.append(
            {
                "index": idx + 1,
                "role": "product",
                "product_id": product.id,
                "product_name": product.name,
                "category": getattr(product.category, "slug", "") if getattr(product, "category", None) else "",
                "asset": ref_path_str,
                "distinctive_traits": CATALOG_TRAITS.get(product.id, product.name),
            }
        )
    return manifest


def build_skill_prompt(
    project: RoomProject,
    selected_products: list[Product],
    analysis: RoomAnalysis | None = None,
    preference: RoomPreference | EffectivePreference | None = None,
    manifest: list[dict[str, Any]] | None = None,
    correction: str = "",
) -> str:
    """Build the structured prompt combining system invariants, catalog manifest,
    rich personalization context, and natural language spatial guidance.
    """
    room_type = (project.room_type or (analysis.room_type if analysis else None) or "room").replace("-", " ")
    
    # 1. Resolve Personalization Attributes
    style_names: list[str] = []
    color_names: list[str] = []
    material_names: list[str] = []
    purpose_str: str = ""
    notes_str: str = ""
    budget_ctx: str = ""

    if isinstance(preference, EffectivePreference):
        style_names = preference.styles
        color_names = preference.colors
        material_names = preference.materials
        purpose_str = preference.purpose or ""
        notes_str = sanitize_user_notes(preference.notes)
        if preference.budget_max is not None:
            budget_ctx = f"Budget target under {float(preference.budget_max):,.0f} {preference.currency}"
    elif preference is not None:
        style_names = [s.name for s in getattr(preference, "styles", [])]
        color_names = [c.name for c in getattr(preference, "colors", [])]
        material_names = [m.name for m in getattr(preference, "materials", [])]
        purpose_str = getattr(preference, "purpose", "") or ""
        notes_str = sanitize_user_notes(getattr(preference, "notes", None))
        b_max = getattr(preference, "budget_max", None)
        if b_max is not None:
            budget_ctx = f"Budget target under {float(b_max):,.0f} VND"

    style_str = ", ".join(style_names) if style_names else "contemporary modern"
    color_str = f"Preferred palette: {', '.join(color_names)}. " if color_names else ""
    mat_str = f"Preferred materials: {', '.join(material_names)}. " if material_names else ""

    # 2. Product mapping block
    prod_lines = []
    for item in (manifest or [])[1:]:
        pid = item.get("product_id")
        idx = item.get("index")
        traits = item.get("distinctive_traits") or item.get("product_name")
        prod_lines.append(f"- Image {idx} (Product #{pid} / Product ID {pid}): {traits}")
    products_block = "\n".join(prod_lines) if prod_lines else "Selected catalog items."

    # 3. Spatial Layout Instructions
    spatial_instructions = build_spatial_layout_guidance(selected_products, analysis)
    spatial_block = "\n".join(f"- {inst}" for inst in spatial_instructions) if spatial_instructions else "- Place items harmoniously on the floor plane."

    # 4. Lighting & Architecture notes
    light_str = "natural daylight from visible windows with soft ambient floor fill"
    if analysis and analysis.lighting and isinstance(analysis.lighting, dict):
        ldir = analysis.lighting.get("direction", "ambient")
        ltype = analysis.lighting.get("type", "natural daylight")
        light_str = f"{ltype} with direction from {ldir}"

    # 5. Assemble Structured Prompt
    intent_parts = []
    if purpose_str:
        intent_parts.append(f"Functional Room Purpose: {purpose_str}.")
    if color_str or mat_str:
        intent_parts.append(f"{color_str}{mat_str}".strip())
    if budget_ctx:
        intent_parts.append(f"Design Context: {budget_ctx}.")
    if notes_str:
        intent_parts.append(f"User Custom Desire: {notes_str}.")
    personalization_section = ("\nUSER PERSONALIZATION CONTEXT:\n" + "\n".join(f"- {p}" for p in intent_parts) + "\n") if intent_parts else ""

    prompt = (
        f"You are AI ROOM DECOR, a catalog-grounded photorealistic interior visualization agent.\n"
        f"TASK: Edit Image 0 ({room_type}) by placing ONLY the selected catalog products. Preserve all existing room architecture and background elements.\n\n"
        f"REFERENCES:\n"
        f"- Image 0: Base room photograph. Camera framing, walls, windows, doors, ceiling, and flooring are IMMUTABLE.\n"
        f"{products_block}\n"
        f"{personalization_section}\n"
        f"SPATIAL LAYOUT & PLACEMENT PLAN:\n"
        f"{spatial_block}\n\n"
        f"BINDING RULES (architecture_lock.md & catalog_fidelity.md):\n"
        f"1. Architecture Lock (Scene & Structure): Keep all walls, ceilings, windows, doorways, architectural trim, camera perspective, AND existing background elements (existing furniture, built-ins, plants, structural fixtures) identical to Image 0. Do NOT erase, shift, or alter existing room objects unless specifically replaced.\n"
        f"2. Strict Catalog Inventory (Zero Hallucination): Place ONLY the explicitly referenced catalog products. Do NOT hallucinate or add unrequested extra items such as vases, flowers, tabletop decor, wall art, side tables, rugs, or decorative clutter.\n"
        f"3. Physical Proportion & Realistic Scale: Maintain anatomically accurate human scale and proper relative proportions between placed items (e.g. coffee table height must remain lower than chair seat; do not oversize, stretch, or exaggerate product dimensions).\n"
        f"4. Catalog Fidelity: Replicate the exact silhouette, materials, cushions, and contours of the reference products. No substitute furniture.\n"
        f"5. Circulation & Clearance: Maintain clear unobstructed pathways to doors, windows, and balcony exits. Do not obstruct door swings.\n"
        f"6. Lighting & Shadows: Match room illumination ({light_str}). Render realistic contact shadows and depth occlusion where furniture contacts the floor. Preserve photorealistic lighting consistency.\n"
        f"7. Style Influence: Integrate selected items harmoniously within {style_str} styling without violating architecture or catalog identity.\n"
    )

    if correction:
        prompt += f"\nPRIOR VALIDATION CORRECTIONS (MUST RESOLVE):\n{correction}\n"

    prompt += "\nOUTPUT REQUIREMENT: Return ONLY the edited photograph showing the room with selected products physically placed."

    if len(prompt) > MAX_SAFE_PROMPT_CHARS:
        prompt = prompt[:MAX_SAFE_PROMPT_CHARS - 20] + "... (truncated)"

    return prompt
