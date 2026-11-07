"""Phase 10C Stage 2B — modern catalog image sourcing pilot (offline-safe driver).

Stages candidates for products 1, 3, 6 and 13 into a *separate* catalog-v3
directory. The pilot is read-only against the database: it loads products but
never writes ProductImage rows, never promotes candidates, and never overwrites
existing images. Promotion is a separate, human-approved step.

Safety:
  - All paths resolve from __file__, never from the current working directory.
  - Download size is capped at 15 MB; format and resolution are validated;
    SHA-256 dedup prevents storing the same bytes twice.
  - Providers with missing keys are skipped (noted) and no credentials are used.
  - Existing V2/V3 outputs are never overwritten.
"""

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.product_image_collector import validate_image_bytes  # noqa: E402
from app.services.semantic_filter import derive_object_rule, semantic_assess  # noqa: E402
from app.services.stock_image_providers import (  # noqa: E402
    MAX_DOWNLOAD_BYTES,
    StockImageProvider,
    UpstreamRequestError,
    build_providers,
)

PRODUCT_IDS = [1, 3, 6, 13]
# Openverse is a free, key-less image source with per-result license metadata
# (CC0/PDM/CC BY/CC BY-SA accepted; NC/ND rejected). No paid API is used.
PILOT_PROVIDER_NAMES = ["openverse"]
MAX_DOWNLOADS_PER_PRODUCT = 3
# Openverse images are often 500-1024px; 500 keeps review-sized photos while
# still rejecting tiny thumbnails.
MIN_SIDE = 500
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

STAGING_ROOT = PROJECT_ROOT / "storage" / "products" / "catalog-v3"
MANUAL_IMPORT_FILENAME = "manual-import.json"

_FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
_MANUAL_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _safe_error_summary(exc: Exception) -> str:
    if isinstance(exc, UpstreamRequestError):
        return str(exc)
    return type(exc).__name__


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_queries(product: Any) -> list[str]:
    name = (product.name or "").strip()
    category = (product.category.name if product.category else "").strip()
    colors = [c.name for c in (product.colors or [])]
    styles = [s.name for s in (product.styles or [])]

    queries: list[str] = []
    if name:
        queries.append(name)
    if category:
        queries.append(f"modern {category}")
    if colors and category:
        queries.append(f"{colors[0].lower()} {category.lower()}")
    if styles and category:
        queries.append(f"{styles[0].lower()} {category.lower()}")

    seen: set[str] = set()
    ordered: list[str] = []
    for q in queries:
        key = q.lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append(q)
    return ordered


def _load_manifest(staging_root: Path) -> dict:
    path = staging_root / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"generated_at": _now_iso(), "staging_directory": str(staging_root), "candidates": []}


def _save_manifest(staging_root: Path, manifest: dict) -> None:
    manifest["generated_at"] = _now_iso()
    manifest["staging_directory"] = str(staging_root)
    (staging_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _downloaded_count(manifest: dict, product_id: int) -> int:
    return sum(
        1
        for c in manifest["candidates"]
        if c.get("product_id") == product_id and c.get("filename")
    )


def _next_seq(directory: Path) -> int:
    if not directory.exists():
        return 1
    numbers = []
    for p in directory.iterdir():
        stem = p.name.split(".")[0]
        if stem.startswith("candidate-") and stem[len("candidate-"):].isdigit():
            numbers.append(int(stem[len("candidate-"):]))
    return max(numbers, default=0) + 1


def _record(manifest: dict, product: Any, candidate: dict, status: str, rejection_reason: str | None) -> None:
    candidate["product_id"] = product.id
    candidate["product_name"] = product.name
    candidate["status"] = status
    candidate["rejection_reason"] = rejection_reason
    candidate.setdefault("filename", None)
    candidate.setdefault("file_hash", None)
    candidate.setdefault("content_type", None)
    candidate.setdefault("detected_format", None)
    candidate.setdefault("collected_at", _now_iso())
    candidate.setdefault("requires_review", False)
    manifest["candidates"].append(candidate)


def _stage_bytes(
    manifest: dict,
    product: Any,
    candidate: dict,
    data: bytes,
    content_type: str,
    reference_name: str,
    staging_root: Path,
    min_side: int,
) -> None:
    if len(data) > MAX_DOWNLOAD_BYTES:
        _record(manifest, product, candidate, "REJECTED", "exceeds 15 MB limit")
        return

    file_hash = _sha256(data)
    if any(c.get("file_hash") == file_hash for c in manifest["candidates"]):
        _record(manifest, product, candidate, "REJECTED", "duplicate image hash")
        return

    result = validate_image_bytes(data, content_type, reference_name)
    candidate["detected_format"] = result["detected_format"]
    candidate["width"] = result["width"]
    candidate["height"] = result["height"]

    if result["status"] != "VALIDATED":
        _record(manifest, product, candidate, "REJECTED", result["reason"])
        return
    if result["detected_format"] not in ALLOWED_FORMATS:
        _record(manifest, product, candidate, "REJECTED", f"unsupported format: {result['detected_format']}")
        return
    if (result["width"] or 0) < min_side or (result["height"] or 0) < min_side:
        _record(
            manifest,
            product,
            candidate,
            "REJECTED",
            f"below {min_side}x{min_side}: {result['width']}x{result['height']}",
        )
        return

    ext = _FORMAT_TO_EXT[result["detected_format"]]
    directory = staging_root / "candidates" / str(product.id)
    directory.mkdir(parents=True, exist_ok=True)
    seq = _next_seq(directory)
    filename = f"candidate-{seq:03d}.{ext}"
    (directory / filename).write_bytes(data)

    candidate["candidate_id"] = f"{product.id}/{filename}"
    candidate["filename"] = filename
    candidate["file_hash"] = file_hash
    candidate["content_type"] = content_type
    candidate["requires_review"] = True
    _record(manifest, product, candidate, "DOWNLOADED", None)


def _stage_download(
    manifest: dict,
    provider: StockImageProvider,
    product: Any,
    candidate: dict,
    staging_root: Path,
    min_side: int,
) -> None:
    url = candidate.get("direct_image_url")
    if not url:
        _record(manifest, product, candidate, "REJECTED", "missing direct image url")
        return

    try:
        data, content_type = provider.download(url)
    except Exception as exc:  # noqa: BLE001 - record failure, never crash the pilot
        _record(manifest, product, candidate, "REJECTED", f"download failed: {str(exc)[:120]}")
        return

    _stage_bytes(manifest, product, candidate, data, content_type, url, staging_root, min_side)


def _stage_local_file(
    manifest: dict,
    product: Any,
    candidate: dict,
    source_path: Path,
    staging_root: Path,
    min_side: int,
) -> None:
    try:
        data = source_path.read_bytes()
    except OSError as exc:  # noqa: BLE001
        _record(manifest, product, candidate, "REJECTED", f"read failed: {str(exc)[:120]}")
        return

    content_type = _MANUAL_CONTENT_TYPES.get(source_path.suffix.lower(), "image/jpeg")
    _stage_bytes(manifest, product, candidate, data, content_type, source_path.name, staging_root, min_side)


def run_pilot(
    db,
    staging_root: Path | str,
    providers: list[StockImageProvider],
    product_ids: list[int] = PRODUCT_IDS,
    max_downloads: int = MAX_DOWNLOADS_PER_PRODUCT,
    min_side: int = MIN_SIDE,
) -> dict:
    from sqlalchemy.orm import joinedload

    from app.models.entities import Product

    staging_root = Path(staging_root)
    staging_root.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(staging_root)

    for pid in product_ids:
        product = (
            db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.colors),
                joinedload(Product.styles),
                joinedload(Product.materials),
            )
            .filter(Product.id == pid)
            .first()
        )
        if product is None:
            continue

        rule = derive_object_rule(product)
        queries = build_queries(product)

        for provider in providers:
            if not provider.enabled():
                print(f"  [skip] provider '{provider.name}' disabled (missing API key)")
                continue

            try:
                results = provider.search(product, queries)
            except Exception as exc:  # noqa: BLE001 - isolate per-product provider failures
                print(
                    f"  [error] provider '{provider.name}' search failed for product {pid}: "
                    f"{_safe_error_summary(exc)}"
                )
                continue

            for candidate in results:
                assessed = semantic_assess(candidate, rule)
                candidate["semantic_decision"] = assessed["semantic_decision"]
                candidate["semantic_score"] = assessed["semantic_score"]
                candidate["semantic_reason"] = assessed["semantic_reason"]

                if assessed["semantic_decision"] == "REJECT":
                    _record(manifest, product, candidate, "SEMANTIC_REJECT", assessed["semantic_reason"])
                    continue
                if candidate.get("license_decision") != "ACCEPTED":
                    _record(
                        manifest,
                        product,
                        candidate,
                        "LICENSE_REJECT",
                        f"license not accepted: {candidate.get('license')}",
                    )
                    continue
                if _downloaded_count(manifest, product.id) >= max_downloads:
                    _record(manifest, product, candidate, "LIMIT_REACHED", "download limit reached")
                    continue

                _stage_download(manifest, provider, product, candidate, staging_root, min_side)

    _save_manifest(staging_root, manifest)
    return manifest


def _resolve_staging_root(base: Path) -> Path:
    """Return a fresh staging directory, versioning away from existing results."""
    if not (base / "manifest.json").exists() and not (base / "catalog-v3-pilot-review.jpg").exists():
        return base
    index = 2
    while True:
        candidate = base.with_name(f"{base.name}-{index}")
        if not (candidate / "manifest.json").exists() and not (candidate / "catalog-v3-pilot-review.jpg").exists():
            return candidate
        index += 1


def _resolve_image_path(staging_root: Path, image_path: str) -> Path:
    path = Path(image_path)
    return path if path.is_absolute() else staging_root / path


def ingest_manual_images(
    db,
    staging_root: Path | str,
    min_side: int = MIN_SIDE,
) -> dict:
    """Stage manually-supplied product images listed in ``manual-import.json``.

    Each entry is ``{product_id, image_path, source_url?, license?, license_url?,
    attribution?}``. Files are copied into the staging ``candidates/`` directory
    with ``requires_review=True``; nothing is written to the database.
    """
    from sqlalchemy.orm import joinedload

    from app.models.entities import Product

    staging_root = Path(staging_root)
    spec_path = staging_root / MANUAL_IMPORT_FILENAME
    manifest = _load_manifest(staging_root)
    if not spec_path.exists():
        return manifest

    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    for entry in spec.get("images") or []:
        product_id = entry.get("product_id")
        image_path = entry.get("image_path")
        if not product_id or not image_path:
            continue

        product = (
            db.query(Product)
            .options(joinedload(Product.category))
            .filter(Product.id == product_id)
            .first()
        )
        if product is None:
            continue

        source_path = _resolve_image_path(staging_root, image_path)
        license_name = entry.get("license") or "UNKNOWN"
        candidate = {
            "id": f"manual-{product_id}-{Path(image_path).name}",
            "source": "manual",
            "query": "manual",
            "title": Path(image_path).name,
            "creator": entry.get("attribution") or "",
            "creator_url": None,
            "license": license_name,
            "license_url": entry.get("license_url"),
            "license_decision": "ACCEPTED" if entry.get("license") else "REVIEW_REQUIRED",
            "page_url": entry.get("source_url"),
            "direct_image_url": str(source_path),
            "width": None,
            "height": None,
            "tags": [],
            "attribution": entry.get("attribution") or "",
        }

        if _downloaded_count(manifest, product_id) >= MAX_DOWNLOADS_PER_PRODUCT:
            _record(manifest, product, candidate, "LIMIT_REACHED", "download limit reached")
            continue

        _stage_local_file(manifest, product, candidate, source_path, staging_root, min_side)

    _save_manifest(staging_root, manifest)
    return manifest


def build_contact_sheet(manifest: dict, staging_root: Path | str, output_path: Path | str) -> None:
    staging_root = Path(staging_root)
    rows = [c for c in manifest["candidates"] if c.get("filename")]
    rows.sort(key=lambda c: (c.get("product_id", 0), c.get("filename") or ""))

    header_font = _load_font(18)
    title_font = _load_font(15)
    body_font = _load_font(13)

    pad = 12
    img_size = 200
    text_x = pad + img_size + pad
    text_w = 760
    row_h = 224
    header_h = 44

    width = pad + img_size + pad + text_w + pad
    height = header_h + max(len(rows), 1) * row_h + pad

    sheet = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 14), "Phase 10C catalog-v3 pilot review", fill=(20, 20, 20), font=header_font)

    if not rows:
        draw.text((pad, header_h + 20), "No downloaded candidates to display.", fill=(120, 120, 120), font=body_font)

    for index, record in enumerate(rows):
        y = header_h + index * row_h
        draw.rectangle((pad, y, pad + img_size, y + img_size), outline=(180, 180, 180))

        image_path = staging_root / "candidates" / str(record["product_id"]) / record["filename"]
        if image_path.exists():
            try:
                thumb = Image.open(image_path).convert("RGB")
                thumb.thumbnail((img_size - 4, img_size - 4))
                sheet.paste(thumb, (pad + 2, y + 2))
            except Exception as exc:  # noqa: BLE001
                draw.text((pad + 6, y + 10), f"open error: {exc}", fill=(200, 0, 0), font=body_font)
        else:
            draw.text((pad + 6, y + 10), "image missing", fill=(200, 0, 0), font=body_font)

        semantic = record.get("semantic_decision") or "-"
        score = record.get("semantic_score")
        license_code = record.get("license") or "-"
        status = record.get("status") or "-"
        reason = record.get("rejection_reason") or ""

        lines = [
            (f"#{record['product_id']}  {record.get('product_name') or ''}", title_font),
            (f"Title: {(record.get('title') or '')[:90]}", body_font),
            (f"Semantic: {semantic} (score {score})", body_font),
            (f"License: {license_code}", body_font),
            (f"Status: {status} - {reason[:60]}", body_font),
        ]
        line_y = y + 10
        for text, font in lines:
            draw.text((text_x, line_y), text, fill=(20, 20, 20), font=font)
            line_y += 34

    sheet.save(output_path, format="JPEG", quality=90)


def main(argv: list[str] | None = None) -> int:
    from app.core.database import SessionLocal

    staging_root = _resolve_staging_root(STAGING_ROOT)
    contact_sheet_path = staging_root / "catalog-v3-pilot-review.jpg"

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Staging root: {staging_root}")
    print(f"Product IDs: {PRODUCT_IDS}")
    print(f"Contact sheet: {contact_sheet_path}")

    providers = build_providers(only_names=PILOT_PROVIDER_NAMES)
    enabled = [p.name for p in providers if p.enabled()]
    print(f"Enabled providers: {enabled if enabled else '(none — manual import mode)'}")

    db = SessionLocal()
    try:
        manifest = run_pilot(db, staging_root, providers)
        manifest = ingest_manual_images(db, staging_root)
        records = manifest["candidates"]
        print(f"Total records: {len(records)}")
        by_product: dict[int, Counter] = {}
        for r in records:
            by_product.setdefault(r["product_id"], Counter())[r["status"]] += 1
        for pid in sorted(by_product):
            print(f"  product {pid}: {dict(by_product[pid])}")
        downloaded = [r for r in records if r.get("filename")]
        print(f"Downloaded (with image file): {len(downloaded)}")

        build_contact_sheet(manifest, staging_root, contact_sheet_path)
        print(f"Contact sheet written to {contact_sheet_path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
