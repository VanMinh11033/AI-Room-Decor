from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.product import ProductRead


class ProductPlacement(BaseModel):
    product_id: int
    x: int | None = Field(None, description="Tọa độ X (pixel) trên ảnh phòng")
    y: int | None = Field(None, description="Tọa độ Y (pixel) trên ảnh phòng")
    width: int | None = Field(None, description="Chiều rộng (pixel) của sản phẩm")
    x_ratio: float | None = Field(None, description="Tọa độ X chuẩn hóa (0.0 - 1.0)")
    y_ratio: float | None = Field(None, description="Tọa độ Y chuẩn hóa (0.0 - 1.0)")
    width_ratio: float | None = Field(None, description="Chiều rộng chuẩn hóa so với phòng (0.1 - 0.9)")


class DesignGenerationCreate(BaseModel):
    product_ids: list[int] = Field(..., min_length=1, max_length=12)
    force: bool = Field(False, description="Bắt buộc tạo mới, bỏ qua cache nếu đã tồn tại")
    placements: list[ProductPlacement] | None = Field(None, description="Tùy chọn vị trí và kích thước đặt sản phẩm")
    light_direction: str | None = Field("auto", description="Hướng sáng: auto, left, right, overhead")
    shadow_intensity: float | None = Field(0.72, ge=0.2, le=1.0, description="Độ đậm bóng đổ (0.2 - 1.0)")
    floor_horizon_ratio: float | None = Field(None, ge=0.2, le=0.95, description="Độ cao chân trời sàn phòng")
    generation_mode: str | None = Field(
        None,
        description="Chế độ tạo thiết kế: CATALOG_ACCURATE (chuẩn Catalog) hoặc AI_PHOTOREALISTIC_PREVIEW (concept AI chân thực)",
    )
    selection_mode: str | None = Field(
        "AUTO",
        description="Chế độ chọn nội thất: AUTO (AI đề xuất) hoặc MANUAL (Khách hàng tự chọn)",
    )

    @field_validator("product_ids")
    @classmethod
    def reject_duplicate_products(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate product IDs are not allowed")
        return value


class DesignGenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_project_id: int
    user_id: int
    status: str
    provider: str
    model: str
    prompt_version: str
    source_image_path: str
    generated_image_url: str | None = None
    generated_image_path: str | None = None
    generation_mode: str = Field("CATALOG_ACCURATE", description="Chế độ tạo: CATALOG_ACCURATE hoặc AI_PHOTOREALISTIC_PREVIEW")
    is_ai_preview: bool = Field(False, description="Đánh dấu ảnh AI concept preview")
    verification_status: str | None = Field(None, description="Trạng thái xác thực: VERIFIED, NEEDS_REVIEW, REJECTED, COMPOSITE_FALLBACK")
    verification_details: dict[str, Any] | None = Field(default_factory=dict, description="Chi tiết đối chiếu sản phẩm")
    quality_score: float | None = Field(None, description="Điểm chất lượng kiểm định độc lập (0 - 100)")
    warnings: list[str] = Field(default_factory=list, description="Cảnh báo kiểm định hoặc tỷ lệ")
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    completed_at: datetime | None = None
    selection_mode: str | None = "AUTO"
    total_price: float | None = None
    products: list[ProductRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DesignGenerationListResponse(BaseModel):
    total: int
    items: list[DesignGenerationRead]
