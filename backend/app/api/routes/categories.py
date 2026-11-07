from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.entities import Category, User
from app.schemas.category import CategoryCreate, CategoryListResponse, CategoryRead, CategoryUpdate
from app.schemas.common import MessageResponse

router = APIRouter(tags=["categories"])


def get_category_or_404(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
):
    query = db.query(Category).filter(Category.is_active.is_(True))
    if search:
        keyword = f"%{search}%"
        query = query.filter((Category.name.ilike(keyword)) | (Category.slug.ilike(keyword)))
    query = query.order_by(Category.name.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/admin/categories", response_model=CategoryListResponse)
def admin_list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
):
    query = db.query(Category)
    if search:
        keyword = f"%{search}%"
        query = query.filter((Category.name.ilike(keyword)) | (Category.slug.ilike(keyword)))
    query = query.order_by(Category.name.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/admin/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    exists = db.query(Category).filter((Category.name == payload.name) | (Category.slug == payload.slug)).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name or slug already exists")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/admin/categories/{category_id}", response_model=CategoryRead)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    category = get_category_or_404(db, category_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data or "slug" in data:
        name = data.get("name", category.name)
        slug = data.get("slug", category.slug)
        exists = db.query(Category).filter(Category.id != category_id, ((Category.name == name) | (Category.slug == slug))).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name or slug already exists")
    for key, value in data.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/admin/categories/{category_id}", response_model=MessageResponse)
def delete_category(category_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    category = get_category_or_404(db, category_id)
    category.is_active = False
    db.commit()
    return {"message": "Category deactivated"}
