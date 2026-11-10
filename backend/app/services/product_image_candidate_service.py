"""Admin-triggered product image candidate collection and review service.

Searches Google Images via the Custom Search JSON API, downloads real images into
a dedicated staging directory, and stores candidate metadata with a PENDING status
for admin review. Only approved candidates are promoted to ``ProductImage`` rows;
nothing is written to the catalog until approval.
"""

from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.entities import Product, ProductImage, ProductImageCandidate, ProductImageCandidateStatus
from app.services.google_images_provider import GoogleImagesProvider
from app.services.product_image_collector import validate_image_bytes
from app.services.stock_image_providers import MAX_DOWNLOAD_BYTES

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STAGING_ROOT = PROJECT_ROOT / "storage" / "products" / "candidate-staging"
STAGING_REL = "products/candidate-staging"

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_FORMAT_TO_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}

DEFAULT_MAX_IMAGES = 3
MAX_IMAGES_LIMIT = 5
MIN_SIDE = 400


def _sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


def _public_url(local_path: str | None) -> str:
    if not local_path:
        return ""
    raw = str(local_path).strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    cleaned = raw.replace("\\", "/").lstrip("/")
    if cleaned.startswith("storage/"):
        cleaned = cleaned[len("storage/"):].lstrip("/")

    local_file = (PROJECT_ROOT / "storage" / cleaned).resolve()
    if local_file.is_file():
        return f"/storage/{quote(cleaned, safe='/')}"

    if settings.cloudinary_cloud_name:
        folder = (settings.cloudinary_folder or "ai_room_decor").strip("/")
        encoded_path = quote(cleaned, safe="/")
        return f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/image/upload/{folder}/{encoded_path}"

    return f"/storage/{quote(cleaned, safe='/')}"


resolve_candidate_public_url = _public_url


class ProductImageCandidateService:
    def __init__(
        self,
        db: Session,
        staging_root: Path | str = STAGING_ROOT,
        provider: Any = None,
        min_side: int = MIN_SIDE,
    ) -> None:
        self.db = db
        self.staging_root = Path(staging_root)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.provider = provider or GoogleImagesProvider()
        self.min_side = min_side

    def search_and_stage(self, product_id: int, max_images: int = DEFAULT_MAX_IMAGES) -> dict:
        max_images = max(1, min(max_images, MAX_IMAGES_LIMIT))
        product = self._load_product(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")

        candidates = self.provider.search(product, None)
        staged = 0
        skipped = 0
        for candidate in candidates:
            if staged >= max_images:
                break
            if candidate.get("semantic_decision") == "REJECT":
                skipped += 1
                continue
            if candidate.get("license_decision") != "ACCEPTED":
                skipped += 1
                continue
            if self._url_seen(candidate.get("direct_image_url")):
                skipped += 1
                continue
            if self._download_and_stage(product, candidate):
                staged += 1
            else:
                skipped += 1
        return {"product_id": product_id, "staged": staged, "skipped": skipped}

    def list_candidates(
        self,
        product_id: int | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[ProductImageCandidate]]:
        query = self.db.query(ProductImageCandidate).options(joinedload(ProductImageCandidate.product))
        if product_id is not None:
            query = query.filter(ProductImageCandidate.product_id == product_id)
        if status:
            query = query.filter(ProductImageCandidate.status == status)
        total = query.count()
        items = (
            query.order_by(ProductImageCandidate.created_at.desc(), ProductImageCandidate.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return total, items

    def approve_candidate(self, candidate_id: int) -> ProductImageCandidate:
        candidate = self.db.get(ProductImageCandidate, candidate_id)
        if candidate is None:
            raise ValueError("Candidate not found")
        if candidate.status != ProductImageCandidateStatus.PENDING.value:
            raise ValueError("Candidate is not pending")
        product = self.db.get(Product, candidate.product_id)
        if product is None:
            raise ValueError("Product not found")

        existing = self.db.query(ProductImage).filter(ProductImage.product_id == product.id).all()
        self.db.add(
            ProductImage(
                product_id=product.id,
                image_url=_public_url(candidate.local_path),
                alt_text=product.name,
                sort_order=len(existing),
                is_primary=len(existing) == 0,
            )
        )
        candidate.status = ProductImageCandidateStatus.APPROVED.value
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def reject_candidate(self, candidate_id: int) -> ProductImageCandidate:
        candidate = self.db.get(ProductImageCandidate, candidate_id)
        if candidate is None:
            raise ValueError("Candidate not found")
        if candidate.status != ProductImageCandidateStatus.PENDING.value:
            raise ValueError("Candidate is not pending")
        candidate.status = ProductImageCandidateStatus.REJECTED.value
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def _load_product(self, product_id: int) -> Product | None:
        return (
            self.db.query(Product)
            .options(
                joinedload(Product.category),
                joinedload(Product.colors),
                joinedload(Product.styles),
                joinedload(Product.materials),
            )
            .filter(Product.id == product_id)
            .first()
        )

    def _url_seen(self, url: str | None) -> bool:
        if not url:
            return True
        return (
            self.db.query(ProductImageCandidate)
            .filter(ProductImageCandidate.image_url == url)
            .first()
            is not None
        )

    def _download_and_stage(self, product: Product, candidate: dict) -> bool:
        url = candidate.get("direct_image_url")
        if not url:
            return False
        try:
            data, content_type = self.provider.download(url)
        except Exception:  # noqa: BLE001 - reject this candidate, keep going
            return False
        if len(data) > MAX_DOWNLOAD_BYTES:
            return False

        file_hash = _sha256(data)
        if (
            self.db.query(ProductImageCandidate)
            .filter(ProductImageCandidate.file_hash == file_hash)
            .first()
            is not None
        ):
            return False

        result = validate_image_bytes(data, content_type, url)
        if result["status"] != "VALIDATED":
            return False
        if result["detected_format"] not in ALLOWED_FORMATS:
            return False
        if (result["width"] or 0) < self.min_side or (result["height"] or 0) < self.min_side:
            return False

        ext = _FORMAT_TO_EXT[result["detected_format"]]
        directory = self.staging_root / str(product.id)
        directory.mkdir(parents=True, exist_ok=True)
        seq = self._next_seq(directory)
        filename = f"candidate-{seq:03d}.{ext}"
        (directory / filename).write_bytes(data)

        self.db.add(
            ProductImageCandidate(
                product_id=product.id,
                source=candidate.get("source") or "openverse",
                source_page_url=candidate.get("source_page") or candidate.get("page_url"),
                image_url=url,
                local_path=f"{STAGING_REL}/{product.id}/{filename}",
                license=candidate.get("license"),
                license_url=candidate.get("license_url"),
                attribution=candidate.get("attribution"),
                creator=candidate.get("creator"),
                status=ProductImageCandidateStatus.PENDING.value,
                width=result["width"],
                height=result["height"],
                file_format=result["detected_format"],
                file_hash=file_hash,
                semantic_decision=candidate.get("semantic_decision"),
            )
        )
        self.db.commit()
        return True

    def _next_seq(self, directory: Path) -> int:
        if not directory.exists():
            return 1
        numbers = []
        for path in directory.iterdir():
            stem = path.name.split(".")[0]
            if stem.startswith("candidate-") and stem[len("candidate-"):].isdigit():
                numbers.append(int(stem[len("candidate-"):]))
        return max(numbers, default=0) + 1
