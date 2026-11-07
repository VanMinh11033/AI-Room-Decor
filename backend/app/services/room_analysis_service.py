from datetime import UTC, datetime
from time import perf_counter

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.vision.base import VisionProvider, VisionProviderError
from app.ai.vision.fallback_provider import LocalFallbackProvider
from app.models.entities import AIUsageLog, RoomAnalysis, RoomProject, User
from app.schemas.room_project import RoomAnalysisResult, RoomProjectCreate
from app.services.storage_service import RoomImageStorageService


class RoomAnalysisService:
    def __init__(self, db: Session, vision_provider: VisionProvider | None = None) -> None:
        self.db = db
        self.vision_provider = vision_provider

    def create_project(self, current_user: User, payload: RoomProjectCreate) -> RoomProject:
        project = RoomProject(
            user_id=current_user.id,
            title=payload.title,
            room_type=payload.room_type,
            status="DRAFT",
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, current_user: User, page: int, page_size: int) -> tuple[int, list[RoomProject]]:
        query = (
            self.db.query(RoomProject)
            .filter(RoomProject.user_id == current_user.id, RoomProject.status != "ARCHIVED")
            .order_by(RoomProject.created_at.desc())
        )
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return total, items

    def get_owned_project(self, current_user: User, project_id: int, include_archived: bool = False) -> RoomProject:
        query = self.db.query(RoomProject).filter(RoomProject.id == project_id, RoomProject.user_id == current_user.id)
        if not include_archived:
            query = query.filter(RoomProject.status != "ARCHIVED")
        project = query.first()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room project not found")
        return project

    def archive_project(self, current_user: User, project_id: int) -> None:
        project = self.get_owned_project(current_user, project_id)
        project.status = "ARCHIVED"
        self.db.commit()

    def upload_room_image(self, current_user: User, project_id: int, file: UploadFile) -> RoomProject:
        project = self.get_owned_project(current_user, project_id)
        stored = RoomImageStorageService().save(file, current_user.id, project.id)
        project.room_image_url = stored.image_url
        project.room_image_path = stored.storage_path
        project.image_original_filename = stored.original_filename
        project.image_content_type = stored.content_type
        project.image_size_bytes = stored.size_bytes
        project.image_checksum = stored.checksum
        project.status = "UPLOADED"
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_current_analysis(self, current_user: User, project_id: int) -> RoomAnalysis:
        project = self.get_owned_project(current_user, project_id)
        if not project.image_checksum:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room analysis not found")
        analysis = (
            self.db.query(RoomAnalysis)
            .filter(
                RoomAnalysis.room_project_id == project.id,
                RoomAnalysis.user_id == current_user.id,
                RoomAnalysis.image_checksum == project.image_checksum,
            )
            .order_by(RoomAnalysis.created_at.desc())
            .first()
        )
        if analysis is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room analysis not found")
        return analysis

    def analyze_room(self, current_user: User, project_id: int, force: bool = False) -> RoomAnalysis:
        project = self.get_owned_project(current_user, project_id)
        if not project.room_image_path or not project.image_checksum or not project.image_content_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a room image before analysis")

        cached = (
            self.db.query(RoomAnalysis)
            .filter(
                RoomAnalysis.room_project_id == project.id,
                RoomAnalysis.user_id == current_user.id,
                RoomAnalysis.image_checksum == project.image_checksum,
                RoomAnalysis.status == "COMPLETED",
            )
            .order_by(RoomAnalysis.created_at.desc())
            .first()
        )
        if cached is not None and not force:
            return cached

        provider = self.vision_provider
        if provider is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Vision provider dependency is missing")

        analysis = RoomAnalysis(
            room_project_id=project.id,
            user_id=current_user.id,
            image_checksum=project.image_checksum,
            status="ANALYZING",
            provider=provider.provider_name,
            model=provider.model_name,
        )
        project.status = "ANALYZING"
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)

        started_at = perf_counter()
        try:
            image_path = RoomImageStorageService().resolve(project.room_image_path)
            provider_result = provider.analyze_room(image_path, project.image_content_type)
            result = RoomAnalysisResult.model_validate(provider_result.result)
            latency_ms = int((perf_counter() - started_at) * 1000)
            self._apply_success(analysis, project, result, provider_result.raw_response)
            usage = provider_result.usage
            self._log_usage(
                current_user=current_user,
                project=project,
                provider=provider.provider_name,
                model=provider.model_name,
                status="SUCCESS",
                latency_ms=latency_ms,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                estimated_cost=usage.estimated_cost if usage else 0,
            )
            self.db.commit()
            self.db.refresh(analysis)
            return analysis
        except VisionProviderError as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            self._log_usage(
                current_user=current_user,
                project=project,
                provider=provider.provider_name,
                model=provider.model_name,
                status="FAILED",
                latency_ms=latency_ms,
                error_code=exc.code,
                error_message=exc.message,
            )
            if exc.code in ("GEMINI_PROVIDER_UNAVAILABLE", "GEMINI_PROVIDER_QUOTA_ERROR"):
                fallback = self._try_local_fallback(current_user, project, analysis, latency_ms)
                if fallback is not None:
                    self.db.commit()
                    self.db.refresh(analysis)
                    return fallback
            self._apply_failure(analysis, project, exc.code, exc.message)
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.code) from exc
        except Exception as exc:
            latency_ms = int((perf_counter() - started_at) * 1000)
            self._apply_failure(analysis, project, "AI_ANALYSIS_FAILED", str(exc))
            self._log_usage(
                current_user=current_user,
                project=project,
                provider=provider.provider_name,
                model=provider.model_name,
                status="FAILED",
                latency_ms=latency_ms,
                error_code="AI_ANALYSIS_FAILED",
                error_message=str(exc),
            )
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI_ANALYSIS_FAILED") from exc

    def _try_local_fallback(
        self,
        current_user: User,
        project: RoomProject,
        analysis: RoomAnalysis,
        latency_ms: int,
    ) -> RoomAnalysis | None:
        try:
            image_path = RoomImageStorageService().resolve(project.room_image_path)
            fallback_provider = LocalFallbackProvider(room_type=project.room_type)
            provider_result = fallback_provider.analyze_room(image_path, project.image_content_type)
            result = RoomAnalysisResult.model_validate(provider_result.result)
            analysis.provider = fallback_provider.provider_name
            analysis.model = fallback_provider.model_name
            self._apply_success(analysis, project, result, provider_result.raw_response)
            self._log_usage(
                current_user=current_user,
                project=project,
                provider=fallback_provider.provider_name,
                model=fallback_provider.model_name,
                status="SUCCESS",
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                estimated_cost=0,
            )
            return analysis
        except Exception:
            return None

    def _apply_success(
        self,
        analysis: RoomAnalysis,
        project: RoomProject,
        result: RoomAnalysisResult,
        raw_response: dict | list | None,
    ) -> None:
        analysis.status = "COMPLETED"
        analysis.room_type = result.room_type
        analysis.dominant_colors = [item.model_dump() for item in result.dominant_colors]
        analysis.existing_objects = [item.model_dump() for item in result.existing_objects]
        analysis.empty_areas = [item.model_dump() for item in result.empty_areas]
        analysis.lighting = result.lighting.model_dump() if result.lighting else None
        analysis.design_characteristics = result.design_characteristics
        analysis.layout_summary = result.layout_summary
        analysis.confidence = result.confidence
        analysis.raw_response = raw_response
        analysis.completed_at = datetime.now(UTC)
        analysis.error_code = None
        analysis.error_message = None
        project.room_type = project.room_type or result.room_type
        project.status = "COMPLETED"

    def _apply_failure(self, analysis: RoomAnalysis, project: RoomProject, error_code: str, error_message: str) -> None:
        analysis.status = "FAILED"
        analysis.error_code = error_code
        analysis.error_message = error_message
        project.status = "FAILED"

    def _log_usage(
        self,
        current_user: User,
        project: RoomProject,
        provider: str,
        model: str,
        status: str,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: float = 0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.db.add(
            AIUsageLog(
                user_id=current_user.id,
                room_project_id=project.id,
                provider=provider,
                model=model,
                task_type="ROOM_IMAGE_ANALYSIS",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=latency_ms,
                error_code=error_code,
                status=status,
                error_message=error_message,
            )
        )
