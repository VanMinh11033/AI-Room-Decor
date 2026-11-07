from datetime import datetime

from pydantic import BaseModel, Field


class ProductImageCandidateRead(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    source: str
    source_page_url: str | None = None
    image_url: str
    public_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    creator: str | None = None
    status: str
    width: int | None = None
    height: int | None = None
    file_format: str | None = None
    semantic_decision: str | None = None
    created_at: datetime


class ProductImageCandidateSearchRequest(BaseModel):
    product_id: int
    max_images: int = Field(3, ge=1, le=5)


class ProductImageCandidateSearchResponse(BaseModel):
    product_id: int
    staged: int
    skipped: int


class ProductImageCandidateListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductImageCandidateRead]
