from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.image.base import ImageProvider
from app.ai.image.factory import get_image_provider
from app.ai.vision.base import VisionProvider
from app.ai.vision.factory import get_vision_provider
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import design_generation_rate_limiter, room_analyze_rate_limiter, room_upload_rate_limiter
from app.models.entities import User
from app.schemas.common import MessageResponse
from app.schemas.design_generation import DesignGenerationCreate, DesignGenerationListResponse, DesignGenerationRead
from app.schemas.recommendation import RecommendationResponse
from app.schemas.room_preference import RoomPreferencePayload, RoomPreferenceRead
from app.schemas.room_project import RoomAnalysisRead, RoomProjectCreate, RoomProjectListResponse, RoomProjectRead
from app.services.design_generation_service import DesignGenerationService
from app.services.recommendation_service import RecommendationService
from app.services.room_analysis_service import RoomAnalysisService
from app.services.room_preference_service import RoomPreferenceService

router = APIRouter(prefix="/room-projects", tags=["room-projects"])


def get_service(
    db: Session = Depends(get_db),
    provider: VisionProvider = Depends(get_vision_provider),
) -> RoomAnalysisService:
    return RoomAnalysisService(db, provider)


def get_preference_service(db: Session = Depends(get_db)) -> RoomPreferenceService:
    return RoomPreferenceService(db)


def get_recommendation_service(db: Session = Depends(get_db)) -> RecommendationService:
    return RecommendationService(db)


def get_design_generation_service(
    db: Session = Depends(get_db),
    provider: ImageProvider = Depends(get_image_provider),
) -> DesignGenerationService:
    return DesignGenerationService(db, provider)


@router.post("", response_model=RoomProjectRead, status_code=status.HTTP_201_CREATED)
def create_room_project(
    payload: RoomProjectCreate,
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    return service.create_project(current_user, payload)


@router.get("", response_model=RoomProjectListResponse)
def list_room_projects(
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, items = service.list_projects(current_user, page, page_size)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/{project_id}", response_model=RoomProjectRead)
def get_room_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    return service.get_owned_project(current_user, project_id)


@router.get("/{project_id}/preferences", response_model=RoomPreferenceRead)
def get_room_project_preferences(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: RoomPreferenceService = Depends(get_preference_service),
):
    return service.get_preference(current_user, project_id)


@router.put("/{project_id}/preferences", response_model=RoomPreferenceRead)
def upsert_room_project_preferences(
    project_id: int,
    payload: RoomPreferencePayload,
    current_user: User = Depends(get_current_user),
    service: RoomPreferenceService = Depends(get_preference_service),
):
    return service.upsert_preference(current_user, project_id, payload)


@router.delete("/{project_id}", response_model=MessageResponse)
def archive_room_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    service.archive_project(current_user, project_id)
    return {"message": "Room project archived"}


@router.post("/{project_id}/image", response_model=RoomProjectRead, dependencies=[Depends(room_upload_rate_limiter)])
def upload_room_project_image(
    project_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    return service.upload_room_image(current_user, project_id, file)


@router.post("/{project_id}/analyze", response_model=RoomAnalysisRead, dependencies=[Depends(room_analyze_rate_limiter)])
def analyze_room_project(
    project_id: int,
    force: bool = Query(False),
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    return service.analyze_room(current_user, project_id, force=force)


@router.get("/{project_id}/analysis", response_model=RoomAnalysisRead)
def get_room_project_analysis(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: RoomAnalysisService = Depends(get_service),
):
    return service.get_current_analysis(current_user, project_id)


@router.get("/{project_id}/recommendations", response_model=RecommendationResponse)
def get_room_project_recommendations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
    limit: int = Query(12, ge=1, le=50),
):
    preference, analysis, recommendations = service.recommend_for_project(current_user, project_id, limit)
    bundle_data = service.last_bundle.to_dict() if getattr(service, "last_bundle", None) else None
    eff_pref_data = service.last_effective_preference.to_dict() if getattr(service, "last_effective_preference", None) else None
    return {
        "room_project_id": project_id,
        "analysis_id": analysis.id,
        "preference": preference,
        "total": len(recommendations),
        "items": [
            {
                "product": item.product,
                "score": item.score,
                "role": getattr(item, "role", None).value if getattr(item, "role", None) else None,
                "boost": getattr(item, "boost", 0.0),
                "penalty": getattr(item, "penalty", 0.0),
                "reasons": item.reasons,
                "breakdown": item.breakdown,
                "provenance": getattr(item, "provenance", {}),
            }
            for item in recommendations
        ],
        "bundle": bundle_data,
        "effective_preference": eff_pref_data,
        "recommendation_version": getattr(settings, "room_decor_recommendation_version", "v1.5"),
    }


@router.post("/{project_id}/design-generations", response_model=DesignGenerationRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(design_generation_rate_limiter)])
def create_room_project_design_generation(
    project_id: int,
    payload: DesignGenerationCreate,
    current_user: User = Depends(get_current_user),
    service: DesignGenerationService = Depends(get_design_generation_service),
):
    return service.create_generation(current_user, project_id, payload)


@router.get("/{project_id}/design-generations", response_model=DesignGenerationListResponse)
def list_room_project_design_generations(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: DesignGenerationService = Depends(get_design_generation_service),
):
    total, items = service.list_generations(current_user, project_id)
    return {"total": total, "items": items}


@router.get("/{project_id}/design-generations/latest", response_model=DesignGenerationRead)
def get_latest_room_project_design_generation(
    project_id: int,
    current_user: User = Depends(get_current_user),
    service: DesignGenerationService = Depends(get_design_generation_service),
):
    return service.get_latest_generation(current_user, project_id)


@router.get("/{project_id}/design-generations/{generation_id}", response_model=DesignGenerationRead)
def get_room_project_design_generation(
    project_id: int,
    generation_id: int,
    current_user: User = Depends(get_current_user),
    service: DesignGenerationService = Depends(get_design_generation_service),
):
    return service.get_generation(current_user, project_id, generation_id)


@router.post(
    "/{project_id}/design-generations/import-gemini",
    response_model=DesignGenerationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(design_generation_rate_limiter)],
)
def import_gemini_manual_design_generation(
    project_id: int,
    file: UploadFile = File(..., description="File ảnh thiết kế PNG hoặc JPG tải từ Gemini"),
    product_ids: str = Form(..., description="Danh sách Product IDs tham chiếu (VD: '1,6' hoặc '[1, 6]')"),
    notes: str | None = Form(None, description="Ghi chú tùy chọn"),
    current_user: User = Depends(get_current_user),
    service: DesignGenerationService = Depends(get_design_generation_service),
):
    import json
    parsed_ids: list[int] = []
    raw = (product_ids or "").strip()
    try:
        if raw.startswith("["):
            parsed_ids = [int(x) for x in json.loads(raw)]
        else:
            parsed_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Định dạng product_ids không hợp lệ. Vui lòng cung cấp danh sách ID phân tách bằng dấu phẩy hoặc JSON array.",
        )

    if not parsed_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần ít nhất một mã sản phẩm (product_id) tham chiếu.",
        )

    return service.import_gemini_manual_design(
        current_user=current_user,
        project_id=project_id,
        file=file,
        product_ids=parsed_ids,
        notes=notes,
    )
