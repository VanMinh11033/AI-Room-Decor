from typing import Type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.entities import Color, Material, RoomType, Style, User
from app.schemas.catalog import (
    CatalogCreate,
    CatalogListResponse,
    CatalogRead,
    CatalogUpdate,
    ColorCreate,
    ColorListResponse,
    ColorRead,
    ColorUpdate,
)
from app.schemas.common import MessageResponse

router = APIRouter(tags=["catalog attributes"])


def list_entities(db: Session, model, active_only: bool, page: int, page_size: int, search: str | None = None):
    query = db.query(model)
    if active_only:
        query = query.filter(model.is_active.is_(True))
    if search:
        keyword = f"%{search}%"
        query = query.filter((model.name.ilike(keyword)) | (model.slug.ilike(keyword)))
    total = query.count()
    items = query.order_by(model.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def get_entity_or_404(db: Session, model, entity_id: int):
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity


def create_entity(db: Session, model, payload):
    exists = db.query(model).filter((model.name == payload.name) | (model.slug == payload.slug)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name or slug already exists")
    entity = model(**payload.model_dump())
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def update_entity(db: Session, model, entity_id: int, payload):
    entity = get_entity_or_404(db, model, entity_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data or "slug" in data:
        name = data.get("name", entity.name)
        slug = data.get("slug", entity.slug)
        exists = db.query(model).filter((model.id != entity_id), ((model.name == name) | (model.slug == slug))).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name or slug already exists")
    for key, value in data.items():
        setattr(entity, key, value)
    db.commit()
    db.refresh(entity)
    return entity


def deactivate_entity(db: Session, model, entity_id: int):
    entity = get_entity_or_404(db, model, entity_id)
    entity.is_active = False
    db.commit()
    return {"message": "Entity deactivated"}


def register_catalog_routes(public_path: str, admin_path: str, model: Type):
    @router.get(public_path, response_model=CatalogListResponse)
    def public_list(
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        search: str | None = None,
    ):
        return list_entities(db, model, True, page, page_size, search)

    @router.get(admin_path, response_model=CatalogListResponse)
    def admin_list(
        db: Session = Depends(get_db),
        _: User = Depends(require_admin),
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=100),
        search: str | None = None,
    ):
        return list_entities(db, model, False, page, page_size, search)

    @router.post(admin_path, response_model=CatalogRead, status_code=status.HTTP_201_CREATED)
    def admin_create(payload: CatalogCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
        return create_entity(db, model, payload)

    @router.put(f"{admin_path}/{{entity_id}}", response_model=CatalogRead)
    def admin_update(entity_id: int, payload: CatalogUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
        return update_entity(db, model, entity_id, payload)

    @router.delete(f"{admin_path}/{{entity_id}}", response_model=MessageResponse)
    def admin_delete(entity_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
        return deactivate_entity(db, model, entity_id)


register_catalog_routes("/materials", "/admin/materials", Material)
register_catalog_routes("/styles", "/admin/styles", Style)
register_catalog_routes("/room-types", "/admin/room-types", RoomType)


@router.get("/colors", response_model=ColorListResponse)
def public_colors(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = None,
):
    return list_entities(db, Color, True, page, page_size, search)


@router.get("/admin/colors", response_model=ColorListResponse)
def admin_colors(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: str | None = None,
):
    return list_entities(db, Color, False, page, page_size, search)


@router.post("/admin/colors", response_model=ColorRead, status_code=status.HTTP_201_CREATED)
def create_color(payload: ColorCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return create_entity(db, Color, payload)


@router.put("/admin/colors/{entity_id}", response_model=ColorRead)
def update_color(entity_id: int, payload: ColorUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return update_entity(db, Color, entity_id, payload)


@router.delete("/admin/colors/{entity_id}", response_model=MessageResponse)
def delete_color(entity_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return deactivate_entity(db, Color, entity_id)
