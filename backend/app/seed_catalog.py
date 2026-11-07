from decimal import Decimal

from app.core.database import SessionLocal
from app.initial_data import seed_initial_data
from app.models.entities import Category, Color, Material, Product, ProductStatus, RoomType, Style


def get_or_create(db, model, defaults=None, **lookup):
    instance = db.query(model).filter_by(**lookup).first()
    if instance:
        return instance
    data = {**lookup, **(defaults or {})}
    instance = model(**data)
    db.add(instance)
    db.flush()
    return instance


def searchable(product: Product) -> str:
    return " ".join(
        [
            product.name,
            product.description or "",
            product.tags or "",
            product.category.name,
            " ".join(item.name for item in product.materials),
            " ".join(item.name for item in product.styles),
            " ".join(item.name for item in product.room_types),
            " ".join(item.name for item in product.colors),
        ]
    ).lower()


def seed_catalog() -> None:
    db = SessionLocal()
    try:
        seed_initial_data(db)

        categories = [
            ("Sofa", "sofa"),
            ("Table", "table"),
            ("Chair", "chair"),
            ("Lighting", "lighting"),
            ("Rug", "rug"),
            ("Wall Decor", "wall-decor"),
            ("Storage", "storage"),
            ("Bedding", "bedding"),
            ("Plant Decor", "plant-decor"),
            ("Accessories", "accessories"),
        ]
        materials = ["Wood", "Metal", "Fabric", "Glass", "Bamboo", "Rattan", "Plastic", "Stone"]
        styles = ["Minimalist", "Japandi", "Scandinavian", "Modern", "Industrial", "Bohemian", "Vintage", "Luxury"]
        room_types = ["Bedroom", "Living Room", "Study Room", "Workspace", "Dining Room", "Studio"]
        colors = [
            ("White", "white", "#ffffff"),
            ("Black", "black", "#111111"),
            ("Oak", "oak", "#b8895b"),
            ("Walnut", "walnut", "#6b4423"),
            ("Sage", "sage", "#9caf88"),
            ("Terracotta", "terracotta", "#c66b4e"),
            ("Navy", "navy", "#1f3a5f"),
            ("Cream", "cream", "#f2eadc"),
            ("Gray", "gray", "#808080"),
            ("Brass", "brass", "#b08d57"),
        ]

        category_map = {slug: get_or_create(db, Category, name=name, slug=slug, defaults={"is_active": True}) for name, slug in categories}
        material_map = {m.lower().replace(" ", "-"): get_or_create(db, Material, name=m, slug=m.lower().replace(" ", "-"), defaults={"is_active": True}) for m in materials}
        style_map = {s.lower().replace(" ", "-"): get_or_create(db, Style, name=s, slug=s.lower().replace(" ", "-"), defaults={"is_active": True}) for s in styles}
        room_map = {r.lower().replace(" ", "-"): get_or_create(db, RoomType, name=r, slug=r.lower().replace(" ", "-"), defaults={"is_active": True}) for r in room_types}
        color_map = {slug: get_or_create(db, Color, name=name, slug=slug, defaults={"hex_code": hex_code, "is_active": True}) for name, slug, hex_code in colors}

        product_specs = [
            ("Japandi Low Sofa", "japandi-low-sofa", "sofa", 8200000, ["fabric", "wood"], ["japandi"], ["living-room", "studio"], ["cream", "oak"]),
            ("Modern Modular Sofa", "modern-modular-sofa", "sofa", 12500000, ["fabric", "metal"], ["modern"], ["living-room"], ["gray", "black"]),
            ("Scandinavian Lounge Chair", "scandinavian-lounge-chair", "chair", 3600000, ["wood", "fabric"], ["scandinavian"], ["living-room", "bedroom"], ["oak", "white"]),
            ("Industrial Bar Chair", "industrial-bar-chair", "chair", 1800000, ["metal", "wood"], ["industrial"], ["dining-room", "workspace"], ["black", "walnut"]),
            ("Oak Coffee Table", "oak-coffee-table", "table", 2400000, ["wood"], ["minimalist", "scandinavian"], ["living-room"], ["oak"]),
            ("Glass Side Table", "glass-side-table", "table", 1750000, ["glass", "metal"], ["modern", "luxury"], ["living-room", "bedroom"], ["black", "brass"]),
            ("Rattan Bedside Table", "rattan-bedside-table", "table", 2100000, ["rattan", "wood"], ["bohemian", "vintage"], ["bedroom"], ["walnut"]),
            ("Minimal Desk", "minimal-desk", "table", 3900000, ["wood", "metal"], ["minimalist", "modern"], ["study-room", "workspace"], ["white", "oak"]),
            ("Brass Floor Lamp", "brass-floor-lamp", "lighting", 2800000, ["metal"], ["luxury", "modern"], ["living-room", "bedroom"], ["brass"]),
            ("Bamboo Pendant Light", "bamboo-pendant-light", "lighting", 1650000, ["bamboo"], ["japandi", "bohemian"], ["dining-room", "studio"], ["oak"]),
            ("Black Desk Lamp", "black-desk-lamp", "lighting", 890000, ["metal", "plastic"], ["industrial", "modern"], ["workspace", "study-room"], ["black"]),
            ("Woven Jute Rug", "woven-jute-rug", "rug", 1900000, ["fabric"], ["bohemian", "japandi"], ["living-room", "bedroom"], ["cream"]),
            ("Geometric Gray Rug", "geometric-gray-rug", "rug", 2600000, ["fabric"], ["modern"], ["living-room", "studio"], ["gray", "black"]),
            ("Vintage Persian Rug", "vintage-persian-rug", "rug", 4300000, ["fabric"], ["vintage", "luxury"], ["living-room", "dining-room"], ["terracotta", "navy"]),
            ("Abstract Wall Art", "abstract-wall-art", "wall-decor", 950000, ["fabric"], ["modern", "minimalist"], ["living-room", "workspace"], ["white", "black"]),
            ("Rattan Wall Mirror", "rattan-wall-mirror", "wall-decor", 1350000, ["rattan", "glass"], ["bohemian", "japandi"], ["bedroom", "studio"], ["oak"]),
            ("Walnut Bookshelf", "walnut-bookshelf", "storage", 5200000, ["wood"], ["vintage", "modern"], ["study-room", "living-room"], ["walnut"]),
            ("White Storage Cabinet", "white-storage-cabinet", "storage", 4100000, ["wood", "metal"], ["minimalist"], ["bedroom", "workspace"], ["white"]),
            ("Stone Decor Tray", "stone-decor-tray", "accessories", 690000, ["stone"], ["luxury", "minimalist"], ["living-room", "bedroom"], ["gray"]),
            ("Ceramic Plant Pot", "ceramic-plant-pot", "plant-decor", 420000, ["stone"], ["scandinavian", "japandi"], ["living-room", "workspace"], ["white", "sage"]),
            ("Tall Faux Plant", "tall-faux-plant", "plant-decor", 1250000, ["plastic"], ["modern", "bohemian"], ["living-room", "studio"], ["sage"]),
            ("Linen Bedding Set", "linen-bedding-set", "bedding", 2300000, ["fabric"], ["minimalist", "japandi"], ["bedroom"], ["cream", "sage"]),
            ("Luxury Velvet Cushion", "luxury-velvet-cushion", "accessories", 620000, ["fabric"], ["luxury", "vintage"], ["living-room", "bedroom"], ["navy"]),
            ("Industrial Wall Shelf", "industrial-wall-shelf", "storage", 1600000, ["metal", "wood"], ["industrial"], ["workspace", "study-room"], ["black", "walnut"]),
            ("Round Dining Table", "round-dining-table", "table", 6800000, ["wood"], ["scandinavian", "modern"], ["dining-room"], ["oak"]),
            ("Modern Dining Chair", "modern-dining-chair", "chair", 1450000, ["fabric", "metal"], ["modern"], ["dining-room"], ["gray"]),
            ("Japandi Floor Cushion", "japandi-floor-cushion", "accessories", 780000, ["fabric"], ["japandi"], ["living-room", "studio"], ["cream"]),
            ("Bamboo Room Divider", "bamboo-room-divider", "accessories", 3100000, ["bamboo"], ["japandi", "bohemian"], ["studio", "bedroom"], ["oak"]),
            ("Minimal White Wardrobe", "minimal-white-wardrobe", "storage", 7900000, ["wood"], ["minimalist"], ["bedroom"], ["white"]),
            ("Glass Console Table", "glass-console-table", "table", 4500000, ["glass", "metal"], ["luxury", "modern"], ["living-room"], ["brass", "black"]),
        ]

        for name, slug, category_slug, price, material_slugs, style_slugs, room_slugs, color_slugs in product_specs:
            product = db.query(Product).filter(Product.slug == slug).first()
            if product is None:
                product = Product(
                    name=name,
                    slug=slug,
                    category_id=category_map[category_slug].id,
                    description=f"{name} for real room decor catalog and future AI matching.",
                    price=Decimal(price),
                    stock_quantity=12,
                    status=ProductStatus.ACTIVE,
                    is_active=True,
                    width=Decimal("80.00"),
                    height=Decimal("70.00"),
                    depth=Decimal("60.00"),
                    weight=Decimal("8.50"),
                    tags="decor, furniture, ai-room-decor",
                )
                db.add(product)
                db.flush()
            product.materials = [material_map[item] for item in material_slugs]
            product.styles = [style_map[item] for item in style_slugs]
            product.room_types = [room_map[item] for item in room_slugs]
            product.colors = [color_map[item] for item in color_slugs]
            db.flush()
            product.searchable_text = searchable(product)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_catalog()
