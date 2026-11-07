from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.entities import Category, Color, Material, Product, ProductImage, ProductStatus, RoomType, Style, User
from app.schemas.common import MessageResponse
from app.schemas.product import ProductCreate, ProductListResponse, ProductRead, ProductUpdate
from app.services.storage_service import ProductImageStorageService

router = APIRouter(tags=["products"])


def product_query(db: Session):
    return db.query(Product).options(
        joinedload(Product.category),
        joinedload(Product.images),
        joinedload(Product.materials),
        joinedload(Product.styles),
        joinedload(Product.room_types),
        joinedload(Product.colors),
    )


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = product_query(db).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def apply_filters(query, search, category_id, material, style, room_type, color, min_price, max_price, is_active):
    if search:
        keyword = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(keyword),
                Product.description.ilike(keyword),
                Product.tags.ilike(keyword),
                Product.searchable_text.ilike(keyword),
            )
        )
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if is_active is not None:
        query = query.filter(Product.is_active.is_(is_active))
    if material:
        query = query.filter(Product.materials.any(Material.slug == material))
    if style:
        query = query.filter(Product.styles.any(Style.slug == style))
    if room_type:
        query = query.filter(Product.room_types.any(RoomType.slug == room_type))
    if color:
        query = query.filter(Product.colors.any(Color.slug == color))
    return query.distinct()


def apply_sort(query, sort: str | None):
    if sort == "price_asc":
        return query.order_by(Product.price.asc())
    if sort == "price_desc":
        return query.order_by(Product.price.desc())
    if sort == "name_asc":
        return query.order_by(Product.name.asc())
    return query.order_by(Product.created_at.desc())


def build_searchable_text(product: Product) -> str:
    pieces = [
        product.name,
        product.description or "",
        product.tags or "",
        product.category.name if product.category else "",
        " ".join(item.name for item in product.materials),
        " ".join(item.name for item in product.styles),
        " ".join(item.name for item in product.room_types),
        " ".join(item.name for item in product.colors),
    ]
    return " ".join(piece for piece in pieces if piece).lower()


def normalize_product_status(value: str | ProductStatus) -> ProductStatus:
    try:
        return value if isinstance(value, ProductStatus) else ProductStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid product status") from exc


def load_many(db: Session, model, ids: list[int]):
    if not ids:
        return []
    records = db.query(model).filter(model.id.in_(ids)).all()
    if len(records) != len(set(ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {model.__tablename__} ids")
    return records


def sync_product_relations(db: Session, product: Product, payload: ProductCreate | ProductUpdate) -> None:
    if getattr(payload, "material_ids", None) is not None:
        product.materials = load_many(db, Material, payload.material_ids or [])
    if getattr(payload, "style_ids", None) is not None:
        product.styles = load_many(db, Style, payload.style_ids or [])
    if getattr(payload, "room_type_ids", None) is not None:
        product.room_types = load_many(db, RoomType, payload.room_type_ids or [])
    if getattr(payload, "color_ids", None) is not None:
        product.colors = load_many(db, Color, payload.color_ids or [])


def sync_images(db: Session, product: Product, images) -> None:
    if images is None:
        return
    product.images.clear()
    db.flush()
    primary_seen = False
    for index, image in enumerate(images):
        data = image.model_dump()
        if data["is_primary"] and not primary_seen:
            primary_seen = True
        elif data["is_primary"] and primary_seen:
            data["is_primary"] = False
        if not primary_seen and index == 0:
            data["is_primary"] = True
            primary_seen = True
        db.add(ProductImage(product_id=product.id, **data))


@router.get("/products", response_model=ProductListResponse)
def list_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: int | None = None,
    material: str | None = None,
    style: str | None = None,
    room_type: str | None = None,
    color: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    sort: str | None = Query(None, pattern="^(newest|price_asc|price_desc|name_asc)$"),
):
    query = apply_filters(product_query(db), search, category_id, material, style, room_type, color, min_price, max_price, True)
    total = query.count()
    items = apply_sort(query, sort).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = get_product_or_404(db, product_id)
    if not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("/admin/products", response_model=ProductListResponse)
def admin_list_products(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    category_id: int | None = None,
    material: str | None = None,
    style: str | None = None,
    room_type: str | None = None,
    color: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    is_active: bool | None = None,
    sort: str | None = Query(None, pattern="^(newest|price_asc|price_desc|name_asc)$"),
):
    query = apply_filters(product_query(db), search, category_id, material, style, room_type, color, min_price, max_price, is_active)
    total = query.count()
    items = apply_sort(query, sort).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/admin/products/{product_id}", response_model=ProductRead)
def admin_get_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return get_product_or_404(db, product_id)


@router.post("/admin/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category does not exist")
    if db.query(Product).filter(Product.slug == payload.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product slug already exists")
    data = payload.model_dump(exclude={"images", "material_ids", "style_ids", "room_type_ids", "color_ids"})
    data["status"] = normalize_product_status(data["status"])
    product = Product(**data)
    db.add(product)
    db.flush()
    sync_product_relations(db, product, payload)
    sync_images(db, product, payload.images)
    product.is_active = product.status == ProductStatus.ACTIVE
    db.flush()
    product.searchable_text = build_searchable_text(product)
    db.commit()
    return get_product_or_404(db, product.id)


@router.put("/admin/products/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = get_product_or_404(db, product_id)
    data = payload.model_dump(exclude_unset=True, exclude={"images", "material_ids", "style_ids", "room_type_ids", "color_ids"})
    if "category_id" in data and db.get(Category, data["category_id"]) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category does not exist")
    if "slug" in data and db.query(Product).filter(Product.slug == data["slug"], Product.id != product_id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product slug already exists")
    for key, value in data.items():
        if key == "status":
            value = normalize_product_status(value)
        setattr(product, key, value)
    sync_product_relations(db, product, payload)
    sync_images(db, product, payload.images)
    if payload.status is not None:
        product.is_active = product.status == ProductStatus.ACTIVE
    db.flush()
    product.searchable_text = build_searchable_text(product)
    db.commit()
    return get_product_or_404(db, product.id)


@router.delete("/admin/products/{product_id}", response_model=MessageResponse)
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = get_product_or_404(db, product_id)
    product.is_active = False
    product.status = ProductStatus.INACTIVE
    db.commit()
    return {"message": "Product deactivated"}


@router.post("/admin/products/{product_id}/images", response_model=ProductRead)
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    alt_text: str | None = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = get_product_or_404(db, product_id)
    image_url = ProductImageStorageService().save(file)
    if is_primary:
        for image in product.images:
            image.is_primary = False
    db.add(
        ProductImage(
            product_id=product.id,
            image_url=image_url,
            alt_text=alt_text or product.name,
            sort_order=len(product.images),
            is_primary=is_primary or not product.images,
        )
    )
    db.commit()
    return get_product_or_404(db, product.id)
