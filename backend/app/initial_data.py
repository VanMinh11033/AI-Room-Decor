from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import Cart, Role, RoleName, User, UserProfile


def seed_initial_data(db: Session) -> None:
    for role_name in RoleName:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            db.add(Role(name=role_name, description=f"{role_name.value} role"))
    db.commit()

    if not settings.admin_email or not settings.admin_password:
        return

    admin_role = db.query(Role).filter(Role.name == RoleName.ADMIN).first()
    existing = db.query(User).filter(User.email == settings.admin_email).first()
    if existing or admin_role is None:
        return

    admin = User(
        email=settings.admin_email,
        full_name=settings.admin_full_name,
        hashed_password=get_password_hash(settings.admin_password),
        role_id=admin_role.id,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    db.add(UserProfile(user_id=admin.id))
    db.add(Cart(user_id=admin.id))
    db.commit()

