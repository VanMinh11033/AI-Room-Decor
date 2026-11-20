from typing import Any, Optional
from pydantic import BaseModel

from app.schemas.product import ProductRead
from app.schemas.room_preference import RoomPreferenceRead


class ProductRecommendationRead(BaseModel):
    product: ProductRead
    score: float
    role: Optional[str] = None
    boost: Optional[float] = 0.0
    penalty: Optional[float] = 0.0
    reasons: list[str]
    breakdown: dict[str, float]
    provenance: Optional[dict[str, Any]] = None


class RecommendationResponse(BaseModel):
    room_project_id: int
    analysis_id: int
    preference: RoomPreferenceRead
    total: int
    items: list[ProductRecommendationRead]
    bundle: Optional[dict[str, Any]] = None
    effective_preference: Optional[dict[str, Any]] = None
    recommendation_version: Optional[str] = "v1.5"
