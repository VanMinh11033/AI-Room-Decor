"""Test Alembic Migration 0008 upgrade and downgrade."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import settings


def test_alembic_migration_0008_upgrade_and_downgrade(db_session):
    alembic_cfg = Config("backend/alembic.ini" if hasattr(settings, "alembic_ini") else "alembic.ini")
    alembic_cfg.set_main_option("script_location", "backend/alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.test_database_url)

    # Inspect table columns before/after
    engine = db_session.get_bind()
    inspector = inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("orders")]

    assert "recipient_name" in columns
    assert "recipient_phone" in columns
    assert "province" in columns
    assert "ward" in columns
    assert "street_address" in columns
    assert "subtotal_amount" in columns
    assert "shipping_fee" in columns
    assert "shipping_fee_status" in columns
    assert "payment_method" in columns
    assert "payment_status" in columns
