from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Category, Color, Material, RoomPreference, RoomProject, Style, User
from app.schemas.room_preference import RoomPreferencePayload


class RoomPreferenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_owned_project(self, current_user: User, project_id: int) -> RoomProject:
        project = (
            self.db.query(RoomProject)
            .filter(RoomProject.id == project_id, RoomProject.user_id == current_user.id, RoomProject.status != "ARCHIVED")
            .first()
        )
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room project not found")
        return project

    def get_preference(self, current_user: User, project_id: int) -> RoomPreference:
        self.get_owned_project(current_user, project_id)
        preference = self._preference_query().filter(
            RoomPreference.room_project_id == project_id,
            RoomPreference.user_id == current_user.id,
        ).first()
        if preference is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room preferences not found")
        return preference

    def upsert_preference(self, current_user: User, project_id: int, payload: RoomPreferencePayload) -> RoomPreference:
        project = self.get_owned_project(current_user, project_id)
        preference = self._preference_query().filter(RoomPreference.room_project_id == project.id).first()
        if preference is None:
            preference = RoomPreference(room_project_id=project.id, user_id=current_user.id)
            self.db.add(preference)
            self.db.flush()

        preference.budget_min = payload.budget_min
        preference.budget_max = payload.budget_max
        preference.currency = payload.currency.upper()
        preference.purpose = payload.purpose
        preference.notes = payload.notes
        preference.styles = self._load_many(Style, self._dedupe(payload.style_ids))
        preference.colors = self._load_many(Color, self._dedupe(payload.color_ids))
        preference.materials = self._load_many(Material, self._dedupe(payload.material_ids))
        preference.categories = self._load_many(Category, self._dedupe(payload.category_ids))

        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not save room preferences") from exc
        return self._preference_query().filter(RoomPreference.id == preference.id).one()

    def _preference_query(self):
        return self.db.query(RoomPreference).options(
            joinedload(RoomPreference.styles),
            joinedload(RoomPreference.colors),
            joinedload(RoomPreference.materials),
            joinedload(RoomPreference.categories),
        )

    @staticmethod
    def _dedupe(ids: list[int]) -> list[int]:
        return list(dict.fromkeys(ids))

    def _load_many(self, model, ids: list[int]):
        if not ids:
            return []
        records = self.db.query(model).filter(model.id.in_(ids)).all()
        if len(records) != len(ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {model.__tablename__} ids")
        return records
