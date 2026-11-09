from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    AIUsageLog,
    Order,
    OrderStatus,
    Product,
    ProductStatus,
    RoomAnalysis,
    RoomDesignGeneration,
    RoomPreference,
    RoomProject,
    User,
)
from app.schemas.admin import (
    AdminAIUsageListResponse,
    AdminAIUsageSummary,
    AdminDashboardResponse,
    AdminRecentAIUsage,
    AdminRecentOrder,
    AdminRecentRoomProject,
    AdminRoomProjectDetail,
    AdminRoomProjectListItem,
    AdminRoomProjectListResponse,
    AdminUserActiveUpdate,
    DashboardStats,
)
from app.schemas.design_generation import DesignGenerationRead
from app.schemas.room_preference import RoomPreferenceRead
from app.schemas.room_project import RoomAnalysisRead, RoomProjectRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard-stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return _build_dashboard_stats(db)


@router.get("/dashboard", response_model=AdminDashboardResponse)
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    recent_orders = (
        db.query(Order)
        .options(joinedload(Order.user))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(5)
        .all()
    )
    recent_projects = (
        db.query(RoomProject)
        .options(joinedload(RoomProject.user), selectinload(RoomProject.analyses), selectinload(RoomProject.design_generations))
        .order_by(RoomProject.created_at.desc(), RoomProject.id.desc())
        .limit(5)
        .all()
    )
    recent_ai_usage = (
        db.query(AIUsageLog)
        .order_by(AIUsageLog.created_at.desc(), AIUsageLog.id.desc())
        .limit(8)
        .all()
    )
    return AdminDashboardResponse(
        stats=_build_dashboard_stats(db),
        recent_orders=[
            AdminRecentOrder(
                id=order.id,
                customer=UserRead.model_validate(order.user) if order.user else None,
                total_amount=Decimal(str(order.total_amount)),
                status=order.status.value if hasattr(order.status, "value") else str(order.status),
                created_at=order.created_at,
            )
            for order in recent_orders
        ],
        recent_room_projects=[_serialize_recent_room_project(project) for project in recent_projects],
        recent_ai_usage=[_serialize_ai_usage(log) for log in recent_ai_usage],
    )


@router.get("/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).options(joinedload(User.role)).order_by(User.created_at.desc()).limit(100).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}/active", response_model=UserRead)
def update_user_active(
    user_id: int,
    payload: AdminUserActiveUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    if user_id == current_admin.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")
    user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/room-projects", response_model=AdminRoomProjectListResponse)
def list_room_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = (
        db.query(RoomProject)
        .options(joinedload(RoomProject.user), selectinload(RoomProject.analyses), selectinload(RoomProject.design_generations))
        .order_by(RoomProject.created_at.desc(), RoomProject.id.desc())
    )
    total = query.count()
    projects = query.offset((page - 1) * page_size).limit(page_size).all()
    return AdminRoomProjectListResponse(total=total, items=[_serialize_project_list_item(project) for project in projects])


@router.get("/room-projects/{project_id}", response_model=AdminRoomProjectDetail)
def get_room_project(project_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    project = (
        db.query(RoomProject)
        .options(
            joinedload(RoomProject.user),
            selectinload(RoomProject.analyses),
            joinedload(RoomProject.preference).selectinload(RoomPreference.styles),
            joinedload(RoomProject.preference).selectinload(RoomPreference.colors),
            joinedload(RoomProject.preference).selectinload(RoomPreference.materials),
            joinedload(RoomProject.preference).selectinload(RoomPreference.categories),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).joinedload(Product.category),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).selectinload(Product.images),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).selectinload(Product.materials),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).selectinload(Product.styles),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).selectinload(Product.room_types),
            selectinload(RoomProject.design_generations).selectinload(RoomDesignGeneration.products).selectinload(Product.colors),
        )
        .filter(RoomProject.id == project_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room project not found")
    latest_analysis = sorted(project.analyses, key=lambda item: (item.created_at, item.id), reverse=True)[0] if project.analyses else None
    generations = sorted(project.design_generations, key=lambda item: (item.created_at, item.id), reverse=True)
    return AdminRoomProjectDetail(
        project=RoomProjectRead.model_validate(project),
        customer=UserRead.model_validate(project.user) if project.user else None,
        latest_analysis=RoomAnalysisRead.model_validate(latest_analysis) if latest_analysis else None,
        preference=RoomPreferenceRead.model_validate(project.preference) if project.preference else None,
        design_generations=[DesignGenerationRead.model_validate(generation) for generation in generations],
    )


@router.get("/ai-usage", response_model=AdminAIUsageListResponse)
def list_ai_usage(
    provider: str | None = None,
    task_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AIUsageLog)
    if provider:
        query = query.filter(AIUsageLog.provider == provider)
    if task_type:
        query = query.filter(AIUsageLog.task_type == task_type)
    if status_filter:
        query = query.filter(AIUsageLog.status == status_filter)
    total = query.count()
    items = query.order_by(AIUsageLog.created_at.desc(), AIUsageLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    summary_base = db.query(AIUsageLog)
    now_utc = datetime.now(UTC)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=UTC)

    today_gemini_calls = summary_base.filter(
        AIUsageLog.provider == "gemini",
        AIUsageLog.created_at >= today_start,
        AIUsageLog.status.in_(["SUCCESS", "RESERVED", "TIMEOUT_SUSPECTED"]),
    ).count()

    today_cloudflare_calls = summary_base.filter(
        AIUsageLog.provider == "cloudflare",
        AIUsageLog.created_at >= today_start,
        AIUsageLog.status.in_(["SUCCESS", "RESERVED", "TIMEOUT_SUSPECTED"]),
    ).count()

    composite_calls = summary_base.filter(AIUsageLog.provider == "composite").count()
    gemini_limit = settings.gemini_daily_system_limit
    cf_limit = settings.cloudflare_daily_system_limit

    summary = AdminAIUsageSummary(
        total_calls=summary_base.count(),
        success_calls=summary_base.filter(AIUsageLog.status == "SUCCESS").count(),
        failed_calls=summary_base.filter(AIUsageLog.status == "FAILED").count(),
        gemini_calls=summary_base.filter(AIUsageLog.provider == "gemini").count(),
        cloudflare_calls=summary_base.filter(AIUsageLog.provider == "cloudflare").count(),
        local_fallback_calls=summary_base.filter(AIUsageLog.provider == "local_fallback").count(),
        composite_fallback_calls=composite_calls,
        total_tokens=int(summary_base.with_entities(func.coalesce(func.sum(AIUsageLog.total_tokens), 0)).scalar() or 0),
        total_cost=Decimal(str(summary_base.with_entities(func.coalesce(func.sum(AIUsageLog.estimated_cost), 0)).scalar() or 0)),
        cloud_ai_enabled=settings.enable_cloud_ai,
        today_gemini_calls=today_gemini_calls,
        today_cloudflare_calls=today_cloudflare_calls,
        gemini_daily_system_limit=gemini_limit,
        cloudflare_daily_system_limit=cf_limit,
        gemini_system_quota_remaining=max(0, gemini_limit - today_gemini_calls),
        cloudflare_system_quota_remaining=max(0, cf_limit - today_cloudflare_calls),
        cost_disclaimer="Chi phí ước tính dựa trên cấu hình, chưa có dữ liệu billing thực tế từ Cloudflare/Gemini",
    )
    return AdminAIUsageListResponse(total=total, summary=summary, items=[_serialize_ai_usage(item) for item in items])


def _build_dashboard_stats(db: Session) -> DashboardStats:
    completed_revenue = (
        db.query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.status == OrderStatus.COMPLETED)
        .scalar()
        or Decimal("0")
    )
    return DashboardStats(
        total_users=db.query(User).count(),
        total_products=db.query(Product).count(),
        active_products=db.query(Product).filter(Product.is_active.is_(True), Product.status == ProductStatus.ACTIVE).count(),
        total_room_projects=db.query(RoomProject).count(),
        total_design_generations=db.query(RoomDesignGeneration).count(),
        total_orders=db.query(Order).count(),
        pending_orders=db.query(Order).filter(Order.status == OrderStatus.PENDING).count(),
        completed_orders=db.query(Order).filter(Order.status == OrderStatus.COMPLETED).count(),
        total_ai_calls=db.query(AIUsageLog).count(),
        completed_order_revenue=Decimal(str(completed_revenue)),
        system_status="OK",
    )


def _serialize_project_list_item(project: RoomProject) -> AdminRoomProjectListItem:
    latest_analysis = sorted(project.analyses, key=lambda item: (item.created_at, item.id), reverse=True)[0] if project.analyses else None
    return AdminRoomProjectListItem(
        project=RoomProjectRead.model_validate(project),
        customer=UserRead.model_validate(project.user) if project.user else None,
        analysis_status=latest_analysis.status if latest_analysis else None,
        design_generation_count=len(project.design_generations),
    )


def _serialize_recent_room_project(project: RoomProject) -> AdminRecentRoomProject:
    latest_analysis = sorted(project.analyses, key=lambda item: (item.created_at, item.id), reverse=True)[0] if project.analyses else None
    return AdminRecentRoomProject(
        id=project.id,
        title=project.title,
        customer=UserRead.model_validate(project.user) if project.user else None,
        status=project.status,
        room_type=project.room_type,
        analysis_status=latest_analysis.status if latest_analysis else None,
        design_generation_count=len(project.design_generations),
        created_at=project.created_at,
    )


def _serialize_ai_usage(log: AIUsageLog) -> AdminRecentAIUsage:
    return AdminRecentAIUsage(
        id=log.id,
        user_id=log.user_id,
        room_project_id=log.room_project_id,
        provider=log.provider,
        model=log.model,
        task_type=log.task_type,
        status=log.status,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
        total_tokens=log.total_tokens,
        estimated_cost=Decimal(str(log.estimated_cost)),
        error_code=log.error_code,
        created_at=log.created_at,
    )
