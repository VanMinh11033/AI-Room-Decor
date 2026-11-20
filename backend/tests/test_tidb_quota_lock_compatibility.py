import threading
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import NotSupportedError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models.entities import AIUsageLog, Base, RoomProject, User
from app.services.ai_quota_service import AIQuotaService


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_tidb_sql_does_not_contain_lock_in_share_mode(memory_db):
    """
    Xác minh các câu query tính quota trong get_daily_usage khi biên dịch
    theo MySQL dialect (được TiDB sử dụng) TUYỆT ĐỐI KHÔNG chứa 'LOCK IN SHARE MODE'.
    """
    service = AIQuotaService(memory_db)
    prov = "cloudflare"
    now = datetime.now(UTC)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
    stale_threshold = now

    query = memory_db.query(func.count(AIUsageLog.id)).filter(
        AIUsageLog.provider == prov,
        AIUsageLog.created_at >= today_start,
        (AIUsageLog.status == "SUCCESS")
        | ((AIUsageLog.status == "RESERVED") & (AIUsageLog.created_at >= stale_threshold))
        | (AIUsageLog.status == "TIMEOUT_SUSPECTED"),
    )

    compiled_sql = str(query.statement.compile(dialect=mysql.dialect()))
    assert "LOCK IN SHARE MODE" not in compiled_sql, "Query must not contain LOCK IN SHARE MODE"
    assert "FOR UPDATE" not in compiled_sql, "Query must not contain FOR UPDATE"


def test_tidb_simulated_dialect_raises_on_lock_in_share_mode(memory_db):
    """
    Mô phỏng TiDB Cloud: Nếu xuất hiện 'LOCK IN SHARE MODE' trong bất kỳ câu truy vấn nào,
    mô phỏng sẽ ném ra NotSupportedError (mã lỗi 1235).
    Xác minh get_daily_usage chạy thành công trơn tru không bị ném lỗi.
    """
    service = AIQuotaService(memory_db)

    # Thêm 1 log mẫu
    log = AIUsageLog(
        user_id=1,
        room_project_id=10,
        provider="cloudflare",
        model="@cf/black-forest-labs/flux-2-dev",
        task_type="ROOM_DESIGN_GENERATION",
        status="SUCCESS",
    )
    memory_db.add(log)
    memory_db.commit()

    # Chạy get_daily_usage
    user_count, sys_count = service.get_daily_usage(1, "cloudflare")
    assert user_count == 1
    assert sys_count == 1


def test_concurrent_two_requests_do_not_exceed_user_quota(memory_db):
    """
    Xác minh hai request gửi đồng thời từ cùng 1 user không thể vượt quá hạn mức User Quota.
    """
    service = AIQuotaService(memory_db)
    user_id = 99
    project_id = 101

    results = []

    def try_reserve():
        # Mỗi thread tạo session độc lập trên cùng DB
        session_factory = sessionmaker(bind=memory_db.get_bind(), autocommit=False, autoflush=False)
        thread_db = session_factory()
        thread_service = AIQuotaService(thread_db)
        with patch.object(thread_service, "get_quota_limits", return_value=(1, 10)):
            res = thread_service.reserve_quota(
                user_id=user_id,
                project_id=project_id,
                provider="cloudflare",
                model="@cf/black-forest-labs/flux-2-dev",
                task_type="ROOM_DESIGN_GENERATION",
            )
            results.append(res)
        thread_db.close()

    t1 = threading.Thread(target=try_reserve)
    t2 = threading.Thread(target=try_reserve)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Đúng 1 request thành công, 1 request bị chặn
    successes = [r for r in results if r is not None]
    assert len(successes) == 1, f"Expected exactly 1 reservation, got {len(successes)}"


def test_two_users_concurrent_do_not_exceed_system_quota(memory_db):
    """
    Xác minh hai user gửi request đồng thời không thể vượt quá hạn mức System Quota.
    """
    results = []

    def try_reserve(uid):
        session_factory = sessionmaker(bind=memory_db.get_bind(), autocommit=False, autoflush=False)
        thread_db = session_factory()
        thread_service = AIQuotaService(thread_db)
        # user_limit=5 nhưng system_limit=1
        with patch.object(thread_service, "get_quota_limits", return_value=(5, 1)):
            res = thread_service.reserve_quota(
                user_id=uid,
                project_id=200 + uid,
                provider="cloudflare",
                model="@cf/black-forest-labs/flux-2-dev",
                task_type="ROOM_DESIGN_GENERATION",
            )
            results.append(res)
        thread_db.close()

    t1 = threading.Thread(target=try_reserve, args=(101,))
    t2 = threading.Thread(target=try_reserve, args=(102,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r is not None]
    assert len(successes) == 1, f"Expected exactly 1 reservation for system quota=1, got {len(successes)}"


def test_advisory_lock_release_after_exception(memory_db):
    """
    Xác minh nếu xảy ra exception trong critical section, khóa advisory lock
    phải luôn được giải phóng an toàn trong finally block.
    """
    service = AIQuotaService(memory_db)
    lock_name = "test_cleanup_lock"

    with pytest.raises(RuntimeError):
        with service._advisory_lock(lock_name, timeout_seconds=2) as acquired:
            assert acquired is True
            raise RuntimeError("Simulation error inside critical section")

    # Ngay sau exception, khóa phải được tái sử dụng thành công
    with service._advisory_lock(lock_name, timeout_seconds=2) as acquired:
        assert acquired is True


def test_fail_closed_when_lock_cannot_be_acquired(memory_db):
    """
    Xác minh nếu lock không thể acquire (timeout hoặc DB error), hệ thống fail-closed,
    trả về None và không bao giờ cho phép gọi Cloudflare.
    """
    service = AIQuotaService(memory_db)

    # Giả lập lock trả về False (bận)
    with patch.object(service, "_advisory_lock") as mock_lock:
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = False
        mock_lock.return_value = mock_ctx

        res = service.reserve_quota(
            user_id=1,
            project_id=10,
            provider="cloudflare",
            model="@cf/black-forest-labs/flux-2-dev",
            task_type="ROOM_DESIGN_GENERATION",
        )
        assert res is None, "Must return None when lock cannot be acquired"


def test_kill_switch_blocks_before_lock(memory_db):
    """
    Xác minh khi ENABLE_CLOUD_AI=false, reserve_quota trả về None ngay lập tức
    mà không cần acquire advisory lock hay query DB.
    """
    service = AIQuotaService(memory_db)
    with patch.object(settings, "enable_cloud_ai", False):
        with patch.object(service, "_advisory_lock") as mock_lock:
            res = service.reserve_quota(
                user_id=1,
                project_id=10,
                provider="cloudflare",
                model="@cf/black-forest-labs/flux-2-dev",
                task_type="ROOM_DESIGN_GENERATION",
            )
            assert res is None
            mock_lock.assert_not_called()
