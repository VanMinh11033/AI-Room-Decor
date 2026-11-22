from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

def build_connect_args(url: str, ssl_verify: bool = False, ssl_ca: str | None = None) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    args = {}
    is_tidb = "tidbcloud.com" in url
    has_ssl_params = "ssl_verify" in url.lower() or "ssl_ca" in url.lower()
    if is_tidb or ssl_verify or has_ssl_params or ssl_ca:
        args["ssl_verify_cert"] = True
        args["ssl_verify_identity"] = True
        if ssl_ca:
            args["ssl_ca"] = ssl_ca
        else:
            try:
                import certifi
                args["ssl_ca"] = certifi.where()
            except ImportError:
                pass
    return args


connect_args = build_connect_args(
    settings.database_url,
    ssl_verify=settings.database_ssl_verify,
    ssl_ca=settings.database_ssl_ca,
)

engine_kwargs = {
    "pool_pre_ping": True,
    "connect_args": connect_args,
}
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

