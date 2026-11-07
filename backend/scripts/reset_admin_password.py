"""Reset the password of the existing ADMIN account (safe recovery).

- Targets the single seeded ADMIN (settings.admin_email) and does nothing if it
  is missing, so it never creates a duplicate account.
- Uses the application's own ``get_password_hash`` (bcrypt via passlib).
- Prompts for the new password with ``getpass`` so it is never echoed, never
  placed in shell history, and never written to a file or log.

Run from the backend directory:

    python scripts/reset_admin_password.py
"""

import getpass
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.entities import Role, RoleName, User  # noqa: E402


def find_admin(db: Session) -> User | None:
    return (
        db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(Role.name == RoleName.ADMIN, User.email == settings.admin_email)
        .first()
    )


def main() -> int:
    db = SessionLocal()
    try:
        admin = find_admin(db)
        if admin is None:
            print(f"No ADMIN account found for email {settings.admin_email!r}. Nothing changed.")
            return 1

        print(f"Found ADMIN: id={admin.id} email={admin.email!r} full_name={admin.full_name!r}")

        password = getpass.getpass("New ADMIN password: ")
        if len(password) < 8:
            print("Password must be at least 8 characters. Nothing changed.")
            return 1
        confirm = getpass.getpass("Confirm new ADMIN password: ")
        if password != confirm:
            print("Passwords do not match. Nothing changed.")
            return 1

        admin.hashed_password = get_password_hash(password)
        admin.is_active = True
        db.commit()
        print("Password updated successfully. Log in with this email and your new password.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
