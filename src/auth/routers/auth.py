from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.db import get_db
from src.auth.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from src.auth.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new user account."""
    return register_user(body, db)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Verify credentials and return a JWT token."""
    return login_user(body, db)
