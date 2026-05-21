from fastapi import APIRouter, Depends
from src.auth.models.user import User
from uuid import UUID
from src.auth.schemas.user import UserResponse
from src.auth.dependencies.auth import get_current_user
from src.config.db import get_db
from sqlalchemy.orm import Session
from src.auth.schemas.user import UpdateUserRequest , UpdatePasswordRequest
from fastapi import HTTPException, status
from src.auth.security.hashing import hash_password, verify_password
from src.project.models.project import Project
from src.environment.models.Environment import Environment
from src.runs.models.run import Run, RunStatus
from src.deployments.models.deployment import Deployment
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from src.auth.models.api_keys import ApiKey
from src.auth.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
from src.auth.security.hashing import hash_password 
from src.auth.models.user_preferences import UserPreferences
from src.auth.schemas.preferences import PreferencesResponse, PreferencesUpdate
from datetime import datetime, timezone
from src.notifications.email_service import notify_security_event  # ← ajouté

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently logged-in user."""
    return current_user

@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the profile of the currently logged-in user."""
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.email is not None:
        current_user.email = body.email
    db.commit()
    db.refresh(current_user)
    return current_user

@router.patch("/me/password", status_code=status.HTTP_200_OK)
def update_password(
    body: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    notify_security_event(db=db, user_id=current_user.id, event="password_changed")  # ← ajouté
    return {"message": "Password updated successfully"}

@router.get("/me/stats")
def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).count()

    total_runs = (
        db.query(Run)
        .join(Environment, Run.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .filter(Project.user_id == current_user.id)
        .filter(Run.status == RunStatus.COMPLETED)
        .count()
    )

    total_deployments = (
        db.query(Deployment)
        .join(Environment, Deployment.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .filter(Project.user_id == current_user.id)
        .count()
    )

    return {
        "total_projects":     total_projects,
        "total_runs":         total_runs,
        "total_deployments":  total_deployments,
    }
    from datetime import datetime, timedelta, timezone
from collections import defaultdict

@router.get("/me/activity")
def get_my_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(weeks=52)

    runs = (
        db.query(Run.finished_at)
        .join(Environment, Run.environment_id == Environment.id)
        .join(Project, Environment.project_id == Project.id)
        .filter(Project.user_id == current_user.id)
        .filter(Run.status == RunStatus.COMPLETED)
        .filter(Run.finished_at >= since)
        .all()
    )

    activity: dict[str, int] = defaultdict(int)
    for (finished_at,) in runs:
        if finished_at:
            day = finished_at.strftime("%Y-%m-%d")
            activity[day] += 1

    return activity


@router.get("/me/api-keys", response_model=list[ApiKeyResponse])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active == True,
    ).all()


@router.post("/me/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw_key, prefix = ApiKey.generate()
    api_key = ApiKey(
        user_id  = current_user.id,
        name     = body.name,
        key_hash = hash_password(raw_key),
        prefix   = prefix,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    notify_security_event(db=db, user_id=current_user.id, event="api_key_created")  # ← ajouté
    return ApiKeyCreatedResponse(
        id           = api_key.id,
        name         = api_key.name,
        prefix       = api_key.prefix,
        created_at   = api_key.created_at,
        raw_key      = raw_key,
    )


@router.delete("/me/api-keys/{key_id}", status_code=204)
def delete_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    api_key = db.query(ApiKey).filter(
        ApiKey.id      == key_id,
        ApiKey.user_id == current_user.id,
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(api_key)
    db.commit()
    notify_security_event(db=db, user_id=current_user.id, event="api_key_deleted")  # ← ajouté

@router.get("/me/preferences", response_model=PreferencesResponse)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.id
    ).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.patch("/me/preferences", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.id
    ).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    if body.email_runs  is not None: prefs.email_runs  = body.email_runs
    if body.deployments is not None: prefs.deployments = body.deployments
    if body.weekly      is not None: prefs.weekly      = body.weekly
    if body.security    is not None: prefs.security    = body.security
    prefs.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prefs)
    return prefs