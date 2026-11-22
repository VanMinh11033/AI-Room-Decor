"""
HỆ THỐNG QUẢN LÝ BẢO TRÌ & ĐÓNG BĂNG TẠO ĐƠN HÀNG (P0 ORDER MAINTENANCE GATE)
Tuân thủ nghiêm ngặt nguyên tắc an toàn:
1. Khi bảo trì kích hoạt:
   - Chặn toàn bộ thao tác ghi/tạo/hủy đơn hàng (POST /api/orders, cancel, v.v.).
   - Trả HTTP 503 Service Unavailable kèm Retry-After header.
   - Không chạm vào DB session của đơn hàng, không trừ tồn kho (Stock), không xóa Cart, không tạo OrderItem.
2. Cho phép tất cả các thao tác đọc an toàn:
   - Auth, Catalog, Cart lookup, Product browsing, AI Room Decor Skill.
3. Hỗ trợ kích hoạt linh hoạt qua:
   - Cấu hình tĩnh: Biến môi trường ORDER_MAINTENANCE_MODE=true trên Render.
   - Điều khiển động thời gian thực: API Admin toggle (không cần restart container).
4. Cung cấp endpoint công khai để probe trạng thái thực tế phục vụ pre-flight check của runner migration.
"""

from datetime import datetime, timezone
import logging
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

# Biến ghi đè runtime trong bộ nhớ (hỗ trợ bật/tắt tức thì không cần restart container)
_runtime_order_maintenance_override: bool | None = None


def is_order_maintenance_active() -> bool:
    """
    Kiểm tra trạng thái đóng băng tạo đơn hàng.
    Quy tắc an toàn P0:
    - Nếu biến môi trường máy chủ (ORDER_MAINTENANCE_MODE=true) đang bật:
      LUÔN trả về True (bắt buộc duy trì bảo trì, runtime override KHÔNG được phép tắt).
    - Nếu biến môi trường không bật:
      Cho phép kiểm tra runtime override để bật bảo trì tạm thời.
    """
    if bool(settings.order_maintenance_mode):
        return True
    if _runtime_order_maintenance_override is not None:
        return _runtime_order_maintenance_override
    return False


def set_order_maintenance_mode(active: bool) -> None:
    """Bật/tắt runtime override đóng băng tạo đơn."""
    global _runtime_order_maintenance_override
    if bool(settings.order_maintenance_mode) and not active:
        logger.warning(
            "[P0 MAINTENANCE GATE] Từ chối tắt bảo trì qua runtime: "
            "Biến môi trường ORDER_MAINTENANCE_MODE=true đang có hiệu lực bắt buộc trên server."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tắt chế độ bảo trì vì biến môi trường ORDER_MAINTENANCE_MODE=true đang được cấu hình bắt buộc trên máy chủ.",
        )
    _runtime_order_maintenance_override = bool(active)
    logger.warning(
        "[P0 MAINTENANCE GATE] Order maintenance mode switched to: %s (runtime override)",
        _runtime_order_maintenance_override,
    )


def reset_order_maintenance_mode() -> None:
    """Xóa runtime override, quay về giá trị trong settings."""
    global _runtime_order_maintenance_override
    _runtime_order_maintenance_override = None
    logger.info("[P0 MAINTENANCE GATE] Reset order maintenance mode to settings default: %s", settings.order_maintenance_mode)


def get_order_maintenance_status() -> dict:
    """Trả về trạng thái chi tiết của Maintenance Gate phục vụ giám sát và probe HTTP."""
    active = is_order_maintenance_active()
    env_enforced = bool(settings.order_maintenance_mode)
    return {
        "order_maintenance_active": active,
        "status": "MAINTENANCE_ACTIVE" if active else "OPERATIONAL",
        "message": (
            settings.order_maintenance_message
            if active
            else "Hệ thống đặt hàng hoạt động bình thường."
        ),
        "env_enforced": env_enforced,
        "config_default": settings.order_maintenance_mode,
        "runtime_override": _runtime_order_maintenance_override,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def require_order_writable() -> None:
    """
    FastAPI Dependency: Bắt buộc hệ thống phải ở trạng thái writable đối với đơn hàng.
    Nếu đang trong maintenance window, ngắt ngay lập tức với HTTP 503 SERVICE UNAVAILABLE.
    KHÔNG chạm vào Database session, KHÔNG trừ stock, KHÔNG xóa cart.
    """
    if is_order_maintenance_active():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=settings.order_maintenance_message,
            headers={
                "Retry-After": "300",
                "X-Maintenance-Mode": "ORDER_CREATION_FREEZE",
            },
        )
