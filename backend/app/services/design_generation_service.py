import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.ai.image.base import GeneratedImage, ImageProvider, ImageProviderError
from app.ai.image.composite_provider import CompositeImageProvider
from app.ai.image.prompt_builder import PROMPT_VERSION, build_design_generation_prompt
from app.models.entities import AIUsageLog, Product, ProductImage, RoomDesignGeneration, RoomProject, User
from app.schemas.design_generation import DesignGenerationCreate
from app.services.ai_quota_service import AIQuotaService
from app.services.recommendation_service import RecommendationService
from app.services.storage_service import GeneratedDesignStorageService, ProductImageStorageService, RoomImageStorageService

logger = logging.getLogger(__name__)

_SECRET_PATTERNS = re.compile(
    r"(?:Bearer\s+[^\s,;]+|sk-[a-zA-Z0-9_\-]{8,}|AIza[0-9A-Za-z\-_]{20,}|(?:token|key|secret|password)=[^\s&,;]+|secret-[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)


def _sanitize_error_message(message: str | None) -> str:
    if not message:
        return ""
    safe = _SECRET_PATTERNS.sub("[REDACTED]", str(message))
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
    ) -> RoomDesignGeneration | None:
        """
        Tìm kiếm bản thiết kế đã sinh thành công trước đó (Design Cache).
        - Cache theo: cùng user_id, room_project_id, room_image_path, tập hợp product_ids, provider, model, prompt_version, và prompt.
        - Prompt phản ánh đầy đủ RoomPreference (phong cách, ngân sách, màu sắc), phân tích phòng, và sản phẩm.
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

        for candidate in candidates:
            candidate_ids = {p.id for p in candidate.products}
            if candidate_ids == target_product_ids and len(candidate.products) == len(target_product_ids):
                # So khớp nội dung prompt chính xác (phản ánh phong cách, màu sắc, sở thích người dùng)
                if (candidate.prompt or "").strip() == (prompt or "").strip():
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

    def _generate_with_composite_fallback(
        self,
        current_user: User,
        project: RoomProject,
        selected_products: list[Product],
        reference_image_paths: list[Path],
        reason: str = "OFFLINE_FALLBACK",
        failed_generation: RoomDesignGeneration | None = None,
    ) -> RoomDesignGeneration:
        """
        Tự động tạo ảnh phối cảnh 2D bằng Pillow Compositor cục bộ khi Cloudflare hết quota, lỗi 429/5xx,
        hoặc khi công tắc khẩn cấp ENABLE_CLOUD_AI=false được kích hoạt.
        """
        started_at = perf_counter()
        composite_provider = CompositeImageProvider()
        source_image_path = RoomImageStorageService().resolve(project.room_image_path)

        categories = [
            p.category.slug if p.category and p.category.slug else "accessories"
            for p in selected_products[:len(reference_image_paths)]
        ]

        if reference_image_paths:
            provider_result = composite_provider.generate_design(
                source_image_path=source_image_path,
                prompt=f"[Chế độ Offline 2D - {reason}] Ghép ảnh nội thất trực tiếp bằng Pillow Compositor.",
                reference_image_paths=reference_image_paths,
                reference_categories=categories,
            )
        else:
            from PIL import Image
            import io
            with Image.open(source_image_path) as room_img:
                buf = io.BytesIO()
                room_img.convert("RGB").save(buf, format="PNG")
                composite_bytes = buf.getvalue()
            provider_result = GeneratedImage(data=composite_bytes, content_type="image/png")

        if failed_generation is not None:
            generation = failed_generation
            generation.provider = composite_provider.provider_name
            generation.model = composite_provider.model_name
            generation.prompt = f"[Chế độ Offline 2D - {reason}] Ghép ảnh nội thất trực tiếp bằng Pillow Compositor. Không sử dụng AI Cloud."
        else:
            generation = RoomDesignGeneration(
                room_project_id=project.id,
                user_id=current_user.id,
                status="GENERATING",
                provider=composite_provider.provider_name,
                model=composite_provider.model_name,
                prompt_version=PROMPT_VERSION,
                source_image_path=project.room_image_path,
                prompt=f"[Chế độ Offline 2D - {reason}] Ghép ảnh nội thất trực tiếp bằng Pillow Compositor. Không sử dụng AI Cloud.",
                products=selected_products,
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

    def create_generation(
        self,
        current_user: User,
        project_id: int,
        payload: DesignGenerationCreate,
    ) -> RoomDesignGeneration:
        project = self._get_owned_project(current_user, project_id)
        if not project.room_image_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ROOM_IMAGE_REQUIRED")

        preference, analysis, recommendations = RecommendationService(self.db).recommend_for_project(current_user, project_id, limit=50)
        recommended_by_id = {item.product.id: item.product for item in recommendations}
        selected_products = self._select_products(payload.product_ids, recommended_by_id)

        reference_image_paths, reference_mapping, included_ids, missing_ids = self._resolve_reference_images(selected_products)
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

        prompt = build_design_generation_prompt(project, analysis, preference, selected_products, reference_mapping)
        self._log_reference_diagnostics(selected_products, included_ids, missing_ids, len(reference_image_paths))

        # 1. Design Cache: Kiểm tra xem đã từng sinh ảnh tương tự trước đó chưa (bao gồm cả prompt & RoomPreference)
        if not getattr(payload, "force", False):
            cached = self._lookup_design_cache(
                user_id=current_user.id,
                project_id=project.id,
                room_image_path=project.room_image_path,
                product_ids=payload.product_ids,
                provider=self.image_provider.provider_name,
                model=self.image_provider.model_name,
                prompt=prompt,
                prompt_version=PROMPT_VERSION,
            )
            if cached is not None:
                return cached

        # 2. Concurrency Check & Reservation dưới Project Lock ngắn hạn
        quota_service = AIQuotaService(self.db)
        is_cloud = self.image_provider.provider_name in ("cloudflare", "gemini", "openai", "qwencloud")
        reservation = None

        with quota_service.project_lock(project.id):
            quota_service.check_in_flight_concurrency(project.id, "ROOM_DESIGN_GENERATION")

            # 3. Emergency Kill Switch check (ENABLE_CLOUD_AI=false)
            if is_cloud and not quota_service.is_cloud_ai_enabled():
                logger.info("Cloud AI disabled via ENABLE_CLOUD_AI=false, auto-falling back to Composite 2D")
                return self._generate_with_composite_fallback(
                    current_user=current_user,
                    project=project,
                    selected_products=selected_products,
                    reference_image_paths=reference_image_paths,
                    reason="CLOUD_AI_DISABLED",
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
                    # Quota chạm trần ngày (User limit hoặc System limit) -> Tự động chuyển Fallback Composite 2D
                    logger.info(
                        "Cloud AI quota reached for provider=%s user=%s, auto-falling back to Composite 2D",
                        self.image_provider.provider_name,
                        current_user.id,
                    )
                    return self._generate_with_composite_fallback(
                        current_user=current_user,
                        project=project,
                        selected_products=selected_products,
                        reference_image_paths=reference_image_paths,
                        reason="QUOTA_EXCEEDED",
                    )

            generation = RoomDesignGeneration(
                room_project_id=project.id,
                user_id=current_user.id,
                status="GENERATING",
                provider=self.image_provider.provider_name,
                model=self.image_provider.model_name,
                prompt_version=PROMPT_VERSION,
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
            provider_result = self._generate(source_image_path, prompt, reference_image_paths)
            stored = GeneratedDesignStorageService().save(
                provider_result.data,
                provider_result.content_type,
                current_user.id,
                project.id,
                generation.id,
            )
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
            if not is_timeout:
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
            diagnostic = f"{exc.code}: {safe_provider_message}" if safe_provider_message else exc.code
            status_code = status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_503_SERVICE_UNAVAILABLE
            raise HTTPException(status_code=status_code, detail=diagnostic) from exc
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

    def _select_products(self, product_ids: list[int], recommended_by_id: dict[int, Product]) -> list[Product]:
        missing_ids = [product_id for product_id in product_ids if product_id not in recommended_by_id]
        if missing_ids:
            existing_count = self.db.query(Product).filter(Product.id.in_(missing_ids)).count()
            detail = "PRODUCT_NOT_RECOMMENDED" if existing_count == len(set(missing_ids)) else "INVALID_PRODUCT_IDS"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        return [recommended_by_id[product_id] for product_id in product_ids]

    def _generate(self, source_image_path: Path, prompt: str, reference_image_paths: list[Path]):
        if getattr(self.image_provider, "MAX_INPUT_IMAGES", 1) > 1:
            return self.image_provider.generate_design(source_image_path, prompt, reference_image_paths=reference_image_paths)
        return self.image_provider.generate_design(source_image_path, prompt)

    def _resolve_reference_images(
        self,
        selected_products: list[Product],
    ) -> tuple[list[Path], list[tuple[int, Product]], list[int], list[int]]:
        max_references = max(0, getattr(self.image_provider, "MAX_INPUT_IMAGES", 1) - 1)
        storage = ProductImageStorageService()

        # Step 1: Detect available readable primary images on disk
        valid_candidates: list[tuple[Product, Path]] = []
        missing_ids: list[int] = []
        for product in selected_products:
            image = self._primary_product_image(product)
            path = storage.resolve(image.image_url) if image is not None else None
            if image is None or path is None or not path.is_file():
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

