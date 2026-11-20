import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.ai.image.base import GeneratedImage, ImageProvider, ImageProviderError
from app.ai.image.composite_provider import CompositeImageProvider
from app.ai.image.prompt_builder import PROMPT_VERSION, build_design_generation_prompt
from app.models.entities import AIUsageLog, Product, ProductImage, RoomAnalysis, RoomDesignGeneration, RoomProject, User
from app.schemas.design_generation import DesignGenerationCreate
from app.services.ai_quota_service import AIQuotaService
from app.services.design_compositor import ISOLATED, classify_product_image
from app.services.recommendation_service import RecommendationService
from app.services.storage_service import (
    GeneratedDesignStorageService,
    ProductImageStorageService,
    RoomImageStorageService,
    validate_image_signature,
)

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = re.compile(
    r"(?:Bearer\s+[^\s,;]+|sk-[a-zA-Z0-9_\-]{8,}|AIza[0-9A-Za-z\-_]{20,}|(?:token|key|secret|password)=[^\s&,;]+|secret-[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)
_PATH_PATTERNS = re.compile(
    r"(?:[A-Za-z]:\\[^\s:\"\'<>]+\\|\/(?:tmp|home|var|app|storage|root)[^\s:\"\'<>]*)",
    re.IGNORECASE,
)


def _sanitize_error_message(message: str | None) -> str:
    if not message:
        return ""
    safe = _SECRET_PATTERNS.sub("[REDACTED]", str(message))
    safe = _PATH_PATTERNS.sub("[PATH]", safe)
    return safe[:500]


CATEGORY_REFERENCE_PRIORITY: dict[str, int] = {
    "sofa": 10,
    "bedding": 15,
    "storage": 20,
    "table": 30,
    "chair": 40,
    "rug": 50,
    "lighting": 60,
    "wall-decor": 70,
    "plant-decor": 80,
    "accessories": 90,
}
DEFAULT_REFERENCE_PRIORITY = 100


def get_category_reference_priority(product: Product) -> int:
    """Return an integer priority for allocating reference image slots. Lower is higher priority.

    Major anchor furniture pieces (sofa, bedding, storage, table) are prioritized
    over secondary seating, lighting, and smaller accessories.
    """
    category_slug = ""
    if getattr(product, "category", None):
        if getattr(product.category, "slug", None):
            category_slug = product.category.slug.strip().lower()
        elif getattr(product.category, "name", None):
            category_slug = product.category.name.strip().lower().replace(" ", "-")
    return CATEGORY_REFERENCE_PRIORITY.get(category_slug, DEFAULT_REFERENCE_PRIORITY)


class DesignGenerationService:
    def __init__(self, db: Session, image_provider: ImageProvider) -> None:
        self.db = db
        self.image_provider = image_provider

    def list_generations(self, current_user: User, project_id: int) -> tuple[int, list[RoomDesignGeneration]]:
        self._get_owned_project(current_user, project_id)
        query = (
            self.db.query(RoomDesignGeneration)
            .options(self._generation_load_options())
            .filter(RoomDesignGeneration.room_project_id == project_id, RoomDesignGeneration.user_id == current_user.id)
            .order_by(RoomDesignGeneration.created_at.desc(), RoomDesignGeneration.id.desc())
        )
        return query.count(), query.all()

    def get_latest_generation(self, current_user: User, project_id: int) -> RoomDesignGeneration:
        self._get_owned_project(current_user, project_id)
        generation = (
            self.db.query(RoomDesignGeneration)
            .options(self._generation_load_options())
            .filter(RoomDesignGeneration.room_project_id == project_id, RoomDesignGeneration.user_id == current_user.id)
            .order_by(RoomDesignGeneration.created_at.desc(), RoomDesignGeneration.id.desc())
            .first()
        )
        if generation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design generation not found")
        return generation

    def import_gemini_manual_design(
        self,
        current_user: User,
        project_id: int,
        file: UploadFile,
        product_ids: list[int],
        notes: str | None = None,
    ) -> RoomDesignGeneration:
        """
        Nhập ảnh thiết kế tạo thủ công từ ứng dụng Gemini (Google AI Pro).
        - Kiểm tra quyền sở hữu dự án phòng.
        - Kiểm tra dự án đã có ảnh phòng gốc.
        - Kiểm tra định dạng ảnh (PNG, JPG/JPEG) và kích thước (<= 15MB).
        - Kiểm tra chữ ký file hợp lệ.
        - Liên kết với ảnh phòng gốc và danh sách sản phẩm tham chiếu.
        - Gán trạng thái NEEDS_REVIEW, nhãn nguồn: 'Ảnh phối cảnh tạo bằng ứng dụng Gemini — nhập thủ công'.
        - Tuyệt đối không gọi Gemini API, không đánh dấu VERIFIED, không tốn chi phí API.
        """
        project = self._get_owned_project(current_user, project_id)
        if not project.room_image_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ROOM_IMAGE_REQUIRED")

        # 1. Kiểm tra định dạng file
        content_type = (file.content_type or "").lower()
        allowed_manual_types = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        expected_ext = allowed_manual_types.get(content_type)
        if expected_ext is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ hỗ trợ file ảnh định dạng PNG hoặc JPG/JPEG",
            )

        original_filename = Path(file.filename or "gemini-design.png").name
        file_ext = Path(original_filename).suffix.lower()
        if file_ext in (".jpeg", ".jpg"):
            file_ext = ".jpg"
        if file_ext not in (".png", ".jpg", ".webp"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phần mở rộng file không hợp lệ (chỉ chấp nhận .png, .jpg, .jpeg)",
            )

        # 2. Kiểm tra dung lượng & chữ ký file
        data = file.file.read()
        if not data or len(data) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File ảnh rỗng")

        max_size = 15 * 1024 * 1024  # 15 MB
        if len(data) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Dung lượng ảnh vượt quá giới hạn 15MB",
            )

        sig_content_type = "image/jpeg" if content_type == "image/jpg" else content_type
        if not validate_image_signature(data, file_ext, sig_content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dữ liệu file ảnh không hợp lệ hoặc bị lỗi chữ ký",
            )

        # 3. Kiểm tra sản phẩm tham chiếu
        if not product_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cần chọn ít nhất một sản phẩm catalog tham chiếu",
            )
        unique_product_ids = list(dict.fromkeys(product_ids))[:12]
        products = (
            self.db.query(Product)
            .filter(Product.id.in_(unique_product_ids), Product.is_active.is_(True))
            .all()
        )
        if not products:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy sản phẩm catalog hợp lệ cho các ID đã chọn",
            )

        # 4. Tạo bản ghi RoomDesignGeneration
        prompt_tag = (
            "[SOURCE: GEMINI_WEB_APP_MANUAL] "
            "[MODE: AI_PHOTOREALISTIC_PREVIEW] "
            "[STATUS: NEEDS_REVIEW] "
            "Ảnh phối cảnh tạo bằng ứng dụng Gemini — nhập thủ công"
        )
        if notes and notes.strip():
            prompt_tag += f" | Ghi chú: {notes.strip()[:200]}"

        generation = RoomDesignGeneration(
            room_project_id=project.id,
            user_id=current_user.id,
            status="GENERATING",
            provider="gemini_manual_import",
            model="gemini-web-app",
            prompt_version="manual-v1",
            source_image_path=project.room_image_path,
            prompt=prompt_tag,
            error_message="Ảnh phối cảnh tạo bằng ứng dụng Gemini — nhập thủ công",
            products=products,
        )
        self.db.add(generation)
        self.db.commit()
        self.db.refresh(generation)

        # 5. Lưu trữ ảnh vào storage
        try:
            save_content_type = "image/jpeg" if file_ext == ".jpg" else content_type
            stored = GeneratedDesignStorageService().save(
                data=data,
                content_type=save_content_type,
                user_id=current_user.id,
                project_id=project.id,
                generation_id=generation.id,
            )
            generation.generated_image_path = stored.storage_path
            generation.generated_image_url = stored.image_url
            generation.status = "COMPLETED"
            generation.completed_at = datetime.now(UTC)
            generation.latency_ms = 0
            self.db.commit()
            return self.get_generation(current_user, project.id, generation.id)
        except Exception as e:
            self.db.rollback()
            generation.status = "FAILED"
            generation.error_code = "MANUAL_IMPORT_STORAGE_FAILED"
            generation.error_message = _sanitize_error_message(str(e))
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể lưu trữ ảnh thiết kế: {str(e)}",
            )

    def get_generation(self, current_user: User, project_id: int, generation_id: int) -> RoomDesignGeneration:
        self._get_owned_project(current_user, project_id)
        generation = (
            self.db.query(RoomDesignGeneration)
            .options(self._generation_load_options())
            .filter(
                RoomDesignGeneration.id == generation_id,
                RoomDesignGeneration.room_project_id == project_id,
                RoomDesignGeneration.user_id == current_user.id,
            )
            .first()
        )
        if generation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design generation not found")
        return generation

    def _compute_checksum(self, file_path: str | Path | None) -> str:
        if not file_path:
            return ""
        try:
            p = Path(file_path)
            if not p.is_file():
                return ""
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return ""

    def _lookup_design_cache(
        self,
        user_id: int,
        project_id: int,
        room_image_path: str,
        product_ids: list[int],
        provider: str,
        model: str,
        prompt: str,
        prompt_version: str = PROMPT_VERSION,
        skill_version: str | None = None,
        reference_image_paths: list[Path] | None = None,
    ) -> RoomDesignGeneration | None:
        """
        Tìm kiếm bản thiết kế đã sinh thành công trước đó (Design Cache).
        - Cache theo: cùng user_id, room_project_id, room_image_path (checksum), tập hợp product_ids,
          product_reference_checksums, provider, model, prompt_version, skill_version và prompt.
        - Tuyệt đối không trả về các phương án có status FAILED hoặc REJECTED.
        - Khi skill_version được yêu cầu, tuyệt đối không dùng kết quả của pipeline cũ để cache hit.
        - Xác minh file ảnh lưu trữ thực sự tồn tại trên ổ đĩa trước khi trả về.
        - Bảo đảm quyền riêng tư: Tuyệt đối không chia sẻ ảnh giữa các user khác nhau.
        """
        candidates = (
            self.db.query(RoomDesignGeneration)
            .options(self._generation_load_options())
            .filter(
                RoomDesignGeneration.room_project_id == project_id,
                RoomDesignGeneration.user_id == user_id,
                RoomDesignGeneration.status == "COMPLETED",
                RoomDesignGeneration.source_image_path == room_image_path,
                RoomDesignGeneration.provider == provider,
                RoomDesignGeneration.model == model,
                RoomDesignGeneration.prompt_version == prompt_version,
            )
            .order_by(RoomDesignGeneration.created_at.desc())
            .all()
        )
        target_product_ids = set(product_ids)
        storage_service = GeneratedDesignStorageService()
        current_room_checksum = self._compute_checksum(room_image_path)
        current_ref_checksums = [
            self._compute_checksum(p) for p in (reference_image_paths or []) if p and Path(p).is_file()
        ]

        for candidate in candidates:
            # 1. Bỏ qua không cache hit với các phương án đã bị REJECTED hoặc FAILED
            if candidate.status != "COMPLETED":
                continue
            if candidate.verification_status in ("REJECTED", "FAILED"):
                continue

            cand_prompt = candidate.prompt or ""
            if "[STATUS: REJECTED]" in cand_prompt or "[STATUS: FAILED]" in cand_prompt:
                continue

            # 2. Kiểm tra bộ sản phẩm
            candidate_ids = {p.id for p in candidate.products}
            if candidate_ids != target_product_ids or len(candidate.products) != len(target_product_ids):
                continue

            # 3. Kiểm tra Skill Bridge Version & Checksums (Không cache chéo pipeline cũ)
            if skill_version is not None:
                if "[SKILL_METADATA_V" not in cand_prompt:
                    # Candidate được tạo bởi pipeline cũ không có Skill metadata -> Không được cache hit
                    continue
                try:
                    from app.ai.skill_bridge import parse_skill_metadata
                    _, meta = parse_skill_metadata(cand_prompt)
                    if meta is None or getattr(meta, "version", None) != skill_version:
                        continue
                    if getattr(meta, "generation_status", None) in ("rejected", "failed"):
                        continue
                    cand_provenance = getattr(meta, "provenance", {}) or {}
                    cand_room_chk = cand_provenance.get("room_image_checksum")
                    if cand_room_chk and current_room_checksum and cand_room_chk != current_room_checksum:
                        continue
                    cand_ref_chks = cand_provenance.get("product_reference_checksums")
                    if cand_ref_chks and current_ref_checksums and cand_ref_chks != current_ref_checksums:
                        continue
                except Exception:
                    continue

            # 4. So khớp nội dung prompt chính xác sau khi loại bỏ metadata tags
            cand_clean = re.split(r"\n\n\[SKILL_METADATA_V\d+\]\n", cand_prompt)[0].strip()
            cand_clean = re.sub(r"^\[MODE:[^\]]+\]\s*(\[STATUS:[^\]]+\]\s*)?", "", cand_clean)
            cand_clean = re.sub(r"\n\[QUALITY_CHECK:[^\]]+\]\s*$", "", cand_clean).strip()

            raw_clean = re.split(r"\n\n\[SKILL_METADATA_V\d+\]\n", prompt or "")[0].strip()
            raw_clean = re.sub(r"^\[MODE:[^\]]+\]\s*(\[STATUS:[^\]]+\]\s*)?", "", raw_clean)
            raw_clean = re.sub(r"\n\[QUALITY_CHECK:[^\]]+\]\s*$", "", raw_clean).strip()

            if cand_clean == raw_clean:
                if candidate.generated_image_path:
                    try:
                        resolved_path = storage_service.resolve(candidate.generated_image_path)
                        if resolved_path.is_file():
                            logger.info(
                                "Design generation cache hit: Reusing generation id=%s for user_id=%s project_id=%s",
                                candidate.id,
                                user_id,
                                project_id,
                            )
                            return candidate
                    except Exception:
                        continue
        return None

    def _pick_compositible_product_image(
        self, product: Product, storage: ProductImageStorageService
    ) -> tuple[ProductImage, Path] | None:
        """Find an ISOLATED image suitable for 2D deterministic compositing.

        Checks prototype cutouts first for authentic verified assets (Sofa #1, Table #6),
        then checks the product's primary and other catalog images.
        """
        # 1. Prioritize verified studio cutouts in storage/verified_catalog_cutouts
        # Strictly verify BOTH product.id AND exact slug to prevent cutout mismatches
        # CẤM sử dụng các cutout copy/giả mạo (như #5, #7, #12, #15)
        AUTHENTIC_COMPOSITE_CUTOUT_IDS = {1, 6, 9, 16, 19, 21, 28}
        p_slug = getattr(product, "slug", "") or ""
        project_root = Path(__file__).resolve().parents[3]
        verified_dir = project_root / "storage" / "verified_catalog_cutouts"

        if verified_dir.is_dir() and p_slug and product.id in AUTHENTIC_COMPOSITE_CUTOUT_IDS:
            exact_cutout = verified_dir / f"{product.id}_{p_slug}.png"
            if exact_cutout.is_file():
                dummy_img = product.images[0] if getattr(product, "images", None) else None
                return dummy_img, exact_cutout

        # 2. Check genuine product catalog images (never placeholders/demo)
        if not getattr(product, "images", None):
            return None

        primary = next((img for img in product.images if getattr(img, "is_primary", False)), None)
        others = sorted(
            [img for img in product.images if img != primary],
            key=lambda img: getattr(img, "sort_order", 0),
        )
        candidates = ([primary] if primary is not None else []) + others

        for img in candidates:
            if not getattr(img, "image_url", None):
                continue
            url_str = str(img.image_url).lower()
            # CẤM TUYỆT ĐỐI đưa ảnh demo, placeholder, thumbnail có chữ/icon/logo vào kết quả composite!
            if any(bad in url_str for bad in ["generated-demo", "demo", "placeholder", "dummy", "thumbnail"]):
                continue
            try:
                path = storage.resolve(img.image_url)
            except Exception:
                continue
            if path is not None and path.is_file():
                path_str = str(path).lower()
                if any(bad in path_str for bad in ["generated-demo", "demo", "placeholder", "dummy", "thumbnail"]):
                    continue
                try:
                    if classify_product_image(path) == ISOLATED:
                        return img, path
                except Exception:
                    continue

        return None

    def _generate_with_composite_fallback(
        self,
        current_user: User,
        project: RoomProject,
        selected_products: list[Product],
        reference_image_paths: list[Path] | None = None,
        reason: str = "OFFLINE_FALLBACK",
        failed_generation: RoomDesignGeneration | None = None,
        placements: list[dict] | None = None,
        light_direction: str | None = None,
        shadow_intensity: float | None = None,
        floor_horizon_ratio: float | None = None,
    ) -> RoomDesignGeneration:
        """
        Tự động tạo ảnh phối cảnh 2D bằng Pillow Compositor cục bộ khi Cloud AI hết quota, lỗi 429/5xx,
        hoặc khi công tắc khẩn cấp ENABLE_CLOUD_AI=false được kích hoạt.

        Chỉ chọn các ảnh ISOLATED (nền trơn/trong suốt). Nếu ảnh chính là SCENE (phối cảnh phòng),
        tự động tìm ảnh ISOLATED khác của cùng sản phẩm để ghép.
        Nếu sản phẩm không có ảnh phù hợp, bỏ qua sản phẩm đó.
        Nếu không có sản phẩm nào phù hợp, trả lỗi có kiểm soát 409 Conflict thay vì tạo ảnh giả.
        """
        started_at = perf_counter()
        composite_provider = CompositeImageProvider()
        source_image_path = RoomImageStorageService().resolve(project.room_image_path)
        storage = ProductImageStorageService()

        # Step 1: Detect and select ISOLATED images for each product
        max_references = max(0, getattr(composite_provider, "MAX_INPUT_IMAGES", 5) - 1)
        compositible_candidates: list[tuple[Product, Path]] = []
        skipped_products: list[Product] = []

        for idx, product in enumerate(selected_products):
            picked = self._pick_compositible_product_image(product, storage)
            if picked is not None:
                compositible_candidates.append((product, picked[1]))
            elif reference_image_paths and idx < len(reference_image_paths):
                # Fallback to direct path if it exists, is NOT a demo placeholder, and is classified as ISOLATED
                p = reference_image_paths[idx]
                if (
                    p
                    and p.is_file()
                    and not any(bad in str(p).lower() for bad in ["generated-demo", "demo", "placeholder", "dummy", "thumbnail"])
                    and classify_product_image(p) == ISOLATED
                ):
                    compositible_candidates.append((product, p))
                    continue
                skipped_products.append(product)
            else:
                skipped_products.append(product)
                logger.warning(
                    "Product id=%s (%s) has no isolated image for 2D composite, excluding from composite canvas",
                    product.id,
                    getattr(product, "name", "unknown"),
                )

        # Step 2: Validate that at least ONE product can be composited (never fake success)
        if not compositible_candidates:
            latency_ms = int((perf_counter() - started_at) * 1000)
            error_code = "NO_COMPOSITIBLE_PRODUCT_IMAGES"
            error_message = (
                "None of the selected products have an isolated cutout image for 2D composite generation. "
                "Please select products with isolated catalog images or enable Cloud AI."
            )
            try:
                self.db.rollback()
            except Exception:
                pass
            if failed_generation is None:
                gen_fail = RoomDesignGeneration(
                    room_project_id=project.id,
                    user_id=current_user.id,
                    status="FAILED",
                    provider=composite_provider.provider_name,
                    model=composite_provider.model_name,
                    prompt_version=PROMPT_VERSION,
                    source_image_path=project.room_image_path,
                    prompt=f"[Chế độ Offline 2D - {reason}] Ghép ảnh nội thất trực tiếp bằng Pillow Compositor.",
                    products=selected_products,
                )
                self._persist_failure(
                    generation=gen_fail,
                    current_user=current_user,
                    project=project,
                    error_code=error_code,
                    error_message=error_message,
                    latency_ms=latency_ms,
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{error_code}: {error_message}",
            )

        prioritized = sorted(
            compositible_candidates,
            key=lambda item: get_category_reference_priority(item[0]),
        )[:max_references]

        composited_products = [item[0] for item in prioritized]
        comp_reference_paths = [item[1] for item in prioritized]
        categories = [
            p.category.slug if p.category and p.category.slug else "accessories"
            for p in composited_products
        ]

        # Step 3: Run composite design with exception handling
        generation: RoomDesignGeneration | None = None
        skipped_names = [p.name for p in skipped_products]
        skipped_note = f" (Đã bỏ qua {len(skipped_products)} sản phẩm không có ảnh bóc nền chuẩn: {', '.join(skipped_names)})" if skipped_products else ""
        comp_status = "COMPOSITE_FALLBACK" if (skipped_products or reason != "USER_MODE_CATALOG_ACCURATE") else "VERIFIED"
        prompt = f"[MODE: CATALOG_ACCURATE] [STATUS: {comp_status}] [Chế độ Offline 2D - {reason}] Bản ghép xem trước Offline – Không phải ảnh AI Photorealistic. Ghép {len(composited_products)}/{len(selected_products)} sản phẩm.{skipped_note}"

        try:
            provider_result = composite_provider.generate_design(
                source_image_path=source_image_path,
                prompt=prompt,
                reference_image_paths=comp_reference_paths,
                reference_categories=categories,
                placements=placements,
                light_direction=light_direction,
                shadow_intensity=shadow_intensity,
                floor_horizon_ratio=floor_horizon_ratio,
            )
        except (ImageProviderError, Exception) as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            safe_message = _sanitize_error_message(str(exc))
            error_code = getattr(exc, "code", "COMPOSITE_GENERATION_FAILED") or "COMPOSITE_GENERATION_FAILED"
            try:
                self.db.rollback()
            except Exception:
                pass
            if failed_generation is None:
                generation = RoomDesignGeneration(
                    room_project_id=project.id,
                    user_id=current_user.id,
                    status="FAILED",
                    provider=composite_provider.provider_name,
                    model=composite_provider.model_name,
                    prompt_version=PROMPT_VERSION,
                    source_image_path=project.room_image_path,
                    prompt=prompt,
                    products=composited_products,
                )
                self._persist_failure(
                    generation=generation,
                    current_user=current_user,
                    project=project,
                    error_code=error_code,
                    error_message=safe_message,
                    latency_ms=latency_ms,
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{error_code}: {safe_message}",
            ) from exc

        # Step 4: Persist successful generation
        if failed_generation is not None:
            generation = failed_generation
            generation.provider = composite_provider.provider_name
            generation.model = composite_provider.model_name
            generation.prompt = prompt
            generation.products = composited_products
        else:
            generation = RoomDesignGeneration(
                room_project_id=project.id,
                user_id=current_user.id,
                status="GENERATING",
                provider=composite_provider.provider_name,
                model=composite_provider.model_name,
                prompt_version=PROMPT_VERSION,
                source_image_path=project.room_image_path,
                prompt=prompt,
                products=composited_products,
            )
            self.db.add(generation)
            self.db.flush()

        stored = GeneratedDesignStorageService().save(
            provider_result.data,
            provider_result.content_type,
            current_user.id,
            project.id,
            generation.id,
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
        generation.status = "COMPLETED"
        generation.generated_image_url = stored.image_url
        generation.generated_image_path = stored.storage_path
        generation.latency_ms = latency_ms
        generation.completed_at = datetime.now(UTC)
        generation.error_code = None
        generation.error_message = None

        use_skill_bridge = bool(getattr(settings, "room_decor_skill_enabled", False)) and getattr(self.image_provider, "provider_name", "") != "composite"
        if use_skill_bridge:
            try:
                from app.ai.skill_bridge import QualityEvaluator, SkillBridgeMetadata, serialize_skill_metadata
                evaluator = QualityEvaluator(threshold=getattr(settings, "room_decor_min_score", 85.0))
                eval_res = evaluator.evaluate(
                    source_room_path=source_image_path,
                    candidate_image_bytes=provider_result.data,
                    selected_product_ids=[p.id for p in composited_products],
                    reference_image_paths=comp_reference_paths,
                    is_composite_mode=True,
                )
                meta = SkillBridgeMetadata(
                    version="1.0.0",
                    quality_score=eval_res.quality_score,
                    component_scores=eval_res.component_scores.model_dump(),
                    gates={
                        "architecture": eval_res.architecture.model_dump(),
                        "access": eval_res.access.model_dump(),
                        "extras": eval_res.extras.model_dump(),
                        "products": {k: v.model_dump() for k, v in eval_res.products.items()},
                    },
                    referenced_product_ids=[p.id for p in selected_products],
                    verified_product_ids=[p.id for p in composited_products],
                    hard_gates_passed=eval_res.hard_gates_passed,
                    neuron_estimate=0,
                    warnings=eval_res.warnings + ([f"Bỏ qua {len(skipped_products)} sản phẩm không có ảnh bóc nền chuẩn: {', '.join(skipped_names)}"] if skipped_products else []),
                    provenance={"skill_version": "1.0.0", "mode": "composite_offline", "reason": reason},
                )
                generation.prompt = serialize_skill_metadata(prompt, meta)
            except Exception as skill_err:
                logger.warning("Skill Bridge composite metadata serialization failed: %s", skill_err)

        self._log_usage(
            current_user=current_user,
            project=project,
            provider=composite_provider.provider_name,
            model=composite_provider.model_name,
            status="SUCCESS",
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=0,
        )
        self.db.commit()
        return self.get_generation(current_user, project.id, generation.id)

    def _generate_v2_offline_preview(
        self,
        current_user: User,
        project: RoomProject,
        selected_products: list[Product],
        reference_image_paths: list[Path] | None = None,
        analysis: RoomAnalysis | None = None,
        included_ids: list[int] | None = None,
    ) -> RoomDesignGeneration:
        """
        AI Room Decor Skill Bridge V2.0 PRO: Offline preview generation using
        incremental Architecture Pixel Protection, Product Intelligence, and Spatial Planner.
        Zero external API calls, zero billing impact.
        """
        started_at = perf_counter()
        source_image_path = RoomImageStorageService().resolve(project.room_image_path)

        from app.ai.skill_bridge.v2.core.engine import Engine
        from app.ai.skill_bridge.v2.security.images import decode
        from app.ai.skill_bridge import SkillBridgeMetadata, serialize_skill_metadata

        inc_ids = included_ids or [p.id for p in selected_products]
        active_products = [p for p in selected_products if p.id in inc_ids]

        product_inputs = []
        for idx, p in enumerate(active_products):
            p_imgs = []
            if reference_image_paths and idx < len(reference_image_paths) and reference_image_paths[idx]:
                p_imgs.append(str(reference_image_paths[idx]).replace("\\", "/"))
            elif getattr(p, "images", None):
                for img in p.images:
                    if getattr(img, "image_url", None):
                        try:
                            p_path = ProductImageStorageService().resolve(img.image_url)
                            if p_path and p_path.is_file():
                                p_imgs.append(str(p_path).replace("\\", "/"))
                                break
                        except Exception:
                            pass
            product_inputs.append({
                "product_id": str(p.id),
                "product_name": str(p.name),
                "product_images": p_imgs if p_imgs else ["storage/products/default.jpg"],
                "product_dimensions": None,
            })

        req = {
            "room_image": str(source_image_path).replace("\\", "/"),
            "room_type": project.room_type or (analysis.room_type if analysis else "living-room"),
            "selected_products": product_inputs,
            "design_style": getattr(project, "design_style", None) or "modern",
            "user_requirements": getattr(project, "user_requirements", None) or "Place catalog furniture realistically on the floor",
        }

        def safe_load_asset(asset_str: str) -> bytes:
            p = Path(asset_str)
            if p.is_file():
                return p.read_bytes()
            try:
                p_room = RoomImageStorageService().resolve(asset_str)
                if p_room and p_room.is_file():
                    return p_room.read_bytes()
            except Exception:
                pass
            try:
                p_prod = ProductImageStorageService().resolve(asset_str)
                if p_prod and p_prod.is_file():
                    return p_prod.read_bytes()
            except Exception:
                pass
            raise ValueError(f"UNAUTHORIZED_OR_MISSING_ASSET: {asset_str}")

        room_bytes = source_image_path.read_bytes()
        room_arr = decode(room_bytes)
        h_room, w_room = room_arr.shape[:2]

        floor_y = int(h_room * 0.62)
        zones = {
            "floor": [[[0, floor_y], [w_room - 1, floor_y], [w_room - 1, h_room - 1], [0, h_room - 1]]],
            "window": [[[0, 0], [int(w_room * 0.3), 0], [int(w_room * 0.3), floor_y], [0, floor_y]]],
            "ceiling": [[[0, 0], [w_room - 1, 0], [w_room - 1, int(h_room * 0.22)], [0, int(h_room * 0.22)]]],
            "wall": [[[int(w_room * 0.3), int(h_room * 0.22)], [w_room - 1, int(h_room * 0.22)], [w_room - 1, floor_y], [int(w_room * 0.3), floor_y]]],
            "existing": [],
            "door": [],
            "walkway": [[[0, int(h_room * 0.95)], [w_room - 1, int(h_room * 0.95)], [w_room - 1, h_room - 1], [0, h_room - 1]]],
        }

        preview_holder = {}
        def save_preview_cb(raw_png: bytes) -> str:
            preview_holder["bytes"] = raw_png
            return "stored_in_memory"

        engine = Engine()
        v2_result = engine.run(req, safe_load_asset, zones, save_preview=save_preview_cb)

        latency_ms = int((perf_counter() - started_at) * 1000)

        generation = RoomDesignGeneration(
            room_project_id=project.id,
            user_id=current_user.id,
            status="GENERATING",
            provider="offline",
            model="pixel-composite-v2",
            prompt_version="v2",
            source_image_path=project.room_image_path,
            prompt="[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: NEEDS_REVIEW] V2 Pixel-Protected Composite Preview",
            products=active_products,
        )
        self.db.add(generation)
        self.db.commit()
        self.db.refresh(generation)

        # Store preview image
        output_bytes = preview_holder.get("bytes") or room_bytes
        stored = GeneratedDesignStorageService().save(
            output_bytes,
            "image/png",
            current_user.id,
            project.id,
            generation.id,
        )

        meta = SkillBridgeMetadata(
            version="2.0.0",
            quality_score=v2_result.get("quality_score"),
            component_scores={},
            generation_status="needs_review",
            gates=v2_result.get("provenance", {}).get("checks", {}),
            referenced_product_ids=[p.id for p in active_products],
            verified_product_ids=[],
            hard_gates_passed=False,
            neuron_estimate=0,
            warnings=v2_result.get("warnings", []),
            provenance={
                "skill_version": "2.0.0",
                "external_inference": 0,
                "provider": "offline",
                "model": "pixel-composite-v2",
                "latency_ms": latency_ms,
            },
        )
        prompt_tagged = "[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: NEEDS_REVIEW] V2 Pixel-Protected Composite Preview"
        generation.prompt = serialize_skill_metadata(prompt_tagged, meta, version="2.0.0")
        generation.generated_image_path = stored.storage_path
        generation.generated_image_url = stored.image_url
        generation.status = "COMPLETED"
        generation.completed_at = datetime.now(UTC)
        generation.latency_ms = latency_ms

        self._log_usage(
            current_user=current_user,
            project=project,
            provider="offline",
            model="pixel-composite-v2",
            status="SUCCESS",
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=0,
        )
        self.db.commit()
        return self.get_generation(current_user, project.id, generation.id)

    def create_generation(
        self,
        current_user: User,
        project_id: int,
        payload: DesignGenerationCreate,
    ) -> RoomDesignGeneration:
        project = self._get_owned_project(current_user, project_id)
        if not project.room_image_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ROOM_IMAGE_REQUIRED")

        rec_service = RecommendationService(self.db)
        preference, analysis, recommendations = rec_service.recommend_for_project(current_user, project_id, limit=50)
        effective_pref = getattr(rec_service, "last_effective_preference", None) or preference
        recommended_by_id = {item.product.id: item.product for item in recommendations}
        selection_mode = (getattr(payload, "selection_mode", None) or "AUTO").upper()
        selected_products = self._select_products(
            payload.product_ids,
            recommended_by_id,
            selection_mode=selection_mode,
            effective_pref=effective_pref,
        )
        total_price = sum(float(p.price or 0.0) for p in selected_products)
        budget_warnings: list[str] = []
        budget_max = getattr(effective_pref, "budget_max", None)
        if budget_max is not None and total_price > float(budget_max):
            budget_warnings.append(
                f"Tổng giá bộ nội thất ({total_price:,.0f} VND) vượt ngân sách dự kiến ({float(budget_max):,.0f} VND)."
            )

        reference_image_paths, reference_mapping, included_ids, missing_ids = self._resolve_reference_images(selected_products)
        ordered_products = [product for _, product in reference_mapping]
        if self.image_provider.provider_name == "gemini" and missing_ids:
            missing_product_ids = ",".join(str(product_id) for product_id in missing_ids)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"GEMINI_PRODUCT_REFERENCE_IMAGE_MISSING: product IDs {missing_product_ids} have no readable catalog image",
            )
        if getattr(self.image_provider, "requires_all_product_references", False) and len(included_ids) != len(selected_products):
            unresolved_ids = [product.id for product in selected_products if product.id not in included_ids]
            unresolved_product_ids = ",".join(str(product_id) for product_id in unresolved_ids)
            max_products = max(0, getattr(self.image_provider, "MAX_INPUT_IMAGES", 1) - 1)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"QWENCLOUD_PRODUCT_REFERENCES_UNAVAILABLE: all selected products need readable images; "
                    f"this model supports at most {max_products} products per design. Affected product IDs: {unresolved_product_ids}"
                ),
            )
        if not included_ids and getattr(self.image_provider, "provider_name", "") not in ("composite", "not_configured", "fake_image"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="NO_VALID_PRODUCT_REFERENCES: Các sản phẩm được chọn chưa có ảnh tham chiếu catalog hợp lệ.",
            )
        use_skill_bridge = bool(getattr(settings, "room_decor_skill_enabled", False)) and getattr(self.image_provider, "provider_name", "") != "composite"
        if use_skill_bridge:
            max_allowed_refs = max(0, getattr(self.image_provider, "MAX_INPUT_IMAGES", 4) - 1)
            if len(selected_products) > max_allowed_refs:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"CAPABILITY_MISMATCH: Mô hình {self.image_provider.provider_name} "
                        f"chỉ hỗ trợ tối đa {max_allowed_refs} sản phẩm tham chiếu trong một ảnh phối cảnh "
                        f"(bạn đã chọn {len(selected_products)} sản phẩm). Vui lòng chọn tối đa {max_allowed_refs} sản phẩm."
                    ),
                )
            if len(included_ids) < len(selected_products):
                unresolved = [p.id for p in selected_products if p.id not in included_ids]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CATALOG_REFERENCE_MISSING: Sản phẩm {unresolved} chưa có ảnh catalog hợp lệ để làm mẫu tham chiếu phối cảnh AI.",
                )
            from app.ai.skill_bridge import build_skill_manifest, build_skill_prompt
            manifest = build_skill_manifest(
                room_image_path=project.room_image_path,
                selected_products=ordered_products,
                reference_image_paths=reference_image_paths,
            )
            # Single ordered reference manifest as the sole source of truth
            manifest_product_ids = [item["product_id"] for item in manifest[1:]]
            manifest_reference_paths = [Path(item["asset"]) for item in manifest[1:]]
            manifest_categories = [item.get("category") or "accessories" for item in manifest[1:]]

            prompt = build_skill_prompt(
                project=project,
                selected_products=ordered_products,
                analysis=analysis,
                preference=effective_pref,
                manifest=manifest,
            )
        else:
            manifest_product_ids = included_ids
            manifest_reference_paths = reference_image_paths
            manifest_categories = [p.category.slug if p.category and p.category.slug else "accessories" for p in ordered_products]
            prompt = build_design_generation_prompt(project, analysis, preference, selected_products, reference_mapping)
        self._log_reference_diagnostics(ordered_products, included_ids, missing_ids, len(manifest_reference_paths))

        is_v1_5 = getattr(settings, "room_decor_v1_5_personalization_enabled", True)
        current_prompt_version = "v1.5" if is_v1_5 else PROMPT_VERSION
        current_skill_version = "1.5.0" if (use_skill_bridge and is_v1_5) else ("1.0.0" if use_skill_bridge else None)

        # 1. Design Cache: Kiểm tra xem đã từng sinh ảnh tương tự trước đó chưa (bao gồm cả prompt & RoomPreference)
        if not getattr(payload, "force", False):
            cached = self._lookup_design_cache(
                user_id=current_user.id,
                project_id=project.id,
                room_image_path=project.room_image_path,
                product_ids=manifest_product_ids,
                provider=self.image_provider.provider_name,
                model=self.image_provider.model_name,
                prompt=prompt,
                prompt_version=current_prompt_version,
                skill_version=current_skill_version,
                reference_image_paths=manifest_reference_paths,
            )
            if cached is not None:
                return cached

        # V2 Engineering Preview Integration (Off by default)
        if getattr(settings, "room_decor_v2_enabled", False):
            v2_mode = getattr(settings, "room_decor_v2_mode", "offline_preview")
            if v2_mode in ("offline_preview", "hybrid"):
                return self._generate_v2_offline_preview(
                    current_user=current_user,
                    project=project,
                    selected_products=selected_products,
                    reference_image_paths=reference_image_paths,
                    analysis=analysis,
                    included_ids=included_ids,
                )

        # 2. Concurrency Check & Reservation dưới Project Lock ngắn hạn
        quota_service = AIQuotaService(self.db)
        is_cloud = self.image_provider.provider_name in ("cloudflare", "gemini", "openai", "qwencloud")
        is_composite = self.image_provider.provider_name == "composite"
        reservation = None

        with quota_service.project_lock(project.id):
            quota_service.check_in_flight_concurrency(project.id, "ROOM_DESIGN_GENERATION")

            # 3. Emergency Kill Switch check (ENABLE_CLOUD_AI=false) hoặc Chế độ Composite 2D trực tiếp
            is_explicit_catalog_mode = getattr(payload, "generation_mode", None) == "CATALOG_ACCURATE"
            if is_cloud and not quota_service.is_cloud_ai_enabled():
                if getattr(payload, "generation_mode", None) == "AI_PHOTOREALISTIC_PREVIEW":
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="CLOUD_AI_DISABLED: Dịch vụ tạo ảnh Cloud AI hiện đang tắt (Kill Switch). Vui lòng kiểm tra lại cấu hình.",
                    )
                reason = "CLOUD_AI_DISABLED"
                logger.info("Running Composite 2D (reason=%s)", reason)
                placement_dicts = None
                if getattr(payload, "placements", None):
                    placement_dicts = [p.model_dump() for p in payload.placements]
                return self._generate_with_composite_fallback(
                    current_user=current_user,
                    project=project,
                    selected_products=selected_products,
                    reference_image_paths=reference_image_paths,
                    reason=reason,
                    placements=placement_dicts,
                    light_direction=getattr(payload, "light_direction", "auto"),
                    shadow_intensity=getattr(payload, "shadow_intensity", 0.72),
                    floor_horizon_ratio=getattr(payload, "floor_horizon_ratio", None),
                )
            elif is_composite or is_explicit_catalog_mode:
                reason = "USER_MODE_CATALOG_ACCURATE" if is_explicit_catalog_mode else "LOCAL_COMPOSITE"
                logger.info("Running Composite 2D (reason=%s)", reason)
                placement_dicts = None
                if getattr(payload, "placements", None):
                    placement_dicts = [p.model_dump() for p in payload.placements]

                return self._generate_with_composite_fallback(
                    current_user=current_user,
                    project=project,
                    selected_products=selected_products,
                    reference_image_paths=reference_image_paths,
                    reason=reason,
                    placements=placement_dicts,
                    light_direction=getattr(payload, "light_direction", "auto"),
                    shadow_intensity=getattr(payload, "shadow_intensity", 0.72),
                    floor_horizon_ratio=getattr(payload, "floor_horizon_ratio", None),
                )

            # 4. Daily Quota Check & Atomic Reservation
            if is_cloud:
                reservation = quota_service.reserve_quota(
                    user_id=current_user.id,
                    project_id=project.id,
                    provider=self.image_provider.provider_name,
                    model=self.image_provider.model_name,
                    task_type="ROOM_DESIGN_GENERATION",
                )
                if reservation is None:
                    user_usage, sys_usage = quota_service.get_daily_usage(current_user.id, self.image_provider.provider_name)
                    user_limit, sys_limit = quota_service.get_quota_limits(self.image_provider.provider_name)
                    if user_usage >= user_limit:
                        err_code = "CLOUDFLARE_IMAGE_QUOTA_ERROR"
                        err_msg = f"Đã đạt giới hạn tạo ảnh Cloudflare AI của bạn trong ngày ({user_usage}/{user_limit} lượt). Vui lòng thử lại vào ngày mai."
                        status_code = status.HTTP_429_TOO_MANY_REQUESTS
                    elif sys_usage >= sys_limit:
                        err_code = "CLOUDFLARE_IMAGE_QUOTA_ERROR"
                        err_msg = f"Hệ thống đã đạt giới hạn tạo ảnh Cloudflare AI trong ngày ({sys_usage}/{sys_limit} lượt). Vui lòng thử lại vào ngày mai."
                        status_code = status.HTTP_429_TOO_MANY_REQUESTS
                    else:
                        err_code = "CLOUDFLARE_IMAGE_LOCK_BUSY"
                        err_msg = "Hệ thống đang bận điều phối quota hoặc xử lý tác vụ khác. Vui lòng thử lại sau vài giây."
                        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

                    logger.warning("Cloud AI quota or reservation unavailable for provider=%s user=%s: %s", self.image_provider.provider_name, current_user.id, err_msg)
                    if getattr(payload, "generation_mode", None) == "AI_PHOTOREALISTIC_PREVIEW":
                        raise HTTPException(
                            status_code=status_code,
                            detail=f"{err_code}: {err_msg}",
                        )
                    # Quota chạm trần ngày cho các mode khác -> Chuyển Fallback Composite 2D
                    placement_dicts = None
                    if getattr(payload, "placements", None):
                        placement_dicts = [p.model_dump() for p in payload.placements]
                    return self._generate_with_composite_fallback(
                        current_user=current_user,
                        project=project,
                        selected_products=selected_products,
                        reference_image_paths=reference_image_paths,
                        reason="QUOTA_EXCEEDED",
                        placements=placement_dicts,
                        light_direction=getattr(payload, "light_direction", "auto"),
                        shadow_intensity=getattr(payload, "shadow_intensity", 0.72),
                        floor_horizon_ratio=getattr(payload, "floor_horizon_ratio", None),
                    )

            is_composite = getattr(self.image_provider, "provider_name", "") == "composite"
            is_v1_5 = getattr(settings, "room_decor_v1_5_personalization_enabled", True)
            generation = RoomDesignGeneration(
                room_project_id=project.id,
                user_id=current_user.id,
                status="GENERATING",
                provider=self.image_provider.provider_name,
                model=self.image_provider.model_name,
                prompt_version="v1.5" if is_v1_5 else PROMPT_VERSION,
                source_image_path=project.room_image_path,
                prompt=prompt,
                products=selected_products,
            )
            self.db.add(generation)
            self.db.commit()

        # Ra khỏi project_lock -> Gọi Cloud AI (không giữ database lock trong thời gian chờ AI)
        started_at = perf_counter()
        try:
            self.db.refresh(generation)
            source_image_path = RoomImageStorageService().resolve(project.room_image_path)
            provider_result = self._generate(
                source_image_path,
                prompt,
                manifest_reference_paths,
                reference_categories=manifest_categories if getattr(self.image_provider, "supports_categories", False) else None,
            )

            # Stage 2D & 2E: Photorealistic Preview mode tagging as in Generation #102
            mode_tag = f"[MODE: AI_PHOTOREALISTIC_PREVIEW] [STATUS: NEEDS_REVIEW]" if is_cloud else "[MODE: CATALOG_ACCURATE] [STATUS: VERIFIED]"
            prompt = f"{mode_tag} {prompt}"
            generation.prompt = prompt

            if not provider_result.data or len(provider_result.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="EMPTY_GENERATED_IMAGE: Dịch vụ AI không trả về dữ liệu ảnh hợp lệ.",
                )

            try:
                source_bytes = source_image_path.read_bytes()
                if is_cloud and provider_result.data == source_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="EMPTY_ROOM_RETURNED: Dịch vụ AI trả về ảnh phòng trống không có nội thất mới.",
                    )
            except HTTPException:
                raise
            except Exception as read_err:
                logger.debug("Source room byte comparison check: %s", read_err)

            # Apply subtle local background preservation if cloud AI and natural alignment is verified
            final_image_data = provider_result.data
            final_content_type = provider_result.content_type
            if is_cloud and not is_composite:
                final_image_data = self._postprocess_preserve_background(source_image_path, provider_result.data)
                final_content_type = "image/jpeg"

            stored = GeneratedDesignStorageService().save(
                final_image_data,
                final_content_type,
                current_user.id,
                project.id,
                generation.id,
            )

            # Quality screening check under Skill V1.0 or legacy warning mode
            if is_cloud:
                if use_skill_bridge:
                    try:
                        from app.ai.skill_bridge import QualityEvaluator, SkillBridgeMetadata, serialize_skill_metadata
                        evaluator = QualityEvaluator(threshold=getattr(settings, "room_decor_min_score", 85.0))
                        eval_res = evaluator.evaluate(
                            source_room_path=source_image_path,
                            candidate_image_bytes=provider_result.data,
                            selected_product_ids=manifest_product_ids,
                            reference_image_paths=manifest_reference_paths,
                            is_composite_mode=False,
                            steps=8,
                        )
                        meta = SkillBridgeMetadata(
                            version="1.5.0" if is_v1_5 else "1.0.0",
                            quality_score=eval_res.quality_score,
                            component_scores=eval_res.component_scores.model_dump(),
                            gates={
                                "architecture": eval_res.architecture.model_dump(),
                                "access": eval_res.access.model_dump(),
                                "extras": eval_res.extras.model_dump(),
                                "products": {k: v.model_dump() for k, v in eval_res.products.items()},
                            },
                            referenced_product_ids=manifest_product_ids,
                            verified_product_ids=eval_res.verified_product_ids,
                            hard_gates_passed=eval_res.hard_gates_passed,
                            neuron_estimate=eval_res.neuron_estimate,
                            warnings=eval_res.warnings + budget_warnings,
                            provenance={
                                "skill_version": "1.5.0" if is_v1_5 else "1.0.0",
                                "selection_mode": selection_mode,
                                "total_price": total_price,
                                "attempts": 1,
                                "provider": generation.provider,
                                "model": generation.model,
                                "room_image_checksum": self._compute_checksum(source_image_path),
                                "product_reference_checksums": [
                                    self._compute_checksum(p) for p in manifest_reference_paths if p and Path(p).is_file()
                                ],
                            },
                        )
                        has_hard_fail = (
                            eval_res.generation_status in ("rejected", "failed")
                            or bool(eval_res.failed_gates)
                            or any(
                                getattr(c, "status", None) == "fail"
                                for c in [eval_res.architecture, eval_res.access, eval_res.extras, *eval_res.products.values()]
                            )
                        )
                        if has_hard_fail:
                            status_tag = "[STATUS: REJECTED]"
                            eval_res.generation_status = "rejected"
                            meta.generation_status = "rejected"
                        else:
                            status_tag = "[STATUS: NEEDS_REVIEW]"
                            meta.generation_status = "needs_review"

                        clean_prompt = re.sub(r"^\[MODE:[^\]]+\]\s*(\[STATUS:[^\]]+\]\s*)?", "", prompt).strip()
                        prompt = f"[MODE: AI_PHOTOREALISTIC_PREVIEW] {status_tag} {clean_prompt}"
                        prompt = serialize_skill_metadata(prompt, meta)
                        generation.prompt = prompt
                        logger.info(
                            "Skill Bridge evaluation gen_id=%s: score=%s, status=%s, hard_gates_passed=%s, warnings=%s",
                            generation.id,
                            eval_res.quality_score,
                            eval_res.generation_status,
                            eval_res.hard_gates_passed,
                            eval_res.warnings,
                        )
                    except Exception as skill_err:
                        logger.warning("Skill Bridge quality evaluation error: %s", skill_err)
                else:
                    try:
                        from app.ai.gemini_hybrid.catalog_validator import CatalogIdentityValidator
                        val_result = CatalogIdentityValidator().validate(
                            source_room_path=source_image_path,
                            output_image_data=provider_result.data,
                            selected_product_ids=manifest_product_ids,
                            reference_image_paths=manifest_reference_paths,
                            is_composite_mode=False,
                        )
                        warning_summary = " | ".join(val_result.notes) if val_result.notes else "ok"
                        logger.info(
                            "AI Generation quality screening for generation id=%s: drift=%.3f, fidelity=%.3f, status=%s, notes=%s",
                            generation.id,
                            val_result.architecture_drift_score,
                            val_result.product_fidelity_score,
                            val_result.status,
                            warning_summary,
                        )
                        prompt = f"{prompt}\n[QUALITY_CHECK: drift={val_result.architecture_drift_score:.3f}, fidelity={val_result.product_fidelity_score:.3f}]"
                        generation.prompt = prompt
                    except Exception as val_err:
                        logger.warning("AI quality screening warning: %s", val_err)
            latency_ms = int((perf_counter() - started_at) * 1000)
            completed_now = datetime.now(UTC)

            # Fencing token check: Kiểm tra xem generation có còn là GENERATING không
            # (Ngăn request chạy quá chậm ghi đè lên request mới sau khi bị Stale Recovery thu hồi)
            affected = (
                self.db.query(RoomDesignGeneration)
                .filter(
                    RoomDesignGeneration.id == generation.id,
                    RoomDesignGeneration.status == "GENERATING",
                )
                .update(
                    {
                        RoomDesignGeneration.status: "COMPLETED",
                        RoomDesignGeneration.generated_image_url: stored.image_url,
                        RoomDesignGeneration.generated_image_path: stored.storage_path,
                        RoomDesignGeneration.prompt: prompt,
                        RoomDesignGeneration.latency_ms: latency_ms,
                        RoomDesignGeneration.completed_at: completed_now,
                        RoomDesignGeneration.error_code: None,
                        RoomDesignGeneration.error_message: None,
                    },
                    synchronize_session="fetch",
                )
            )

            if affected == 0:
                logger.warning(
                    "Fencing token check failed for generation id=%s: task was recovered or superseded. Dropping completion.",
                    generation.id,
                )
                if reservation is not None:
                    quota_service.release_reservation(reservation, error_code="SUPERSEDED_STALE_TASK")
                self.db.commit()
                return self.get_generation(current_user, project.id, generation.id)

            usage = provider_result.usage
            if reservation is not None:
                quota_service.finalize_success(
                    reservation=reservation,
                    latency_ms=latency_ms,
                    input_tokens=usage.input_tokens if usage else 0,
                    output_tokens=usage.output_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    estimated_cost=usage.estimated_cost if usage else 0,
                )
            else:
                self._log_usage(
                    current_user=current_user,
                    project=project,
                    provider=generation.provider,
                    model=generation.model,
                    status="SUCCESS",
                    latency_ms=latency_ms,
                    input_tokens=usage.input_tokens if usage else 0,
                    output_tokens=usage.output_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    estimated_cost=usage.estimated_cost if usage else 0,
                )
            self.db.commit()
            return self.get_generation(current_user, project.id, generation.id)
        except ImageProviderError as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            safe_provider_message = _sanitize_error_message(exc.message) if exc.message else None
            is_timeout = (
                exc.code in ("TIMEOUT", "GATEWAY_TIMEOUT", "DEADLINE_EXCEEDED")
                or "timeout" in (exc.code or "").lower()
                or "timeout" in (safe_provider_message or "").lower()
            )
            logger.error(
                "design_generation_provider_failed provider=%s model=%s project_id=%s generation_id=%s error_code=%s error_message=%s is_timeout=%s",
                generation.provider,
                generation.model,
                project.id,
                getattr(generation, "id", None),
                exc.code,
                safe_provider_message,
                is_timeout,
            )

            # Giải phóng reservation quota do lỗi provider (nếu timeout: gán TIMEOUT_SUSPECTED)
            if reservation is not None:
                quota_service.release_reservation(
                    reservation,
                    error_code=exc.code,
                    error_message=safe_provider_message,
                    is_timeout=is_timeout,
                )

            # Requirement 4: Không tự động retry khi kết quả provider không xác định (timeout)
            # Khi người dùng yêu cầu tạo thiết kế AI (Cloudflare FLUX), KHÔNG tự động chuyển sang Composite 2D
            if not is_timeout and getattr(payload, "generation_mode", None) != "AI_PHOTOREALISTIC_PREVIEW":
                try:
                    logger.info("Auto-falling back to Composite 2D after provider error %s", exc.code)
                    return self._generate_with_composite_fallback(
                        current_user=current_user,
                        project=project,
                        selected_products=selected_products,
                        reference_image_paths=reference_image_paths,
                        reason=exc.code,
                        failed_generation=generation,
                    )
                except Exception as fallback_err:
                    logger.error("Composite fallback failed: %s", fallback_err)

            try:
                self.db.rollback()
            except Exception:
                pass
            try:
                self._persist_failure(
                    generation=generation,
                    current_user=current_user,
                    project=project,
                    error_code="TIMEOUT_SUSPECTED" if is_timeout else exc.code,
                    error_message=safe_provider_message,
                    latency_ms=latency_ms,
                )
            except Exception as persist_err:
                logger.error(
                    "PERSIST_FAILURE_STATE_FAILED generation_id=%s provider=%s error_type=%s: %s",
                    getattr(generation, "id", None),
                    generation.provider,
                    type(persist_err).__name__,
                    _sanitize_error_message(str(persist_err)),
                )
            vn_message = safe_provider_message or ""
            if exc.code == "CLOUDFLARE_IMAGE_AUTH_ERROR":
                vn_message = "Lỗi xác thực Cloudflare API Token. Vui lòng kiểm tra lại cấu hình."
            elif exc.code == "CLOUDFLARE_IMAGE_DAILY_QUOTA_EXCEEDED":
                vn_message = "Hạn mức 10.000 Neurons miễn phí hôm nay của tài khoản Cloudflare Free đã chạm trần (Mã lỗi 4006 từ Cloudflare). Hạn mức sẽ tự động được làm mới (reset) lúc 00:00 UTC (tương đương 07:00 sáng mai giờ Việt Nam)."
            elif exc.code == "CLOUDFLARE_IMAGE_RATE_LIMIT_OR_BUSY":
                vn_message = "Máy chủ Cloudflare AI đang xử lý quá nhiều yêu cầu đồng thời (Mã lỗi 3040 - Rate Limit). Hạn mức ngày vẫn còn, vui lòng đợi 30 - 60 giây rồi thử lại."
            elif exc.code == "CLOUDFLARE_IMAGE_QUOTA_ERROR":
                vn_message = "Hạn mức tạo ảnh Cloudflare Workers AI hôm nay đã hết. Vui lòng thử lại vào 07:00 sáng mai (giờ Việt Nam)."
            elif exc.code in ("CLOUDFLARE_IMAGE_SERVER_ERROR", "502", "503", "504"):
                vn_message = "Máy chủ Cloudflare AI hiện đang quá tải hoặc gặp sự cố. Vui lòng thử lại sau giây lát."
            elif is_timeout:
                vn_message = "Quá thời gian chờ phản hồi từ Cloudflare AI (Timeout). Vui lòng thử lại."
            elif not vn_message:
                vn_message = f"Không thể tạo ảnh từ Cloudflare FLUX ({exc.code})."

            diagnostic = f"{exc.code}: {vn_message}"
            status_code = status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_503_SERVICE_UNAVAILABLE
            raise HTTPException(status_code=status_code, detail=diagnostic) from exc
        except HTTPException as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            if reservation is not None:
                quota_service.release_reservation(
                    reservation,
                    error_code="HTTP_EXCEPTION",
                    error_message=str(exc.detail),
                )
            try:
                self._persist_failure(
                    generation=generation,
                    current_user=current_user,
                    project=project,
                    error_code="GENERATION_REJECTED",
                    error_message=str(exc.detail),
                    latency_ms=latency_ms,
                )
            except Exception as persist_err:
                logger.error("Failed to persist failure for generation %s: %s", getattr(generation, "id", None), persist_err)
            raise
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            safe_message = _sanitize_error_message(str(exc)) or "Internal design generation error"
            is_timeout = "timeout" in str(exc).lower() or isinstance(exc, TimeoutError)
            if reservation is not None:
                quota_service.release_reservation(
                    reservation,
                    error_code="INTERNAL_GENERATION_ERROR",
                    error_message=safe_message,
                    is_timeout=is_timeout,
                )
            logger.error(
                "design_generation_unexpected_failed provider=%s model=%s project_id=%s generation_id=%s error_type=%s error_code=INTERNAL_GENERATION_ERROR error_message=%s",
                generation.provider,
                generation.model,
                project.id,
                getattr(generation, "id", None),
                type(exc).__name__,
                safe_message,
            )
            try:
                self.db.rollback()
            except Exception:
                pass
            try:
                self._persist_failure(
                    generation=generation,
                    current_user=current_user,
                    project=project,
                    error_code="TIMEOUT_SUSPECTED" if is_timeout else "INTERNAL_GENERATION_ERROR",
                    error_message=safe_message,
                    latency_ms=latency_ms,
                )
            except Exception as persist_err:
                logger.error(
                    "PERSIST_FAILURE_STATE_FAILED generation_id=%s provider=%s error_type=%s: %s",
                    getattr(generation, "id", None),
                    generation.provider,
                    type(persist_err).__name__,
                    _sanitize_error_message(str(persist_err)),
                )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="INTERNAL_GENERATION_ERROR",
            ) from exc

    def _get_owned_project(self, current_user: User, project_id: int) -> RoomProject:
        project = (
            self.db.query(RoomProject)
            .filter(RoomProject.id == project_id, RoomProject.user_id == current_user.id, RoomProject.status != "ARCHIVED")
            .first()
        )
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room project not found")
        return project

    def _select_products(
        self,
        product_ids: list[int],
        recommended_by_id: dict[int, Product],
        selection_mode: str = "AUTO",
        effective_pref: Any | None = None,
    ) -> list[Product]:
        products = self.db.query(Product).filter(Product.id.in_(product_ids), Product.is_active == True).all()
        products_map = {p.id: p for p in products}

        missing_ids = [pid for pid in product_ids if pid not in products_map]
        if missing_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_PRODUCT_IDS")

        is_manual = (selection_mode or "").upper() == "MANUAL"
        if not is_manual:
            not_recommended = [
                pid for pid in product_ids
                if pid not in recommended_by_id
            ]
            if not_recommended:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PRODUCT_NOT_RECOMMENDED")

        return [products_map[pid] for pid in product_ids]

    def _generate(
        self,
        source_image_path: Path,
        prompt: str,
        reference_image_paths: list[Path],
        reference_categories: list[str | None] | None = None,
    ):
        if getattr(self.image_provider, "supports_categories", False):
            return self.image_provider.generate_design(
                source_image_path,
                prompt,
                reference_image_paths=reference_image_paths,
                reference_categories=reference_categories,
            )
        if getattr(self.image_provider, "MAX_INPUT_IMAGES", 1) > 1:
            return self.image_provider.generate_design(source_image_path, prompt, reference_image_paths=reference_image_paths)
        return self.image_provider.generate_design(source_image_path, prompt)

    def _resolve_reference_images(
        self,
        selected_products: list[Product],
    ) -> tuple[list[Path], list[tuple[int, Product]], list[int], list[int]]:
        max_references = max(0, getattr(self.image_provider, "MAX_INPUT_IMAGES", 4) - 1)
        storage = ProductImageStorageService()
        is_composite = getattr(self.image_provider, "provider_name", "") == "composite"

        # Step 1: Detect available readable primary images on disk
        valid_candidates: list[tuple[Product, Path]] = []
        missing_ids: list[int] = []
        project_root = Path(__file__).resolve().parents[3]
        clean_refs_dirs = [
            project_root / "storage" / "product_references_clean",
            Path(__file__).resolve().parents[1] / "ai" / "skill_bridge" / "product_references_clean",
        ]

        for product in selected_products:
            if is_composite:
                picked = self._pick_compositible_product_image(product, storage)
                if picked is not None:
                    valid_candidates.append((product, picked[1]))
                else:
                    missing_ids.append(product.id)
            else:
                # 1. First priority: Check clean reference repository (authentic, focused crop, 512px)
                clean_path = None
                p_slug = getattr(product, "slug", "") or ""
                for c_dir in clean_refs_dirs:
                    if c_dir.is_dir() and p_slug:
                        for ext in (".jpg", ".png", ".webp"):
                            cand = c_dir / f"{product.id}_{p_slug}{ext}"
                            if cand.is_file():
                                clean_path = cand
                                break
                    if clean_path is not None:
                        break

                if clean_path is not None and clean_path.is_file():
                    valid_candidates.append((product, clean_path))
                    continue

                # 2. Second priority: Fallback to genuine primary product image
                image = self._primary_product_image(product)
                try:
                    path = storage.resolve(image.image_url) if image is not None else None
                except Exception:
                    path = None
                if image is None or path is None or not path.is_file():
                    missing_ids.append(product.id)
                else:
                    path_str = str(path).lower()
                    if any(bad in path_str for bad in ["generated-demo", "demo", "placeholder", "dummy", "thumbnail"]):
                        missing_ids.append(product.id)
                    else:
                        valid_candidates.append((product, path))

        # Step 2: Stable-sort candidates by anchor furniture priority
        # (sofa > bedding > storage > table > chair > rug > lighting > wall-decor > accessories).
        # Python's sorted() is stable, preserving original user selection order within the same category priority tier.
        prioritized_candidates = sorted(
            valid_candidates,
            key=lambda item: get_category_reference_priority(item[0]),
        )

        # Step 3: Cap at max_references
        selected_references = prioritized_candidates[:max_references]

        reference_image_paths: list[Path] = []
        reference_mapping: list[tuple[int, Product]] = []
        included_ids: list[int] = []

        for index, (product, path) in enumerate(selected_references, start=1):
            reference_image_paths.append(path)
            reference_mapping.append((index, product))
            included_ids.append(product.id)

        return reference_image_paths, reference_mapping, included_ids, missing_ids

    def _primary_product_image(self, product: Product) -> ProductImage | None:
        primary = next((image for image in product.images if image.is_primary), None)
        if primary is not None:
            return primary
        if product.images:
            return sorted(product.images, key=lambda image: image.sort_order)[0]
        return None

    def _log_reference_diagnostics(
        self,
        selected_products: list[Product],
        included_ids: list[int],
        missing_ids: list[int],
        reference_image_count: int,
    ) -> None:
        logger.info(
            "design_generation_references provider=%s model=%s room_reference=true selected_products=%d reference_images_sent=%d selected_product_ids=%s product_ids_with_images=%s product_ids_missing_images=%s",
            getattr(self.image_provider, "provider_name", "unknown"),
            getattr(self.image_provider, "model_name", "unknown"),
            len(selected_products),
            reference_image_count,
            [product.id for product in selected_products],
            included_ids,
            missing_ids,
        )

    def _generation_load_options(self):
        return joinedload(RoomDesignGeneration.products).joinedload(Product.category)

    def _log_usage(
        self,
        current_user: User,
        project: RoomProject,
        provider: str,
        model: str,
        status: str,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.db.add(
            AIUsageLog(
                user_id=current_user.id,
                room_project_id=project.id,
                provider=provider,
                model=model,
                task_type="ROOM_DESIGN_GENERATION",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=latency_ms,
                error_code=error_code,
                status=status,
                error_message=error_message,
            )
        )

    def _persist_failure(
        self,
        generation: RoomDesignGeneration,
        current_user: User,
        project: RoomProject,
        error_code: str,
        error_message: str | None,
        latency_ms: int,
    ) -> None:
        try:
            self.db.rollback()
        except Exception:
            pass
        try:
            generation.status = "FAILED"
            generation.error_code = error_code
            generation.error_message = error_message
            generation.latency_ms = latency_ms
            self.db.add(generation)
            self._log_usage(
                current_user=current_user,
                project=project,
                provider=generation.provider,
                model=generation.model,
                status="FAILED",
                latency_ms=latency_ms,
                error_code=error_code,
                error_message=error_message,
            )
            self.db.commit()
        except Exception as persist_exc:
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.error(
                "PERSIST_FAILURE_STATE_FAILED generation_id=%s provider=%s error_type=%s: %s",
                getattr(generation, "id", None),
                getattr(generation, "provider", None),
                type(persist_exc).__name__,
                _sanitize_error_message(str(persist_exc)),
            )

    def _postprocess_preserve_background(
        self,
        source_image_path: Path,
        ai_image_data: bytes,
    ) -> bytes:
        """Kỹ thuật bảo toàn nền cục bộ (Local Background Preservation).

        Chiến lược:
        1. Kiểm tra độ lệch kiến trúc vùng trần nhà & tường trên (top 20% của phòng).
        2. Nếu độ lệch thấp (top_diff < 0.15): góc máy và trần nhà đã rất khớp.
           Áp dụng blending chuyển tiếp êm dịu (cosine soft fade, độ mờ nhẹ 0.45) ở 15% trên cùng
           để giữ 100% màu sơn và vân trần nguyên bản mà không chạm vào vùng nội thất hay mặt sàn.
        3. Nếu độ lệch cao (top_diff >= 0.15) hoặc có lỗi hình học:
           TUYỆT ĐỐI KHÔNG ép giữ nền để tránh tạo viền cắt ghép hay bóng đổ giả.
           Giữ nguyên 100% kết quả tự nhiên do AI tạo.
        """
        from io import BytesIO
        from PIL import Image
        import numpy as np

        try:
            with Image.open(source_image_path) as src_im:
                src_rgb = src_im.convert("RGB")
            with Image.open(BytesIO(ai_image_data)) as ai_im:
                ai_rgb = ai_im.convert("RGB")

            target_w, target_h = ai_rgb.size
            if src_rgb.size != (target_w, target_h):
                src_resized = src_rgb.resize((target_w, target_h), Image.Resampling.LANCZOS)
            else:
                src_resized = src_rgb

            src_arr = np.array(src_resized, dtype=np.float32)
            ai_arr = np.array(ai_rgb, dtype=np.float32)

            # Check alignment on ceiling / upper wall (top 20%)
            check_h = max(10, int(target_h * 0.20))
            top_diff = float(np.mean(np.abs(src_arr[:check_h, :] - ai_arr[:check_h, :])) / 255.0)

            # Only blend if natural alignment is verified (drift < 15%)
            if top_diff < 0.15:
                pure_top = max(2, int(target_h * 0.08))   # Top 8%
                fade_end = max(4, int(target_h * 0.20))   # Fade zone up to 20%
                mask = np.zeros((target_h, target_w), dtype=np.float32)
                mask[:pure_top, :] = 0.45  # 45% max source blend to maintain natural light
                for y in range(pure_top, fade_end):
                    t = (y - pure_top) / max(1, fade_end - pure_top)
                    mask[y, :] = 0.45 * 0.5 * (1.0 + np.cos(t * np.pi))

                blended = src_arr * mask[:, :, np.newaxis] + ai_arr * (1.0 - mask[:, :, np.newaxis])
                blended = np.clip(blended, 0, 255).astype(np.uint8)

                result_im = Image.fromarray(blended, "RGB")
                buf = BytesIO()
                result_im.save(buf, format="JPEG", quality=95, optimize=True)
                logger.info(
                    "Applied gentle background preservation post-processing (top_diff=%.3f, blend=top20%%)",
                    top_diff,
                )
                return buf.getvalue()
            else:
                logger.info(
                    "Skipped background preservation: top architectural drift %.3f >= 0.15 threshold",
                    top_diff,
                )
                return ai_image_data
        except Exception as exc:
            logger.warning("Background preservation post-processing exception: %s", exc)
            return ai_image_data

