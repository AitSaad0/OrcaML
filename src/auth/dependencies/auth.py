from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import uuid

from src.config.db import get_db
from src.auth.models.user import User
from src.auth.security.tokens import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract token → verify → load user. Raises 401 if anything is wrong."""
    token = credentials.credentials
    user_id = decode_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Convert string to UUID object for PostgreSQL compatibility
    # SQLite stores UUIDs as strings so we try both
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token payload")

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        # Fallback: try string comparison (SQLite in tests)
        user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    return user
