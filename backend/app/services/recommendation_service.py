from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.entities import RoomAnalysis, RoomPreference, RoomProject, User
from app.recommendation.bundle_optimizer import OptimizedBundle
from app.recommendation.engine import RecommendationEngine
from app.recommendation.resolver import EffectivePreference, EffectivePreferenceResolver


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.engine = RecommendationEngine(db)
        self.last_bundle: OptimizedBundle | None = None
        self.last_effective_preference: EffectivePreference | None = None

    def recommend_for_project(self, current_user: User, project_id: int, limit: int = 50):
        project = (
            self.db.query(RoomProject)
            .filter(RoomProject.id == project_id, RoomProject.user_id == current_user.id, RoomProject.status != "ARCHIVED")
            .first()
        )
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room project not found")

        preference = (
            self.db.query(RoomPreference)
            .options(
                joinedload(RoomPreference.styles),
                joinedload(RoomPreference.colors),
                joinedload(RoomPreference.materials),
                joinedload(RoomPreference.categories),
            )
            .filter(RoomPreference.room_project_id == project.id, RoomPreference.user_id == current_user.id)
            .first()
        )

        has_profile_pref = (
            current_user.profile is not None
            and any([
                getattr(current_user.profile, "preferred_style", None),
                getattr(current_user.profile, "preferred_colors", None),
                getattr(current_user.profile, "preferred_materials", None),
            ])
        )

        if preference is None and not has_profile_pref:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ROOM_PREFERENCES_REQUIRED")

        analysis = (
            self.db.query(RoomAnalysis)
            .filter(
                RoomAnalysis.room_project_id == project.id,
                RoomAnalysis.user_id == current_user.id,
                RoomAnalysis.status == "COMPLETED",
            )
            .order_by(RoomAnalysis.created_at.desc())
            .first()
        )
        if analysis is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ROOM_ANALYSIS_REQUIRED")

        if getattr(settings, "room_decor_v1_5_personalization_enabled", True):
            eff_pref = EffectivePreferenceResolver(self.db).resolve(
                current_user=current_user,
                project=project,
                room_preference=preference,
                analysis=analysis,
            )
            diversified, bundle = self.engine.recommend_v1_5(eff_pref, analysis, current_user.id, limit)
            self.last_bundle = bundle
            self.last_effective_preference = eff_pref
            return preference, analysis, diversified
        else:
            return preference, analysis, self.engine.recommend(preference, analysis, limit)
