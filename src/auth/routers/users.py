from fastapi import APIRouter, Depends
from src.auth.models.user import User
from src.auth.schemas.user import UserResponse
from src.auth.dependencies.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently logged-in user."""
    return current_user
