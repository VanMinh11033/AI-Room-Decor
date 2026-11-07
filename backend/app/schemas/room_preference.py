from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.catalog import CatalogRead, ColorRead
from app.schemas.category import CategoryRead


class RoomPreferencePayload(BaseModel):
    budget_min: Decimal | None = Field(None, ge=0)
    budget_max: Decimal | None = Field(None, ge=0)
    currency: str = Field("VND", min_length=3, max_length=10)
    purpose: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=1000)
    style_ids: list[int] = Field(default_factory=list)
    color_ids: list[int] = Field(default_factory=list)
    material_ids: list[int] = Field(default_factory=list)
    category_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_budget_range(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min must be less than or equal to budget_max")
        return self


class RoomPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_project_id: int
    user_id: int
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: str
    purpose: str | None = None
    notes: str | None = None
    styles: list[CatalogRead] = Field(default_factory=list)
    colors: list[ColorRead] = Field(default_factory=list)
    materials: list[CatalogRead] = Field(default_factory=list)
    categories: list[CategoryRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
