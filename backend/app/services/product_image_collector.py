import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx
from PIL import Image
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Product
from app.services.openverse_provider import OpenverseImageSourceProvider
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

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STAGING_ROOT = PROJECT_ROOT / "storage" / "product-collected"

STATUS_DOWNLOADED = "DOWNLOADED"
STATUS_VALIDATED = "VALIDATED"
STATUS_SUITABLE = "SUITABLE"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"

MIN_WIDTH = 200
MIN_HEIGHT = 200
MIN_ASPECT = 0.25
MAX_ASPECT = 4.0

_EXTENSION_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".avif": "AVIF",
    ".gif": "GIF",
}
_FORMAT_TO_EXTENSION = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "AVIF": "avif",
    "GIF": "gif",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _extension_matches(url: str, detected_format: str) -> bool:
    suffix = Path(urlparse(url).path).suffix.lower()
    return _EXTENSION_TO_FORMAT.get(suffix) == detected_format


def build_search_phrase(product: Product) -> str:
    parts: list[str] = [product.name]
    parts += [s.name for s in product.styles]
    parts += [c.name for c in product.colors]
    parts += [m.name for m in product.materials]
    if product.category is not None:
        parts.append(product.category.name)
    parts += ["isolated product", "white background"]

    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(part)
    return " ".join(ordered)


class ProductImageSourceProvider:
    name: str

    def search(self, product: Product) -> list[Any]:
        raise NotImplementedError

    def download(self, url: str) -> tuple[bytes, str]:
        raise NotImplementedError


class ManualUrlProvider:
    name = "manual_url"

    def __init__(self, client_factory: Callable[[], Any] | None = None, timeout_seconds: int = 30) -> None:
        self._client_factory = client_factory
        self.timeout_seconds = timeout_seconds

    def search(self, product: Product) -> list[Any]:
        raise NotImplementedError("manual_url provider is manual-only and does not search")

    def download(self, url: str) -> tuple[bytes, str]:
        client = self._client_factory() if self._client_factory is not None else httpx.Client(
            timeout=self.timeout_seconds, follow_redirects=True
        )
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content, response.headers.get("content-type", "")
        finally:
            if self._client_factory is None:
                client.close()


def validate_image_bytes(data: bytes, content_type: str, url: str) -> dict:
    result = {
        "status": None,
        "reason": "",
        "detected_format": None,
        "width": None,
        "height": None,
        "file_hash": _sha256(data),
        "extension_matches_format": None,
    }

    if not (content_type or "").lower().startswith("image/"):
        result["status"] = STATUS_REJECTED
        result["reason"] = "non-image content-type"
        return result

    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
    except Exception as exc:
        result["status"] = STATUS_REJECTED
        result["reason"] = f"undecodable or corrupt: {str(exc)[:100]}"
        return result

    try:
        with Image.open(BytesIO(data)) as im:
            im.load()
            result["detected_format"] = im.format
            result["width"], result["height"] = im.size
    except Exception as exc:
        result["status"] = STATUS_REJECTED
        result["reason"] = f"decode error: {str(exc)[:100]}"
        return result

    if result["width"] < MIN_WIDTH or result["height"] < MIN_HEIGHT:
        result["status"] = STATUS_REJECTED
        result["reason"] = f"too small: {result['width']}x{result['height']}"
        return result

    ratio = result["width"] / result["height"]
    if ratio < MIN_ASPECT or ratio > MAX_ASPECT:
        result["status"] = STATUS_REJECTED
        result["reason"] = f"unreasonable aspect ratio: {ratio:.2f}"
        return result

    result["extension_matches_format"] = _extension_matches(url, result["detected_format"])
    result["status"] = STATUS_VALIDATED
    result["reason"] = "ok"
    return result


def preprocess_to_rgba(path: Path, output_path: Path, tolerance: float = BACKGROUND_REMOVAL_TOLERANCE) -> None:
    with Image.open(path) as im:
        rgba = im.convert("RGBA")

    analysis = analyze_reference_image(path)
    if analysis["has_transparency"]:
        processed = rgba
    else:
        background = estimate_background_color(rgba)
        processed = remove_uniform_background(rgba, background, tolerance=tolerance)

    processed = trim_transparent(processed, padding=TRIM_PADDING)
    if processed is None:
        raise ValueError("fully transparent after background removal")
    processed = cap_dimensions(processed, MAX_REFERENCE_SIDE)
    processed.save(output_path, format="PNG")


class CollectionService:
    def __init__(
        self,
        db: Session,
        staging_root: Path | str | None = None,
        provider: ProductImageSourceProvider | None = None,
        openverse_provider: OpenverseImageSourceProvider | None = None,
        background_tolerance: float = BACKGROUND_REMOVAL_TOLERANCE,
    ) -> None:
        self.db = db
        self.staging_root = Path(staging_root) if staging_root else DEFAULT_STAGING_ROOT
        self.provider = provider or ManualUrlProvider()
        self.openverse_provider = openverse_provider or OpenverseImageSourceProvider()
        self.background_tolerance = background_tolerance
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def _manifest_path(self) -> Path:
        return self.staging_root / "manifest.json"

    def _load_manifest(self) -> dict:
        path = self._manifest_path()
        if not path.exists():
            return {"generated_at": _now_iso(), "staging_directory": str(self.staging_root), "candidates": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict) -> None:
        manifest["generated_at"] = _now_iso()
        manifest["staging_directory"] = str(self.staging_root)
        self._manifest_path().write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def _append_record(self, record: dict) -> dict:
        manifest = self._load_manifest()
        manifest["candidates"].append(record)
        self._save_manifest(manifest)
        return record

    def _next_candidate_number(self, product_id: int) -> int:
        directory = self.staging_root / str(product_id)
        if not directory.exists():
            return 1
        existing = [p.name for p in directory.iterdir() if p.name.startswith("candidate-")]
        numbers = []
        for name in existing:
            stem = name.split(".")[0]
            digits = stem.replace("candidate-", "")
            if digits.isdigit():
                numbers.append(int(digits))
        return max(numbers, default=0) + 1

    def add_manual_candidate(
        self,
        product_id: int,
        image_url: str,
        source_name: str = "manual_url",
        source_page_url: str | None = None,
    ) -> dict:
        product = self.db.get(Product, product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        base = {
            "product_id": product_id,
            "product_name": product.name,
            "source_name": source_name,
            "source_page_url": source_page_url,
            "direct_image_url": image_url,
            "collected_at": _now_iso(),
        }

        try:
            data, content_type = self.provider.download(image_url)
        except Exception as exc:
            record = {
                **base,
                "candidate_id": None,
                "filename": None,
                "content_type": None,
                "file_hash": None,
                "status": STATUS_REJECTED,
                "detected_format": None,
                "width": None,
                "height": None,
                "extension_matches_format": None,
                "validation_reason": f"download failed: {str(exc)[:120]}",
                "suitability_reason": None,
                "processed_path": None,
            }
            return self._append_record(record)

        file_hash = _sha256(data)
        manifest = self._load_manifest()
        if any(candidate.get("file_hash") == file_hash for candidate in manifest["candidates"]):
            record = {
                **base,
                "candidate_id": None,
                "filename": None,
                "content_type": content_type,
                "file_hash": file_hash,
                "status": STATUS_REJECTED,
                "detected_format": None,
                "width": None,
                "height": None,
                "extension_matches_format": None,
                "validation_reason": "duplicate image hash",
                "suitability_reason": None,
                "processed_path": None,
            }
            return self._append_record(record)

        number = self._next_candidate_number(product_id)
        filename = f"candidate-{number:03d}.img"
        directory = self.staging_root / str(product_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(data)

        record = {
            **base,
            "candidate_id": f"{product_id}/{filename}",
            "filename": filename,
            "content_type": content_type,
            "file_hash": file_hash,
            "status": STATUS_DOWNLOADED,
            "detected_format": None,
            "width": None,
            "height": None,
            "extension_matches_format": None,
            "validation_reason": None,
            "suitability_reason": None,
            "processed_path": None,
        }
        return self._append_record(record)

    def validate_candidates(self) -> list[dict]:
        manifest = self._load_manifest()
        changed = False
        for record in manifest["candidates"]:
            if record["status"] != STATUS_DOWNLOADED:
                continue
            path = self.staging_root / str(record["product_id"]) / record["filename"]
            result = validate_image_bytes(path.read_bytes(), record["content_type"], record["direct_image_url"])
            record["detected_format"] = result["detected_format"]
            record["width"] = result["width"]
            record["height"] = result["height"]
            record["extension_matches_format"] = result["extension_matches_format"]
            record["validation_reason"] = result["reason"]

            if result["status"] == STATUS_REJECTED:
                record["status"] = STATUS_REJECTED
            else:
                record["status"] = STATUS_VALIDATED
                ext = _FORMAT_TO_EXTENSION.get(result["detected_format"], "img")
                new_filename = f"{record['filename'].rsplit('.', 1)[0]}.{ext}"
                if new_filename != record["filename"]:
                    old_path = path
                    new_path = old_path.with_name(new_filename)
                    old_path.rename(new_path)
                    record["filename"] = new_filename
                    record["candidate_id"] = f"{record['product_id']}/{new_filename}"
            changed = True

        if changed:
            self._save_manifest(manifest)
        return manifest["candidates"]

    def preprocess_candidates(self) -> list[dict]:
        manifest = self._load_manifest()
        changed = False
        for record in manifest["candidates"]:
            if record["status"] != STATUS_VALIDATED:
                continue
            path = self.staging_root / str(record["product_id"]) / record["filename"]
            analysis = analyze_reference_image(path)
            record["suitability_reason"] = analysis["reason"]
            if not analysis["background_removal_candidate"]:
                record["status"] = STATUS_REJECTED
                changed = True
                continue

            clean_filename = f"{record['filename'].rsplit('.', 1)[0]}.clean.png"
            clean_path = self.staging_root / str(record["product_id"]) / clean_filename
            try:
                preprocess_to_rgba(path, clean_path, tolerance=self.background_tolerance)
                record["processed_path"] = f"{record['product_id']}/{clean_filename}"
                record["status"] = STATUS_SUITABLE
            except Exception as exc:
                record["status"] = STATUS_REJECTED
                record["suitability_reason"] = f"preprocess error: {str(exc)[:100]}"
            changed = True

        if changed:
            self._save_manifest(manifest)
        return manifest["candidates"]

    def approve_candidate(self, candidate_id: str) -> dict:
        manifest = self._load_manifest()
        for record in manifest["candidates"]:
            if record["candidate_id"] == candidate_id:
                if record["status"] != STATUS_SUITABLE:
                    raise ValueError(f"Candidate {candidate_id} is not SUITABLE")
                record["status"] = STATUS_APPROVED
                self._save_manifest(manifest)
                return record
        raise ValueError(f"Candidate {candidate_id} not found")

    def list_candidates(self) -> list[dict]:
        return self._load_manifest()["candidates"]

    def audit_products(self) -> list[dict]:
        products = (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.materials),
                joinedload(Product.styles),
                joinedload(Product.colors),
                joinedload(Product.room_types),
            )
            .order_by(Product.id)
            .all()
        )
        manifest = self._load_manifest()
        approved = {record["product_id"] for record in manifest["candidates"] if record["status"] == STATUS_APPROVED}
        rows = []
        for product in products:
            rows.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "search_phrase": build_search_phrase(product),
                    "has_approved_real": product.id in approved,
                }
            )
        return rows

    def _load_product(self, product_id: int) -> Product:
        product = (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.materials),
                joinedload(Product.styles),
                joinedload(Product.colors),
                joinedload(Product.room_types),
            )
            .filter(Product.id == product_id)
            .first()
        )
        if product is None:
            raise ValueError(f"Product {product_id} not found")
        return product

    def collect_openverse(self, product_id: int, max_downloads: int = 3) -> list[dict]:
        product = self._load_product(product_id)
        candidates = self.openverse_provider.search(product)
        results: list[dict] = []

        for candidate in candidates:
            if candidate.get("semantic_decision") == "REJECT":
                record = self._openverse_semantic_reject_record(product, candidate)
                self._append_record(record)
                results.append(record)
            elif candidate["license_decision"] != "ACCEPTED":
                record = self._openverse_review_record(product, candidate)
                self._append_record(record)
                results.append(record)

        downloaded = 0
        for candidate in candidates:
            if candidate.get("semantic_decision") == "REJECT":
                continue
            if candidate["license_decision"] != "ACCEPTED":
                continue
            if downloaded >= max_downloads:
                break
            record = self._download_openverse_candidate(product, candidate)
            self._append_record(record)
            results.append(record)
            downloaded += 1
        return results

    def _openverse_review_record(self, product: Product, candidate: dict) -> dict:
        return {
            "product_id": product.id,
            "product_name": product.name,
            "source_name": "openverse",
            "source_page_url": candidate.get("source_page"),
            "direct_image_url": candidate.get("direct_image_url"),
            "openverse_id": candidate.get("openverse_id"),
            "query": candidate.get("query"),
            "title": candidate.get("title"),
            "creator": candidate.get("creator"),
            "creator_url": candidate.get("creator_url"),
            "source": candidate.get("source"),
            "license": candidate.get("license"),
            "license_version": candidate.get("license_version"),
            "license_url": candidate.get("license_url"),
            "attribution": candidate.get("attribution"),
            "thumbnail_url": candidate.get("thumbnail_url"),
            "filetype": candidate.get("filetype"),
            "license_decision": candidate.get("license_decision"),
            "rank_score": candidate.get("rank_score"),
            "semantic_decision": candidate.get("semantic_decision"),
            "semantic_score": candidate.get("semantic_score"),
            "semantic_reason": candidate.get("semantic_reason"),
            "collected_at": _now_iso(),
            "candidate_id": None,
            "filename": None,
            "content_type": None,
            "file_hash": None,
            "status": "LICENSE_REVIEW_REQUIRED",
            "detected_format": None,
            "width": candidate.get("width"),
            "height": candidate.get("height"),
            "extension_matches_format": None,
            "validation_reason": None,
            "suitability_reason": None,
            "processed_path": None,
        }

    def _openverse_semantic_reject_record(self, product: Product, candidate: dict) -> dict:
        return {
            "product_id": product.id,
            "product_name": product.name,
            "source_name": "openverse",
            "source_page_url": candidate.get("source_page"),
            "direct_image_url": candidate.get("direct_image_url"),
            "openverse_id": candidate.get("openverse_id"),
            "query": candidate.get("query"),
            "title": candidate.get("title"),
            "creator": candidate.get("creator"),
            "creator_url": candidate.get("creator_url"),
            "source": candidate.get("source"),
            "license": candidate.get("license"),
            "license_version": candidate.get("license_version"),
            "license_url": candidate.get("license_url"),
            "attribution": candidate.get("attribution"),
            "thumbnail_url": candidate.get("thumbnail_url"),
            "filetype": candidate.get("filetype"),
            "license_decision": candidate.get("license_decision"),
            "rank_score": candidate.get("rank_score"),
            "semantic_decision": candidate.get("semantic_decision"),
            "semantic_score": candidate.get("semantic_score"),
            "semantic_reason": candidate.get("semantic_reason"),
            "collected_at": _now_iso(),
            "candidate_id": None,
            "filename": None,
            "content_type": None,
            "file_hash": None,
            "status": STATUS_REJECTED,
            "detected_format": None,
            "width": candidate.get("width"),
            "height": candidate.get("height"),
            "extension_matches_format": None,
            "validation_reason": candidate.get("semantic_reason"),
            "suitability_reason": None,
            "processed_path": None,
        }

    def _download_openverse_candidate(self, product: Product, candidate: dict) -> dict:
        base = {
            "product_id": product.id,
            "product_name": product.name,
            "source_name": "openverse",
            "source_page_url": candidate.get("source_page"),
            "direct_image_url": candidate.get("direct_image_url"),
            "openverse_id": candidate.get("openverse_id"),
            "query": candidate.get("query"),
            "title": candidate.get("title"),
            "creator": candidate.get("creator"),
            "creator_url": candidate.get("creator_url"),
            "source": candidate.get("source"),
            "license": candidate.get("license"),
            "license_version": candidate.get("license_version"),
            "license_url": candidate.get("license_url"),
            "attribution": candidate.get("attribution"),
            "thumbnail_url": candidate.get("thumbnail_url"),
            "filetype": candidate.get("filetype"),
            "license_decision": candidate.get("license_decision"),
            "rank_score": candidate.get("rank_score"),
            "semantic_decision": candidate.get("semantic_decision"),
            "semantic_score": candidate.get("semantic_score"),
            "semantic_reason": candidate.get("semantic_reason"),
            "collected_at": _now_iso(),
        }
        try:
            data, content_type = self.openverse_provider.download(candidate["direct_image_url"])
        except Exception as exc:
            return {
                **base,
                "candidate_id": None,
                "filename": None,
                "content_type": None,
                "file_hash": None,
                "status": STATUS_REJECTED,
                "detected_format": None,
                "width": candidate.get("width"),
                "height": candidate.get("height"),
                "extension_matches_format": None,
                "validation_reason": f"download failed: {str(exc)[:120]}",
                "suitability_reason": None,
                "processed_path": None,
            }

        file_hash = _sha256(data)
        manifest = self._load_manifest()
        if any(record.get("file_hash") == file_hash for record in manifest["candidates"]):
            return {
                **base,
                "candidate_id": None,
                "filename": None,
                "content_type": content_type,
                "file_hash": file_hash,
                "status": STATUS_REJECTED,
                "detected_format": None,
                "width": candidate.get("width"),
                "height": candidate.get("height"),
                "extension_matches_format": None,
                "validation_reason": "duplicate image hash",
                "suitability_reason": None,
                "processed_path": None,
            }

        number = self._next_candidate_number(product.id)
        filename = f"candidate-{number:03d}.img"
        directory = self.staging_root / str(product.id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_bytes(data)

        return {
            **base,
            "candidate_id": f"{product.id}/{filename}",
            "filename": filename,
            "content_type": content_type,
            "file_hash": file_hash,
            "status": STATUS_DOWNLOADED,
            "detected_format": None,
            "width": candidate.get("width"),
            "height": candidate.get("height"),
            "extension_matches_format": None,
            "validation_reason": None,
            "suitability_reason": None,
            "processed_path": None,
        }


def _print_candidates(candidates: list[dict]) -> None:
    print("\nID\tPRODUCT\tSTATUS\tSOURCE\tFILE\tFORMAT\tSIZE\tHASH")
    for record in candidates:
        size = f"{record['width']}x{record['height']}" if record["width"] else "-"
        print(
            f"{record['candidate_id'] or '-'}\t{record['product_id']}\t{record['status']}\t"
            f"{record['source_name']}\t{record['filename'] or '-'}\t{record['detected_format'] or '-'}\t"
            f"{size}\t{(record['file_hash'] or '')[:12]}"
        )


def main(argv: list[str] | None = None) -> int:
    from app.core.database import SessionLocal

    parser = argparse.ArgumentParser(prog="product-image-collector")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("audit", help="List products needing real images and their search phrases")
    subparsers.add_parser("status", help="Show collection status")
    subparsers.add_parser("validate", help="Validate DOWNLOADED candidates")
    subparsers.add_parser("preprocess", help="Analyze and preprocess VALIDATED candidates")

    add_url = subparsers.add_parser("add-url", help="Add a manual URL candidate")
    add_url.add_argument("--product-id", type=int, required=True)
    add_url.add_argument("--image-url", required=True)
    add_url.add_argument("--page-url", default=None)
    add_url.add_argument("--source", default="manual_url")

    approve = subparsers.add_parser("approve", help="Approve a SUITABLE candidate")
    approve.add_argument("--id", required=True, help="candidate_id")

    collect = subparsers.add_parser("collect", help="Search Openverse, download, validate, and preprocess candidates")
    collect.add_argument("--product-id", type=int, required=True)
    collect.add_argument("--max-downloads", type=int, default=3)

    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        if args.command == "audit":
            rows = service.audit_products()
            print("PRODUCT_ID\tPRODUCT_NAME\tHAS_APPROVED_REAL\tSEARCH_PHRASE")
            for row in rows:
                print(f"{row['product_id']}\t{row['product_name']}\t{row['has_approved_real']}\t{row['search_phrase']}")
        elif args.command == "status":
            _print_candidates(service.list_candidates())
        elif args.command == "add-url":
            record = service.add_manual_candidate(args.product_id, args.image_url, args.source, args.page_url)
            print(json.dumps(record, indent=2, ensure_ascii=False))
        elif args.command == "validate":
            _print_candidates(service.validate_candidates())
        elif args.command == "preprocess":
            _print_candidates(service.preprocess_candidates())
        elif args.command == "approve":
            record = service.approve_candidate(args.id)
            print(json.dumps(record, indent=2, ensure_ascii=False))
        elif args.command == "collect":
            service.collect_openverse(args.product_id, max_downloads=args.max_downloads)
            service.validate_candidates()
            _print_candidates(service.preprocess_candidates())
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
