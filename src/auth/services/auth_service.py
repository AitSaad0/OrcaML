from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.auth.models.user import User
from src.auth.schemas.user import RegisterRequest, LoginRequest, TokenResponse
from src.auth.security.hashing import hash_password, verify_password
from src.auth.security.tokens import create_access_token
from src.config.config import settings


def register_user(body: RegisterRequest, db: Session) -> User:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )
    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login_user(body: LoginRequest, db: Session) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    token = create_access_token(user_id=str(user.id))
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
