from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design_generation import DesignGenerationRead
from app.schemas.room_preference import RoomPreferenceRead
from app.schemas.room_project import RoomAnalysisRead, RoomProjectRead
from app.schemas.user import UserRead


class DashboardStats(BaseModel):
    total_users: int
    total_products: int
    active_products: int = 0
    total_room_projects: int = 0
    total_design_generations: int = 0
    total_orders: int
    pending_orders: int = 0
    completed_orders: int = 0
    total_ai_calls: int = 0
    completed_order_revenue: Decimal = Decimal("0")
    system_status: str


class AdminRecentOrder(BaseModel):
    id: int
    customer: UserRead | None = None
    total_amount: Decimal
    status: str
    created_at: datetime


class AdminRecentRoomProject(BaseModel):
    id: int
    title: str
    customer: UserRead | None = None
    status: str
    room_type: str | None = None
    analysis_status: str | None = None
    design_generation_count: int
    created_at: datetime


class AdminRecentAIUsage(BaseModel):
    id: int
    user_id: int | None = None
    room_project_id: int | None = None
    provider: str
    model: str
    task_type: str
    status: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    error_code: str | None = None
    created_at: datetime


class AdminDashboardResponse(BaseModel):
    stats: DashboardStats
    recent_orders: list[AdminRecentOrder] = Field(default_factory=list)
    recent_room_projects: list[AdminRecentRoomProject] = Field(default_factory=list)
    recent_ai_usage: list[AdminRecentAIUsage] = Field(default_factory=list)


class AdminUserActiveUpdate(BaseModel):
    is_active: bool


class AdminRoomProjectListItem(BaseModel):
    project: RoomProjectRead
    customer: UserRead | None = None
    analysis_status: str | None = None
    design_generation_count: int = 0


class AdminRoomProjectListResponse(BaseModel):
    total: int
    items: list[AdminRoomProjectListItem]


class AdminRoomProjectDetail(BaseModel):
    project: RoomProjectRead
    customer: UserRead | None = None
    latest_analysis: RoomAnalysisRead | None = None
    preference: RoomPreferenceRead | None = None
    design_generations: list[DesignGenerationRead] = Field(default_factory=list)


class AdminAIUsageSummary(BaseModel):
    total_calls: int
    success_calls: int
    failed_calls: int
    gemini_calls: int
    cloudflare_calls: int
    local_fallback_calls: int
    composite_fallback_calls: int = 0
    total_tokens: int
    total_cost: Decimal
    cloud_ai_enabled: bool = True
    today_gemini_calls: int = 0
    today_cloudflare_calls: int = 0
    gemini_daily_system_limit: int = 50
    cloudflare_daily_system_limit: int = 10
    gemini_system_quota_remaining: int = 50
    cloudflare_system_quota_remaining: int = 10
    cost_disclaimer: str = "Chi phí ước tính dựa trên cấu hình, chưa có dữ liệu billing thực tế từ Cloudflare/Gemini"


class AdminAIUsageListResponse(BaseModel):
    total: int
    summary: AdminAIUsageSummary
    items: list[AdminRecentAIUsage]
