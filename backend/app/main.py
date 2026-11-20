from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.routes import admin, auth, cart, catalog_attributes, categories, orders, product_image_candidates, products, room_projects, users
from app.core.config import settings
from app.core.database import SessionLocal
from app.initial_data import seed_initial_data

STORAGE_DIR = Path(settings.storage_root_dir) if settings.storage_root_dir else (Path(__file__).resolve().parents[2] / "storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

is_prod = settings.app_env.lower() == "production"
app = FastAPI(
    title="AI Room Decor API",
    version="0.1.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
)

trusted_proxies = [h.strip() for h in settings.trusted_proxies.split(",") if h.strip()]
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted_proxies or ["127.0.0.1", "localhost"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(catalog_attributes.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(product_image_candidates.router, prefix="/api")
app.include_router(room_projects.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(orders.admin_router, prefix="/api")
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")


@app.on_event("startup")
def on_startup() -> None:
    if settings.is_testing:
        return
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "OK"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    import logging
    logging.getLogger(__name__).error(
        "Unhandled server exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    from fastapi.responses import JSONResponse
    origin = request.headers.get("origin")
    headers = {}
    if origin and (origin in settings.cors_origins or "*" in settings.cors_origins):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "Đã xảy ra lỗi máy chủ nội bộ. Vui lòng thử lại sau."},
        headers=headers,
    )

