from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.entities import ProductImageCandidate, User
from app.schemas.product_image_candidate import (
    ProductImageCandidateListResponse,
    ProductImageCandidateRead,
    ProductImageCandidateSearchRequest,
    ProductImageCandidateSearchResponse,
)
from app.services.google_images_provider import GoogleImagesNotConfiguredError
from app.services.product_image_candidate_service import ProductImageCandidateService, _public_url
from app.services.stock_image_providers import UpstreamRequestError

router = APIRouter(prefix="/admin/product-image-candidates", tags=["admin-product-image-candidates"])


def get_service(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> ProductImageCandidateService:
    return ProductImageCandidateService(db)


def _serialize(candidate: ProductImageCandidate) -> ProductImageCandidateRead:
    return ProductImageCandidateRead(
        id=candidate.id,
        product_id=candidate.product_id,
        product_name=candidate.product.name if candidate.product else None,
        source=candidate.source,
        source_page_url=candidate.source_page_url,
        image_url=candidate.image_url,
        public_url=_public_url(candidate.local_path) if candidate.local_path else None,
        license=candidate.license,
        license_url=candidate.license_url,
        attribution=candidate.attribution,
        creator=candidate.creator,
        status=candidate.status,
        width=candidate.width,
        height=candidate.height,
        file_format=candidate.file_format,
        semantic_decision=candidate.semantic_decision,
        created_at=candidate.created_at,
    )


@router.post("/search", response_model=ProductImageCandidateSearchResponse)
def search_and_stage(
    payload: ProductImageCandidateSearchRequest,
    service: ProductImageCandidateService = Depends(get_service),
):
    try:
        return service.search_and_stage(payload.product_id, payload.max_images)
    except GoogleImagesNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UpstreamRequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google image search failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("", response_model=ProductImageCandidateListResponse)
def list_candidates(
    product_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ProductImageCandidateService = Depends(get_service),
):
    total, items = service.list_candidates(product_id, status_filter, page, page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize(candidate) for candidate in items],
    }


@router.post("/{candidate_id}/approve", response_model=ProductImageCandidateRead)
def approve_candidate(candidate_id: int, service: ProductImageCandidateService = Depends(get_service)):
    try:
        return _serialize(service.approve_candidate(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{candidate_id}/reject", response_model=ProductImageCandidateRead)
def reject_candidate(candidate_id: int, service: ProductImageCandidateService = Depends(get_service)):
    try:
        return _serialize(service.reject_candidate(candidate_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
