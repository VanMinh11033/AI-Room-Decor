from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.product import ProductRead


class DesignGenerationCreate(BaseModel):
    product_ids: list[int] = Field(..., min_length=1, max_length=12)
    force: bool = Field(False, description="Bắt buộc tạo mới, bỏ qua cache nếu đã tồn tại")

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
    error_code: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    completed_at: datetime | None = None
    products: list[ProductRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DesignGenerationListResponse(BaseModel):
    total: int
    items: list[DesignGenerationRead]
