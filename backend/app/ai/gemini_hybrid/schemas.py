from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LightingAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(..., description="Loại ánh sáng (natural daylight, artificial, mixed)")
    direction: Literal["left", "right", "overhead", "ambient"] = Field(
        "ambient", description="Hướng chiếu sáng chủ đạo"
    )
    level: str = Field("medium", description="Cường độ ánh sáng (bright, medium, dim)")
    color_temp: Literal["warm", "neutral", "cool"] = Field(
        "neutral", description="Nhiệt độ màu ánh sáng"
    )


class FloorAreaSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visible: bool = Field(True, description="Mặt sàn có nhìn thấy rõ trong ảnh không")
    horizon_ratio: float = Field(
        0.65, ge=0.2, le=0.95, description="Độ cao đường chân trời sàn (tỷ lệ 0.2 - 0.95)"
    )
    floor_material: str | None = Field(None, description="Vật liệu sàn (wood, tile, concrete, carpet)")


class DecorSpot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    location: str = Field(..., description="Vị trí đặt nội thất (center floor, left corner, right corner, wall)")
    description: str | None = Field(None, description="Mô tả không gian trống")
    suitable_categories: list[str] = Field(default_factory=list, description="Phân loại phù hợp")


class GeminiRoomAnalysisSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    room_type: str = Field(..., description="Loại phòng được phát hiện (living room, empty room, bedroom, etc.)")
    layout_summary: str = Field(..., description="Tóm tắt bố cục không gian dựa trên bằng chứng ảnh")
    floor_area: FloorAreaSchema = Field(default_factory=FloorAreaSchema)
    lighting: LightingAnalysisSchema = Field(
        default_factory=lambda: LightingAnalysisSchema(type="natural daylight", direction="ambient", level="bright", color_temp="neutral")
    )
    dominant_colors: list[str] = Field(default_factory=list, description="Danh sách màu sắc chủ đạo")
    decor_spots: list[DecorSpot] = Field(default_factory=list, description="Các vị trí khả dụng để bố trí đồ đạc")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Độ tin cậy của phân tích thị giác")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float, values: Any) -> float:
        # Nếu không thấy mặt sàn, độ tin cậy của bài toán bố trí nội thất không được vượt quá 0.5
        return round(v, 3)


class PlannedPlacement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: int = Field(..., description="Mã ID sản phẩm catalog chính xác")
    category: str | None = Field(None, description="Phân loại nội thất")
    x_ratio: float = Field(..., ge=0.02, le=0.98, description="Tọa độ tâm ngang X (0.02 - 0.98)")
    y_ratio: float = Field(..., ge=0.20, le=0.98, description="Tọa độ đáy chân đế Y (0.20 - 0.98)")
    width_ratio: float = Field(..., ge=0.08, le=0.90, description="Tỷ lệ chiều rộng so với chiều rộng phòng (0.08 - 0.90)")
    z_index: int = Field(..., ge=0, le=10, description="Thứ tự lớp hiển thị từ xa đến gần")
    reasoning: str | None = Field(None, description="Lý do bố trí vị trí này")


class GeminiLayoutPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    placements: list[PlannedPlacement] = Field(default_factory=list)
    light_direction: str = Field("auto")
    shadow_intensity: float = Field(0.72, ge=0.2, le=1.0)
    floor_horizon_ratio: float = Field(0.65, ge=0.2, le=0.95)
    plan_notes: str | None = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED", "COMPOSITE_FALLBACK"]
    is_catalog_exact: bool = Field(False, description="100% pixel sản phẩm lấy từ Catalog thật")
    is_ai_preview: bool = Field(False, description="Ảnh do AI tạo concept")
    matched_product_count: int
    expected_product_count: int
    architecture_drift_score: float = Field(0.0, ge=0.0, le=1.0, description="Mức độ thay đổi kiến trúc phòng (0: không đổi, 1: đổi hoàn toàn)")
    product_fidelity_score: float = Field(1.0, ge=0.0, le=1.0, description="Độ tương đồng màu sắc / nhận diện sản phẩm")
    notes: list[str] = Field(default_factory=list)
