"""Functional Room Planning & Catalog Role Classification for AI Room Decor V1.5 PRO.

Classifies the 30 catalog products into functional design roles:
- ANCHOR: Primary foundational furniture pieces defining the room's main utility.
- FUNCTIONAL: Secondary supporting utility furniture providing ergonomic convenience.
- ACCENT: Lighting, textiles, and decorative items establishing atmosphere.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.models.entities import Product


class ProductRole(str, Enum):
    ANCHOR = "ANCHOR"
    FUNCTIONAL = "FUNCTIONAL"
    ACCENT = "ACCENT"


# Explicit mapping for the 30 audited catalog products
CATALOG_ROLES: dict[int, ProductRole] = {
    # Sofas & Primary Seating (Anchor)
    1: ProductRole.ANCHOR,       # Japandi Low Sofa
    2: ProductRole.ANCHOR,       # Modern Modular Sofa
    3: ProductRole.ANCHOR,       # Scandinavian Lounge Chair (Can act as Anchor in small room or bedroom)
    # Work & Dining Desks (Anchor)
    8: ProductRole.ANCHOR,       # Minimal Desk
    25: ProductRole.ANCHOR,      # Round Dining Table
    22: ProductRole.ANCHOR,      # Linen Bedding Set (Represents bed area)
    27: ProductRole.ANCHOR,      # Japandi Floor Cushion (Low floor seating anchor)

    # Tables & Utility Seating & Storage (Functional)
    4: ProductRole.FUNCTIONAL,   # Industrial Bar Chair
    5: ProductRole.FUNCTIONAL,   # Oak Coffee Table
    6: ProductRole.FUNCTIONAL,   # Glass Side Table
    7: ProductRole.FUNCTIONAL,   # Rattan Bedside Table
    17: ProductRole.FUNCTIONAL,  # Walnut Bookshelf
    18: ProductRole.FUNCTIONAL,  # White Storage Cabinet
    26: ProductRole.FUNCTIONAL,  # Modern Dining Chair
    29: ProductRole.FUNCTIONAL,  # Minimal White Wardrobe
    30: ProductRole.FUNCTIONAL,  # Glass Console Table

    # Lighting, Rugs & Decor (Accent)
    9: ProductRole.ACCENT,       # Brass Floor Lamp
    10: ProductRole.ACCENT,      # Bamboo Pendant Light
    11: ProductRole.ACCENT,      # Black Desk Lamp
    12: ProductRole.ACCENT,      # Woven Jute Rug
    13: ProductRole.ACCENT,      # Geometric Gray Rug
    14: ProductRole.ACCENT,      # Vintage Persian Rug
    15: ProductRole.ACCENT,      # Abstract Wall Art
    16: ProductRole.ACCENT,      # Rattan Wall Mirror
    19: ProductRole.ACCENT,      # Stone Decor Tray
    20: ProductRole.ACCENT,      # Ceramic Plant Pot
    21: ProductRole.ACCENT,      # Tall Faux Plant
    23: ProductRole.ACCENT,      # Luxury Velvet Cushion
    24: ProductRole.ACCENT,      # Industrial Wall Shelf
    28: ProductRole.ACCENT,      # Bamboo Room Divider
}


# Preferred composition recipe by room type
ROOM_TYPE_RECIPES: dict[str, list[ProductRole]] = {
    "living-room": [ProductRole.ANCHOR, ProductRole.ACCENT, ProductRole.FUNCTIONAL],
    "living room": [ProductRole.ANCHOR, ProductRole.ACCENT, ProductRole.FUNCTIONAL],
    "phòng khách": [ProductRole.ANCHOR, ProductRole.ACCENT, ProductRole.FUNCTIONAL],
    "bedroom": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "phòng ngủ": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "study-room": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "study room": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "workspace": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "phòng làm việc": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "phòng học": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "dining-room": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "dining room": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "phòng ăn": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
    "studio": [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT],
}


def get_product_role(product: Product) -> ProductRole:
    """Return the designated functional role for a catalog product."""
    if product.id in CATALOG_ROLES:
        return CATALOG_ROLES[product.id]

    cat_slug = getattr(product.category, "slug", "").lower() if getattr(product, "category", None) else ""
    if cat_slug in ("sofa", "bedding"):
        return ProductRole.ANCHOR
    if cat_slug in ("table", "storage", "chair"):
        return ProductRole.FUNCTIONAL
    return ProductRole.ACCENT


def get_recipe_for_room(room_type: str) -> list[ProductRole]:
    """Return the functional role hierarchy for a room type."""
    normalized = room_type.strip().lower()
    return ROOM_TYPE_RECIPES.get(normalized, [ProductRole.ANCHOR, ProductRole.FUNCTIONAL, ProductRole.ACCENT])
