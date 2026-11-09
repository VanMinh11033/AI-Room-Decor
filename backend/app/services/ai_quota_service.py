import contextlib
from datetime import UTC, datetime, timedelta
import logging
import threading

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AIUsageLog, RoomAnalysis, RoomDesignGeneration

logger = logging.getLogger(__name__)

CLOUD_PROVIDERS = {"gemini", "cloudflare", "openai", "qwencloud"}

_local_locks: dict[str, threading.Lock] = {}
_local_lock_guard = threading.Lock()


def _get_threading_lock(name: str) -> threading.Lock:
    with _local_lock_guard:
        if name not in _local_locks:
            _local_locks[name] = threading.Lock()
        return _local_locks[name]


class AIQuotaService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @contextlib.contextmanager
    def _advisory_lock(self, lock_name: str, timeout_seconds: int = 5):
        """
        Khóa đồng bộ đa tầng: Threading Lock cho các request trong cùng process,
        kết hợp MySQL GET_LOCK cho multi-process / đa kết nối database.
        Đảm bảo tính nguyên tử tuyệt đối khi kiểm tra và đặt chỗ quota.
        """
        is_mysql = False
        try:
            bind = self.db.get_bind()
            if bind and "mysql" in bind.dialect.name:
                is_mysql = True
        except Exception:
            pass

        safe_name = f"ai_lock_{lock_name}"[:64]
        thread_lock = _get_threading_lock(safe_name)
        thread_acquired = thread_lock.acquire(timeout=timeout_seconds)
        if not thread_acquired:
            logger.warning("Failed to acquire thread lock for %s within %ss", safe_name, timeout_seconds)
            yield False
            return

        mysql_acquired = False
        if is_mysql:
            try:
                res = self.db.execute(
                    text("SELECT GET_LOCK(:lock_name, :timeout)"),
                    {"lock_name": safe_name, "timeout": timeout_seconds},
                ).scalar()
                mysql_acquired = (res == 1)
                if not mysql_acquired:
                    logger.warning("Failed to acquire MySQL GET_LOCK for %s within %ss", safe_name, timeout_seconds)
            except Exception as exc:
                logger.error("Error executing GET_LOCK for %s: %s", safe_name, exc)
                mysql_acquired = False

        acquired = mysql_acquired if is_mysql else thread_acquired
        try:
            yield acquired
        finally:
            if is_mysql and mysql_acquired:
                try:
                    self.db.execute(
                        text("SELECT RELEASE_LOCK(:lock_name)"),
                        {"lock_name": safe_name},
                    )
                except Exception as exc:
                    logger.error("Error releasing MySQL lock %s: %s", safe_name, exc)
            if thread_acquired:
                thread_lock.release()

    @contextlib.contextmanager
    def project_lock(self, project_id: int, timeout_seconds: int = 5):
        """Khóa dự án trong thời gian ngắn (vài ms) khi kiểm tra và tạo in-flight task."""
        lock_name = f"project_{project_id}"
        with self._advisory_lock(lock_name, timeout_seconds=timeout_seconds) as acquired:
            yield acquired

    def is_cloud_ai_enabled(self) -> bool:
        """Kiểm tra công tắc ngắt khẩn cấp (Emergency Kill Switch)."""
        return bool(settings.enable_cloud_ai)

    def check_in_flight_concurrency(self, project_id: int, task_type: str) -> None:
        """
        Chặn các yêu cầu AI trùng lặp hoặc chạy đồng thời trên cùng một dự án phòng.
        Tự động phục hồi nếu có yêu cầu cũ bị treo quá thời gian cho phép (stale in-flight).
        """
        now = datetime.now(UTC)
        timeout_threshold = now - timedelta(seconds=settings.ai_in_flight_timeout_seconds)

        if task_type == "ROOM_IMAGE_ANALYSIS":
            active_analysis = (
                self.db.query(RoomAnalysis)
                .filter(
                    RoomAnalysis.room_project_id == project_id,
                    RoomAnalysis.status == "ANALYZING",
                )
                .order_by(RoomAnalysis.created_at.desc())
                .first()
            )
            if active_analysis is not None:
                # Kiểm tra xem yêu cầu có còn trong ngưỡng timeout hay đã bị treo (stale)
                created_at = active_analysis.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)

                if created_at >= timeout_threshold:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="AI_ANALYSIS_IN_PROGRESS: Yêu cầu phân tích phòng đang được xử lý, vui lòng chờ.",
                    )
                else:
                    # Yêu cầu cũ bị treo/crash -> chuyển sang FAILED để không chặn yêu cầu mới
                    logger.warning(
                        "Recovering stale in-flight analysis id=%s for project_id=%s",
                        active_analysis.id,
                        project_id,
                    )
                    active_analysis.status = "FAILED"
                    active_analysis.error_code = "STALE_ANALYSIS_TIMEOUT"
                    active_analysis.error_message = "Quá thời gian xử lý cho phép (Stale lock recovered)."
                    self.db.commit()

        elif task_type == "ROOM_DESIGN_GENERATION":
            active_generation = (
                self.db.query(RoomDesignGeneration)
                .filter(
                    RoomDesignGeneration.room_project_id == project_id,
                    RoomDesignGeneration.status == "GENERATING",
                )
                .order_by(RoomDesignGeneration.created_at.desc())
                .first()
            )
            if active_generation is not None:
                created_at = active_generation.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)

                if created_at >= timeout_threshold:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="DESIGN_GENERATION_IN_PROGRESS: Yêu cầu tạo thiết kế đang được xử lý, vui lòng chờ.",
                    )
                else:
                    logger.warning(
                        "Recovering stale in-flight design generation id=%s for project_id=%s",
                        active_generation.id,
                        project_id,
                    )
                    active_generation.status = "FAILED"
                    active_generation.error_code = "STALE_GENERATION_TIMEOUT"
                    active_generation.error_message = "Quá thời gian tạo ảnh cho phép (Stale lock recovered)."
                    self.db.commit()

    def get_quota_limits(self, provider: str) -> tuple[int, int]:
        """
        Trả về (user_limit, system_limit) cấu hình theo provider từ environment settings.
        """
        prov = (provider or "").strip().lower()
        if prov == "gemini":
            return settings.gemini_daily_user_limit, settings.gemini_daily_system_limit
        if prov == "cloudflare":
            return settings.cloudflare_daily_user_limit, settings.cloudflare_daily_system_limit
        # Provider Cloud khác (OpenAI, QwenCloud...)
        return 5, 20

    def get_daily_usage(self, user_id: int | None, provider: str) -> tuple[int, int]:
        """
        Đếm số lượt đã tiêu thụ hoặc đang giữ chỗ trong ngày hôm nay (UTC).
        - Đối với System quota: Bao gồm SUCCESS, RESERVED (chưa stale) và TIMEOUT_SUSPECTED.
        - Đối với User quota: Bao gồm SUCCESS và RESERVED (chưa stale).
        """
        now = datetime.now(UTC)
        today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        stale_threshold = now - timedelta(seconds=settings.ai_in_flight_timeout_seconds)

        prov = (provider or "").strip().lower()

        is_mysql = False
        try:
            bind = self.db.get_bind()
            if bind and "mysql" in bind.dialect.name:
                is_mysql = True
        except Exception:
            pass

        # System query: đếm cả SUCCESS, RESERVED chưa stale và TIMEOUT_SUSPECTED để chặn thủng ngân sách
        system_base = self.db.query(AIUsageLog).filter(
            AIUsageLog.provider == prov,
            AIUsageLog.created_at >= today_start,
            (AIUsageLog.status == "SUCCESS")
            | ((AIUsageLog.status == "RESERVED") & (AIUsageLog.created_at >= stale_threshold))
            | (AIUsageLog.status == "TIMEOUT_SUSPECTED"),
        )
        if is_mysql:
            system_base = system_base.with_for_update(read=True)
        system_count = system_base.count()

        user_count = 0
        if user_id is not None:
            user_base = self.db.query(AIUsageLog).filter(
                AIUsageLog.user_id == user_id,
                AIUsageLog.provider == prov,
                AIUsageLog.created_at >= today_start,
                (AIUsageLog.status == "SUCCESS")
                | ((AIUsageLog.status == "RESERVED") & (AIUsageLog.created_at >= stale_threshold)),
            )
            if is_mysql:
                user_base = user_base.with_for_update(read=True)
            user_count = user_base.count()

        return user_count, system_count

    def reserve_quota(
        self,
        user_id: int,
        project_id: int,
        provider: str,
        model: str,
        task_type: str,
    ) -> AIUsageLog | None:
        """
        Kiểm tra và đặt chỗ quota nguyên tử trước khi gọi Cloud AI provider.
        - Sử dụng advisory lock trong thời gian ngắn (vài ms) để kiểm tra hạn mức.
        - Commit ngay bản ghi RESERVED xuống DB để các transaction khác nhìn thấy.
        - Giải phóng lock ngay lập tức TRƯỚC KHI gọi Cloud AI.
        - Trả về đối tượng AIUsageLog nếu thành công, None nếu hết quota hoặc tắt Kill switch.
        """
        prov = (provider or "").strip().lower()
        if prov not in CLOUD_PROVIDERS:
            # Các provider offline (local_fallback, composite) không bị tính quota Cloud
            return None

        if not self.is_cloud_ai_enabled():
            logger.info("Cloud AI is disabled via kill switch (ENABLE_CLOUD_AI=false).")
            return None

        lock_name = f"quota_{prov}"
        with self._advisory_lock(lock_name, timeout_seconds=5) as acquired:
            if not acquired:
                logger.warning("Could not acquire quota lock for provider=%s, rejecting reservation.", prov)
                return None

            user_limit, system_limit = self.get_quota_limits(prov)
            user_used, system_used = self.get_daily_usage(user_id, prov)

            if user_used >= user_limit:
                logger.warning(
                    "Daily AI quota reached for user_id=%s on provider=%s (%s/%s)",
                    user_id,
                    prov,
                    user_used,
                    user_limit,
                )
                return None

            if system_used >= system_limit:
                logger.warning(
                    "System daily AI quota reached on provider=%s (%s/%s)",
                    prov,
                    system_used,
                    system_limit,
                )
                return None

            # Đặt chỗ nguyên tử và commit ngay lập tức
            reservation = AIUsageLog(
                user_id=user_id,
                room_project_id=project_id,
                provider=prov,
                model=model,
                task_type=task_type,
                status="RESERVED",
            )
            self.db.add(reservation)
            self.db.commit()
            self.db.refresh(reservation)
            return reservation

    def finalize_success(
        self,
        reservation: AIUsageLog,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> None:
        """Chuyển trạng thái đặt chỗ thành công (SUCCESS) và cập nhật thông số tiêu thụ."""
        reservation.status = "SUCCESS"
        reservation.latency_ms = latency_ms
        reservation.input_tokens = input_tokens
        reservation.output_tokens = output_tokens
        reservation.total_tokens = total_tokens
        reservation.estimated_cost = estimated_cost
        self.db.commit()

    def release_reservation(
        self,
        reservation: AIUsageLog,
        error_code: str | None = None,
        error_message: str | None = None,
        status: str = "FAILED",
        is_timeout: bool = False,
    ) -> None:
        """
        Giải phóng chỗ đặt khi Cloud API thất bại hoặc chuyển sang Fallback.
        - Nếu is_timeout=True (không xác định kết quả phía provider): gán TIMEOUT_SUSPECTED để tính vào System quota.
        - Mặc định: FAILED (giải phóng quota).
        """
        final_status = "TIMEOUT_SUSPECTED" if is_timeout else status
        reservation.status = final_status
        reservation.error_code = error_code
        reservation.error_message = error_message
        self.db.commit()

