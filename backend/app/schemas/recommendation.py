from pydantic import BaseModel

from app.schemas.product import ProductRead
from app.schemas.room_preference import RoomPreferenceRead


class ProductRecommendationRead(BaseModel):
    product: ProductRead
    score: float
    reasons: list[str]
    breakdown: dict[str, float]


class RecommendationResponse(BaseModel):
    room_project_id: int
    analysis_id: int
    preference: RoomPreferenceRead
    total: int
    items: list[ProductRecommendationRead]
