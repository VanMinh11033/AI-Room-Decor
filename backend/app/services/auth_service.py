from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_password
from app.models.entities import Cart, Role, RoleName, User, UserProfile


def create_customer(db: Session, email: str, password: str, full_name: str) -> User:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    customer_role = db.query(Role).filter(Role.name == RoleName.CUSTOMER).first()
    if customer_role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Customer role is not seeded")
    user = User(
        email=email.lower(),
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role_id=customer_role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id))
    db.add(Cart(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    return user


def build_token_pair(user: User) -> dict:
    subject = str(user.id)
    return {
        "access_token": create_access_token(subject),
        "refresh_token": create_refresh_token(subject),
        "token_type": "bearer",
        "user": user,
    }

