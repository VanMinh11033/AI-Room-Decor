from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.entities import RoomAnalysis, RoomPreference, RoomProject, User
from app.recommendation.engine import RecommendationEngine


class RecommendationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.engine = RecommendationEngine(db)

    def recommend_for_project(self, current_user: User, project_id: int, limit: int):
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
        if preference is None:
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

        return preference, analysis, self.engine.recommend(preference, analysis, limit)
