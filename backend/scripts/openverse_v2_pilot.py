"""Openverse V2 pilot for Phase 10B.5.

Collects real Openverse candidates for a fixed, limited set of products
(1, 3, 9, 12) into a *separate* V2 staging root so the existing V1 pilot
(storage/product-collected/) is never modified.

Safety contract:
  - Product IDs are hard-limited to [1, 3, 9, 12].
  - At most 3 downloaded candidates per product (semantic ACCEPT + license OK).
  - Semantic REJECT candidates are never downloaded (enforced by
    CollectionService.collect_openverse).
  - Read-only database access: products are loaded, never written.
  - No candidate is approved or promoted; no ProductImage rows are touched.
  - Stops immediately on HTTP 429 from Openverse.
  - Existing V2 outputs are never overwritten (script refuses to start if the
    V2 manifest or the contact sheet already exists).
  - All paths are resolved from __file__, never from the current working dir.
"""

import sys
from collections import Counter
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.openverse_provider import OpenverseImageSourceProvider  # noqa: E402
from app.services.product_image_collector import CollectionService  # noqa: E402

PRODUCT_IDS = [1, 3, 9, 12]
MAX_DOWNLOADS_PER_PRODUCT = 3

V2_STAGING_ROOT = PROJECT_ROOT / "storage" / "product-collected-v2"
V2_MANIFEST_PATH = V2_STAGING_ROOT / "manifest.json"
CONTACT_SHEET_PATH = (
    PROJECT_ROOT / "storage" / "product-collected" / "openverse-pilot-review-v2.jpg"
)

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _print_summary(records: list[dict]) -> None:
    by_product: dict[int, list[dict]] = {}
    for record in records:
        by_product.setdefault(record["product_id"], []).append(record)

    for product_id in sorted(by_product):
        recs = by_product[product_id]
        statuses = Counter(record["status"] for record in recs)
        print(f"  product {product_id}: {len(recs)} records, statuses={dict(statuses)}")

    downloaded = [record for record in records if record.get("filename")]
    print(f"  downloaded candidates with image file: {len(downloaded)}")


def _build_contact_sheet(records: list[dict], staging_root: Path, output_path: Path) -> None:
    rows = [record for record in records if record.get("filename")]
    rows.sort(key=lambda r: (r["product_id"], r.get("filename") or ""))

    header_font = _load_font(18)
    title_font = _load_font(15)
    body_font = _load_font(13)

    pad = 12
    img_size = 200
    text_x = pad + img_size + pad
    text_w = 764
    row_h = 224
    header_h = 44

    width = pad + img_size + pad + text_w + pad
    height = header_h + max(len(rows), 1) * row_h + pad

    sheet = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (pad, 14),
        "Openverse V2 Pilot Review - Products 1, 3, 9, 12",
        fill=(20, 20, 20),
        font=header_font,
    )

    if not rows:
        draw.text(
            (pad, header_h + 20),
            "No downloaded candidates to display.",
            fill=(120, 120, 120),
            font=body_font,
        )

    for index, record in enumerate(rows):
        y = header_h + index * row_h
        draw.rectangle((pad, y, pad + img_size, y + img_size), outline=(180, 180, 180))

        image_path = staging_root / str(record["product_id"]) / record["filename"]
        if image_path.exists():
            try:
                thumb = Image.open(image_path).convert("RGB")
                thumb.thumbnail((img_size - 4, img_size - 4))
                sheet.paste(thumb, (pad + 2, y + 2))
            except Exception as exc:  # noqa: BLE001 - keep sheet rendering resilient
                draw.text((pad + 6, y + 10), f"open error: {exc}", fill=(200, 0, 0), font=body_font)
        else:
            draw.text((pad + 6, y + 10), "image missing", fill=(200, 0, 0), font=body_font)

        product_name = record.get("product_name") or ""
        title = record.get("title") or ""
        semantic_decision = record.get("semantic_decision") or "-"
        semantic_score = record.get("semantic_score")
        license_code = record.get("license") or "-"
        status = record.get("status") or "-"
        reason = record.get("suitability_reason") or record.get("validation_reason") or ""

        lines = [
            (f"#{record['product_id']}  {product_name}", title_font),
            (f"Title: {title[:90]}", body_font),
            (f"Semantic: {semantic_decision} (score {semantic_score})", body_font),
            (f"License: {license_code}", body_font),
            (f"Suitability: {status} - {reason[:60]}", body_font),
        ]

        line_y = y + 10
        for text, font in lines:
            draw.text((text_x, line_y), text, fill=(20, 20, 20), font=font)
            line_y += 34

    sheet.save(output_path, format="JPEG", quality=90)


def main() -> int:
    if V2_MANIFEST_PATH.exists():
        print(f"ABORT: V2 manifest already exists at {V2_MANIFEST_PATH}. "
              f"Move it aside before running to avoid overwriting it.")
        return 2
    if CONTACT_SHEET_PATH.exists():
        print(f"ABORT: contact sheet already exists at {CONTACT_SHEET_PATH}. "
              f"Move it aside before running to avoid overwriting it.")
        return 2

    print(f"Project root: {PROJECT_ROOT}")
    print(f"V2 staging root: {V2_STAGING_ROOT}")
    print(f"Product IDs: {PRODUCT_IDS}")
    print(f"Contact sheet output: {CONTACT_SHEET_PATH}")

    db = SessionLocal()
    try:
        service = CollectionService(db, staging_root=V2_STAGING_ROOT)

        for product_id in PRODUCT_IDS:
            print(f"Collecting product {product_id} ...")
            try:
                service.collect_openverse(product_id, max_downloads=MAX_DOWNLOADS_PER_PRODUCT)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    print("ABORT: Openverse returned HTTP 429 (rate limited). Stopping pilot.")
                    return 2
                print(f"  WARNING: HTTP {exc.response.status_code} for product {product_id}: {exc}")
                continue

        print("Validating candidates ...")
        service.validate_candidates()
        print("Preprocessing candidates ...")
        service.preprocess_candidates()

        records = service.list_candidates()
        print(f"Total V2 records: {len(records)}")
        _print_summary(records)

        print("Building contact sheet ...")
        _build_contact_sheet(records, V2_STAGING_ROOT, CONTACT_SHEET_PATH)
        print(f"Contact sheet written to {CONTACT_SHEET_PATH}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
