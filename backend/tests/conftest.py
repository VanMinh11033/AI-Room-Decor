import os
import tempfile
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")
os.environ.setdefault("TEST_DATABASE_URL", "mysql+pymysql://root:@127.0.0.1:3306/ai_room_decor_test?charset=utf8mb4")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ.setdefault("APP_ENV", "test")
os.environ["PRODUCT_STORAGE_DIR"] = "test_storage/products"
os.environ["ROOM_STORAGE_DIR"] = str(Path(tempfile.gettempdir()) / "ai_room_decor_test_rooms")
os.environ["GENERATED_DESIGN_STORAGE_DIR"] = str(Path(tempfile.gettempdir()) / "ai_room_decor_test_generated_designs")
os.environ["VISION_PROVIDER"] = ""
os.environ["VISION_MODEL"] = ""
os.environ["VISION_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["IMAGE_PROVIDER"] = ""
os.environ["IMAGE_MODEL"] = ""
os.environ["IMAGE_API_KEY"] = ""
os.environ["CLOUDFLARE_ACCOUNT_ID"] = ""
os.environ["CLOUDFLARE_API_TOKEN"] = ""
os.environ["QWENCLOUD_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.initial_data import seed_initial_data
from app.main import app
from app.models import *  # noqa: F401,F403

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]


def ensure_test_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    database = url.database
    if not database:
        raise RuntimeError("TEST_DATABASE_URL must include a database name")
    engine = create_engine(url.set(database=None), pool_pre_ping=True, poolclass=NullPool)
    with engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(
            text(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        )
    engine.dispose()


ensure_test_database()
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    with engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(text("SET FOREIGN_KEY_CHECKS=0"))
    Base.metadata.drop_all(bind=engine)
    with engine.connect() as connection:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(text("SET FOREIGN_KEY_CHECKS=1"))
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_initial_data(db)
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.rollback()
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
