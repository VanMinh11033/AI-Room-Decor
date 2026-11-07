from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=140)
    description: str | None = None
    is_active: bool = True


class CatalogCreate(CatalogBase):
    pass


class CatalogUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    slug: str | None = Field(None, min_length=2, max_length=140)
    description: str | None = None
    is_active: bool | None = None


class ColorCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    slug: str = Field(..., min_length=2, max_length=140)
    hex_code: str | None = Field(None, max_length=20)
    is_active: bool = True


class ColorUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    slug: str | None = Field(None, min_length=2, max_length=140)
    hex_code: str | None = Field(None, max_length=20)
    is_active: bool | None = None


class CatalogRead(CatalogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ColorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    hex_code: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CatalogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CatalogRead]


class ColorListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ColorRead]

