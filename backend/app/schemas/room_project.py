from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoomProjectCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    room_type: str | None = Field(None, max_length=100)


class RoomProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    room_type: str | None = None
    room_image_url: str | None = None
    image_original_filename: str | None = None
    image_content_type: str | None = None
    image_size_bytes: int | None = None
    status: str
    preference_configured: bool = False
    created_at: datetime
    updated_at: datetime


class RoomProjectListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RoomProjectRead]


class DominantColor(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    hex: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    percentage: int | None = Field(None, ge=0, le=100)


class DetectedObject(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    confidence: float = Field(..., ge=0, le=1)


class EmptyArea(BaseModel):
    location: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    suitable_for_decor: bool = True


class LightingAnalysis(BaseModel):
    type: str = Field(..., min_length=1, max_length=80)
    level: str = Field(..., min_length=1, max_length=80)


class RoomAnalysisResult(BaseModel):
    room_type: str | None = Field(None, max_length=100)
    dominant_colors: list[DominantColor] = Field(default_factory=list)
    existing_objects: list[DetectedObject] = Field(default_factory=list)
    empty_areas: list[EmptyArea] = Field(default_factory=list)
    lighting: LightingAnalysis | None = None
    design_characteristics: list[str] = Field(default_factory=list)
    layout_summary: str | None = None
    confidence: float = Field(..., ge=0, le=1)


class RoomAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_project_id: int
    user_id: int
    image_checksum: str
    status: str
    provider: str
    model: str
    room_type: str | None = None
    dominant_colors: list[DominantColor] = Field(default_factory=list)
    existing_objects: list[DetectedObject] = Field(default_factory=list)
    empty_areas: list[EmptyArea] = Field(default_factory=list)
    lighting: LightingAnalysis | None = None
    design_characteristics: list[str] = Field(default_factory=list)
    layout_summary: str | None = None
    confidence: Decimal | None = None
    error_code: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("dominant_colors", "existing_objects", "empty_areas", "design_characteristics", mode="before")
    @classmethod
    def default_null_lists(cls, value):
        return [] if value is None else value
