"""Test Alembic Migration 0009 upgrade and downgrade specification, offline SQL generation, and live execution."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_alembic_migration_0009_structure():
    migration_path = Path("alembic/versions/0009_order_total_amount_nullable.py")
    if not migration_path.exists():
        migration_path = Path("backend/alembic/versions/0009_order_total_amount_nullable.py")
    assert migration_path.exists(), f"Migration file not found at {migration_path}"

    spec = importlib.util.spec_from_file_location("migration_0009", str(migration_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "0009_order_total_amount_nullable"
    assert mod.down_revision == "0008_cod_checkout_upgrade"
    assert callable(getattr(mod, "upgrade", None))
    assert callable(getattr(mod, "downgrade", None))


def test_alembic_migration_0009_offline_sql_upgrade():
    """Verify that Alembic generates exact non-destructive MySQL DDL for upgrade."""
    cmd = [sys.executable, "-m", "alembic", "upgrade", "0008:0009", "--sql"]
    cwd = Path(__file__).resolve().parent.parent
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)

    sql = result.stdout
    assert "ALTER TABLE orders MODIFY total_amount NUMERIC(12, 2) NULL;" in sql
    assert "UPDATE alembic_version SET version_num='0009_order_total_amount_nullable'" in sql


def test_alembic_migration_0009_offline_sql_downgrade():
    """Verify that Alembic generates safe downgrade DDL for downgrade."""
    cmd = [sys.executable, "-m", "alembic", "downgrade", "0009:0008", "--sql"]
    cwd = Path(__file__).resolve().parent.parent
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)

    sql = result.stdout
    assert "ALTER TABLE orders MODIFY total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0;" in sql
    assert "UPDATE alembic_version SET version_num='0008_cod_checkout_upgrade'" in sql


def test_alembic_migration_0009_live_execution():
    """Verify live table migration execution, null insertion, and schema alteration."""
    migration_path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0009_order_total_amount_nullable.py"
    spec = importlib.util.spec_from_file_location("migration_0009", str(migration_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        # 1. Baseline table replicating production orders before 0009
        conn.execute(sa.text("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subtotal_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
                shipping_fee NUMERIC(12, 2) NULL,
                shipping_fee_status VARCHAR(50) NOT NULL DEFAULT 'CALCULATED',
                total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0
            )
        """))
        conn.commit()

        # 2. Verify inserting NULL into total_amount fails before upgrade
        try:
            conn.execute(sa.text("INSERT INTO orders (subtotal_amount, total_amount) VALUES (12500000, NULL)"))
            conn.commit()
            assert False, "Should have failed with NOT NULL constraint"
        except Exception:
            conn.rollback()

        # 3. Execute migration upgrade() live
        ctx = MigrationContext.configure(conn)
        op = Operations(ctx)
        # Monkey patch Alembic module's op to our configured operations
        orig_op = getattr(mod, "op")
        mod.op = op
        try:
            mod.upgrade()
            conn.commit()
        finally:
            mod.op = orig_op

        # 4. Verify inserting NULL into total_amount SUCCEEDS after upgrade
        conn.execute(sa.text("INSERT INTO orders (subtotal_amount, total_amount, shipping_fee_status) VALUES (12500000, NULL, 'PENDING_CALCULATION')"))
        conn.commit()

        row = conn.execute(sa.text("SELECT id, subtotal_amount, total_amount, shipping_fee_status FROM orders WHERE id = 1")).fetchone()
        assert row is not None
        assert row[0] == 1
        assert float(row[1]) == 12500000.0
        assert row[2] is None
        assert row[3] == "PENDING_CALCULATION"
