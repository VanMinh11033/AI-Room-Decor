import json
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Product, ProductImage
from app.services.reference_image_processing import (
    BACKGROUND_REMOVAL_TOLERANCE,
    MAX_REFERENCE_SIDE,
    TRIM_PADDING,
    analyze_reference_image,
    cap_dimensions,
    estimate_background_color,
    remove_uniform_background,
    trim_transparent,
)
from app.services.storage_service import ProductImageStorageService

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REFERENCE_ROOT = PROJECT_ROOT / "storage" / "product-references"
DEMO_MARKER = "/generated-demo/"

SUITABILITY_PREPARED = "PREPARED"
SUITABILITY_UNSUITABLE = "UNSUITABLE"
SUITABILITY_FAILED = "FAILED"

SOURCE_REAL = "REAL_CATALOG"
SOURCE_DEMO = "GENERATED_DEMO"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _image_sort_key(image: ProductImage) -> tuple[int, int]:
    return (0 if image.is_primary else 1, image.sort_order)


def _is_demo(image: ProductImage) -> bool:
    return DEMO_MARKER in image.image_url


class ProductReferencePreparationService:
    def __init__(
        self,
        db: Session,
        reference_root: Path | str | None = None,
        product_storage: ProductImageStorageService | None = None,
        max_side: int = MAX_REFERENCE_SIDE,
        background_tolerance: float = BACKGROUND_REMOVAL_TOLERANCE,
    ) -> None:
        self.db = db
        self.reference_root = Path(reference_root) if reference_root else DEFAULT_REFERENCE_ROOT
        self.product_storage = product_storage or ProductImageStorageService()
        self.max_side = max_side
        self.background_tolerance = background_tolerance
        self.reference_root.mkdir(parents=True, exist_ok=True)

    def prepare_all(self) -> list[dict]:
        products = (
            self.db.query(Product)
            .options(joinedload(Product.category), joinedload(Product.images))
            .order_by(Product.id)
            .all()
        )
        results = [self.prepare_product(product) for product in products]
        self._write_manifest(results)
        return results

    def prepare_product(self, product: Product) -> dict:
        images = sorted(product.images, key=_image_sort_key)
        real_images = [img for img in images if not _is_demo(img)]
        demo_images = [img for img in images if _is_demo(img)]
        candidates = real_images + demo_images

        first_entry: dict | None = None
        for image in candidates:
            source_type = SOURCE_DEMO if _is_demo(image) else SOURCE_REAL
            entry = self._prepare_from(product, image, source_type)
            if first_entry is None:
                first_entry = entry
            if entry["suitability_status"] == SUITABILITY_PREPARED:
                return entry

        if first_entry is not None:
            return first_entry
        return self._no_image_entry(product)

    def _prepare_from(self, product: Product, image: ProductImage, source_type: str) -> dict:
        base = {
            "product_id": product.id,
            "product_name": product.name,
            "source_image_url": image.image_url,
            "source_type": source_type,
            "source_format": None,
            "source_dimensions": None,
            "preprocessing_method": None,
            "suitability_status": None,
            "suitability_reason": None,
            "output_path": None,
            "output_width": None,
            "output_height": None,
            "has_alpha": False,
            "generated_at": _now_iso(),
        }

        path = self.product_storage.resolve(image.image_url)
        analysis = analyze_reference_image(path)
        base["source_format"] = analysis["detected_format"]
        if analysis["width"] is not None and analysis["height"] is not None:
            base["source_dimensions"] = f"{analysis['width']}x{analysis['height']}"

        if not analysis["decodable"]:
            base["suitability_status"] = SUITABILITY_FAILED
            base["suitability_reason"] = analysis["reason"] or "unreadable"
            return base

        if analysis["has_transparency"]:
            return self._finish_prepared(product, path, base, "already_transparent_trim", analysis["reason"])
        if analysis["background_removal_candidate"]:
            return self._finish_prepared(product, path, base, "uniform_background_flood_fill", analysis["reason"])

        base["suitability_status"] = SUITABILITY_UNSUITABLE
        base["suitability_reason"] = analysis["reason"] or "non-uniform background"
        return base

    def _finish_prepared(self, product: Product, path: Path, base: dict, method: str, reason: str) -> dict:
        try:
            with Image.open(path) as im:
                rgba = im.convert("RGBA")
                if method == "already_transparent_trim":
                    processed = rgba
                else:
                    background = estimate_background_color(rgba)
                    processed = remove_uniform_background(rgba, background, tolerance=self.background_tolerance)
                processed = trim_transparent(processed, padding=TRIM_PADDING)
                if processed is None:
                    base["suitability_status"] = SUITABILITY_UNSUITABLE
                    base["suitability_reason"] = "fully transparent after background removal"
                    return base
                processed = cap_dimensions(processed, self.max_side)
                output = self.reference_root / f"{product.id}.png"
                processed.save(output, format="PNG")
                base["preprocessing_method"] = method
                base["suitability_status"] = SUITABILITY_PREPARED
                base["suitability_reason"] = reason or "ok"
                base["output_path"] = str(Path("storage") / "product-references" / f"{product.id}.png").replace("\\", "/")
                base["output_width"], base["output_height"] = processed.size
                base["has_alpha"] = True
                return base
        except Exception as exc:
            base["suitability_status"] = SUITABILITY_FAILED
            base["suitability_reason"] = f"processing error: {str(exc)[:120]}"
            return base

    def _no_image_entry(self, product: Product) -> dict:
        return {
            "product_id": product.id,
            "product_name": product.name,
            "source_image_url": None,
            "source_type": None,
            "source_format": None,
            "source_dimensions": None,
            "preprocessing_method": None,
            "suitability_status": SUITABILITY_UNSUITABLE,
            "suitability_reason": "no image",
            "output_path": None,
            "output_width": None,
            "output_height": None,
            "has_alpha": False,
            "generated_at": _now_iso(),
        }

    def _write_manifest(self, results: list[dict]) -> Path:
        manifest = {
            "generated_at": _now_iso(),
            "output_directory": str(self.reference_root),
            "total_products": len(results),
            "products": results,
        }
        manifest_path = self.reference_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest_path


def _print_report(results: list[dict], manifest_path: Path) -> None:
    real_prepared = [e for e in results if e["source_type"] == SOURCE_REAL and e["suitability_status"] == SUITABILITY_PREPARED]
    demo_prepared = [e for e in results if e["source_type"] == SOURCE_DEMO and e["suitability_status"] == SUITABILITY_PREPARED]
    unsuitable = [e for e in results if e["suitability_status"] == SUITABILITY_UNSUITABLE]
    failed = [e for e in results if e["suitability_status"] == SUITABILITY_FAILED]

    print("\nPRODUCT_ID\tPRODUCT_NAME\tSOURCE_TYPE\tSTATUS\tOUTPUT")
    for entry in results:
        source_type = entry["source_type"] or "-"
        output = entry["output_path"] or "-"
        print(f"{entry['product_id']}\t{entry['product_name']}\t{source_type}\t{entry['suitability_status']}\t{output}")

    print("\nSUMMARY")
    print(f"total_products: {len(results)}")
    print(f"REAL_CATALOG prepared: {len(real_prepared)}")
    print(f"GENERATED_DEMO prepared: {len(demo_prepared)}")
    print(f"unsuitable: {len(unsuitable)}")
    print(f"failed/unreadable: {len(failed)}")
    print(f"skipped (no image): {sum(1 for e in results if e['suitability_reason'] == 'no image')}")
    print(f"manifest: {manifest_path}")


def main() -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = ProductReferencePreparationService(db)
        results = service.prepare_all()
        manifest_path = service.reference_root / "manifest.json"
        _print_report(results, manifest_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
