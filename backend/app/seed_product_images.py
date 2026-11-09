import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.engine import make_url
from sqlalchemy.orm import joinedload

from app.core.config import PROJECT_ROOT, settings
from app.core.database import SessionLocal
from app.models.entities import Product, ProductImage

IMAGE_SIZE = 800
OUTPUT_DIRNAME = "generated-demo"

CATEGORY_BACKGROUNDS = {
    "sofa": ("#F7EFE7", "#C88965"),
    "table": ("#F4F1EA", "#9B6A45"),
    "chair": ("#F3F6F1", "#6F8A70"),
    "lighting": ("#F8F1D9", "#D4A63F"),
    "rug": ("#F6ECEB", "#B55B5B"),
    "wall-decor": ("#F5F0EA", "#6E6A64"),
    "storage": ("#EEF2F4", "#617787"),
    "bedding": ("#F4F0F5", "#8A6F91"),
    "plant-decor": ("#EEF5EB", "#5E8C61"),
    "accessories": ("#F8F0E7", "#B97A56"),
}

COLOR_HEX = {
    "black": "#111111",
    "brass": "#B08D57",
    "cream": "#F2EADC",
    "gray": "#808080",
    "navy": "#1F3A5F",
    "oak": "#B8895B",
    "sage": "#9CAF88",
    "terracotta": "#C66B4E",
    "walnut": "#6B4423",
    "white": "#FFFFFF",
}


def assert_development_database() -> None:
    # 1. Chặn tuyệt đối nếu môi trường được cấu hình là production hoặc staging
    if (settings.app_env or "").lower() in {"production", "prod", "staging"}:
        raise RuntimeError(
            f"Refusing to seed demo product images in production environment (APP_ENV={settings.app_env})."
        )

    # 2. Chặn nếu đang cấu hình lưu trữ đám mây (Cloudinary) để tránh upload ảnh demo lên CDN thật
    if (settings.storage_backend or "").lower() == "cloudinary":
        raise RuntimeError(
            "Refusing to seed demo product images when STORAGE_BACKEND is configured for Cloudinary."
        )

    url = make_url(settings.database_url)
    database = url.database
    host = (url.host or "").lower()

    # 3. Chặn kết nối tới cơ sở dữ liệu từ xa (remote cloud host như TiDB Cloud, AWS RDS, Render, ...)
    allowed_hosts = {"localhost", "127.0.0.1", "mysql", "mariadb", "host.docker.internal", ""}
    if host not in allowed_hosts:
        raise RuntimeError(
            f"Refusing to seed product images to remote host '{host}'. "
            "Demo seeding is strictly limited to local development databases."
        )

    # 4. Chặn ghi nhầm vào cơ sở dữ liệu test
    if not database or "test" in database.lower():
        raise RuntimeError(
            f"Refusing to seed demo product images to test database: {database}"
        )

    # 5. Kiểm tra tên database phát triển hợp lệ (mặc định: ai_room_decor, ai_room_decor_dev)
    # Cho phép cờ môi trường ALLOW_DEMO_SEED=1 nếu lập trình viên dùng tên DB local tùy biến
    allowed_databases = {"ai_room_decor", "ai_room_decor_dev"}
    if database not in allowed_databases and not os.getenv("ALLOW_DEMO_SEED"):
        raise RuntimeError(
            f"Refusing to seed product images outside allowed development databases ({allowed_databases}). "
            f"Current database: '{database}'. If this is a local development database, "
            f"set environment variable ALLOW_DEMO_SEED=1 to permit execution."
        )


def storage_root() -> Path:
    root = Path(settings.product_storage_dir)
    return root if root.is_absolute() else (PROJECT_ROOT / root).resolve()


def font(size: int) -> ImageFont.ImageFont:
    for candidate in ["arial.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=selected_font)
    return right - left


def wrap_text(draw: ImageDraw.ImageDraw, text: str, selected_font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_width(draw, candidate, selected_font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def product_palette(product: Product) -> tuple[str, str, str]:
    category_slug = product.category.slug if product.category else "accessories"
    background, accent = CATEGORY_BACKGROUNDS.get(category_slug, ("#F6F0EA", "#B97A56"))
    if product.colors:
        primary_slug = product.colors[0].slug
        accent = product.colors[0].hex_code or COLOR_HEX.get(primary_slug, accent)
    secondary = "#2F2A26" if accent.lower() in {"#ffffff", "#f2eadc"} else "#FFFFFF"
    return background, accent, secondary


def rounded_rectangle(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 30) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_category_icon(draw: ImageDraw.ImageDraw, slug: str, accent: str) -> None:
    shadow = "#00000022"
    dark = "#2F2A26"
    if slug == "sofa":
        rounded_rectangle(draw, (190, 365, 610, 520), shadow, 45)
        rounded_rectangle(draw, (180, 340, 620, 500), accent, 45)
        rounded_rectangle(draw, (220, 280, 580, 385), accent, 40)
        rounded_rectangle(draw, (225, 370, 390, 470), "#FFFFFFAA", 28)
        rounded_rectangle(draw, (410, 370, 575, 470), "#FFFFFFAA", 28)
        draw.rectangle((240, 500, 280, 565), fill=dark)
        draw.rectangle((520, 500, 560, 565), fill=dark)
    elif slug == "chair":
        rounded_rectangle(draw, (280, 330, 520, 480), accent, 35)
        rounded_rectangle(draw, (310, 235, 490, 360), accent, 38)
        draw.line((320, 480, 275, 590), fill=dark, width=18)
        draw.line((480, 480, 525, 590), fill=dark, width=18)
        draw.line((330, 500, 470, 500), fill=dark, width=12)
    elif slug == "table":
        rounded_rectangle(draw, (220, 330, 580, 390), accent, 28)
        draw.rectangle((265, 390, 310, 575), fill=dark)
        draw.rectangle((490, 390, 535, 575), fill=dark)
        draw.arc((265, 505, 535, 650), 180, 360, fill=accent, width=12)
    elif slug == "lighting":
        draw.line((400, 185, 400, 325), fill=dark, width=12)
        draw.polygon([(300, 335), (500, 335), (560, 470), (240, 470)], fill=accent)
        draw.ellipse((330, 455, 470, 595), fill="#FFE8A8")
        draw.arc((315, 445, 485, 615), 0, 180, fill=dark, width=10)
    elif slug == "rug":
        rounded_rectangle(draw, (190, 280, 610, 540), accent, 60)
        draw.arc((255, 330, 545, 600), 180, 360, fill="#FFFFFFAA", width=18)
        draw.arc((305, 365, 495, 550), 180, 360, fill="#FFFFFFAA", width=16)
    elif slug == "plant-decor":
        rounded_rectangle(draw, (310, 455, 490, 600), accent, 28)
        draw.ellipse((240, 255, 405, 420), fill="#5E8C61")
        draw.ellipse((395, 235, 560, 410), fill="#6FA871")
        draw.ellipse((320, 170, 480, 355), fill="#7FB678")
        draw.line((400, 455, 400, 280), fill=dark, width=12)
    elif slug == "storage":
        rounded_rectangle(draw, (240, 245, 560, 590), accent, 24)
        draw.line((240, 360, 560, 360), fill="#FFFFFF99", width=8)
        draw.line((400, 245, 400, 590), fill="#FFFFFF99", width=8)
        draw.ellipse((365, 400, 385, 420), fill=dark)
        draw.ellipse((415, 400, 435, 420), fill=dark)
    elif slug == "bedding":
        rounded_rectangle(draw, (190, 310, 610, 545), accent, 34)
        rounded_rectangle(draw, (225, 250, 395, 345), "#FFFFFFCC", 28)
        rounded_rectangle(draw, (405, 250, 575, 345), "#FFFFFFCC", 28)
        draw.rectangle((210, 545, 255, 600), fill=dark)
        draw.rectangle((545, 545, 590, 600), fill=dark)
    elif slug == "wall-decor":
        rounded_rectangle(draw, (250, 210, 550, 535), dark, 18)
        rounded_rectangle(draw, (275, 235, 525, 510), "#FFFFFF", 14)
        draw.polygon([(305, 475), (390, 360), (450, 430), (500, 330), (500, 485), (305, 485)], fill=accent)
        draw.ellipse((335, 275, 390, 330), fill=accent)
    else:
        draw.ellipse((260, 245, 425, 410), fill=accent)
        rounded_rectangle(draw, (390, 330, 540, 560), accent, 42)
        draw.arc((240, 430, 560, 620), 180, 360, fill=dark, width=16)


def generate_image(product: Product, destination: Path) -> None:
    background, accent, secondary = product_palette(product)
    image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((-160, -160, 350, 350), fill="#FFFFFF88")
    draw.ellipse((520, 520, 980, 980), fill="#FFFFFF66")
    draw_category_icon(draw, product.category.slug if product.category else "accessories", accent)

    title_font = font(44)
    meta_font = font(25)
    title_lines = wrap_text(draw, product.name, title_font, 660)
    y = 635
    for line in title_lines:
      draw.text(((IMAGE_SIZE - text_width(draw, line, title_font)) / 2, y), line, fill="#2F2A26", font=title_font)
      y += 52
    meta = product.category.name if product.category else "AI Room Decor"
    pill_width = text_width(draw, meta, meta_font) + 46
    rounded_rectangle(draw, ((IMAGE_SIZE - pill_width) // 2, 70, (IMAGE_SIZE + pill_width) // 2, 118), accent, 24)
    draw.text(((IMAGE_SIZE - text_width(draw, meta, meta_font)) / 2, 81), meta, fill=secondary, font=meta_font)
    image.save(destination, "PNG")


def seed_product_images() -> dict[str, int]:
    assert_development_database()
    root = storage_root()
    output_dir = root / OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        products = (
            db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.images), joinedload(Product.colors))
            .order_by(Product.id.asc())
            .all()
        )
        for product in products:
            if product.images:
                skipped += 1
                continue
            filename = f"{product.id}-{product.slug}.png"
            path = output_dir / filename
            if not path.exists():
                generate_image(product, path)
            db.add(
                ProductImage(
                    product_id=product.id,
                    image_url=f"/storage/products/{OUTPUT_DIRNAME}/{filename}",
                    alt_text=f"Ảnh minh họa sản phẩm {product.name}",
                    sort_order=0,
                    is_primary=True,
                )
            )
            created += 1
        db.commit()
        return {"products": len(products), "created": created, "skipped": skipped}
    finally:
        db.close()


if __name__ == "__main__":
    result = seed_product_images()
    print(
        "Product image seed completed: "
        f"{result['created']} created, {result['skipped']} skipped, {result['products']} products checked."
    )
