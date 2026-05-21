# src/notifications/email_service.py
"""
Email notification service for OrcaML — powered by Resend.

Each public function follows the same contract:
  1. Check the relevant UserPreferences flag (gate).
  2. Build the HTML via templates.py.
  3. Send via Resend SDK.
  4. Return True on success, False on failure (never raises).

Callers (Celery tasks, endpoints) should never have to handle exceptions
from this module — failures are logged and silently swallowed so a
notification error never breaks the main business logic.

Usage example (in a Celery task after a run completes):
    from src.notifications.email_service import notify_run_completed
    notify_run_completed(db=db, run=run)
"""

import logging
from typing import Optional
import resend  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from src.config.config import settings
from src.notifications.template import (  # ← corrigé : "templates" avec s
    run_completed_html,
    deployment_html,
    weekly_summary_html,
    security_alert_html,
)

# ---------------------------------------------------------------------------
# SDK initialisation
# ---------------------------------------------------------------------------

resend.api_key = settings.RESEND_API_KEY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _send(*, to: str, subject: str, html: str) -> bool:
    """
    Low-level wrapper around resend.Emails.send().

    Returns True if the API accepted the request, False otherwise.
    Never raises — all exceptions are caught and logged.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY is not set — email not sent to %s", to)
        return False

    try:
        response = resend.Emails.send({
            "from":    settings.RESEND_FROM_EMAIL,
            "to":      [to],
            "subject": subject,
            "html":    html,
        })
        logger.info("Email sent | id=%s | to=%s | subject=%s", response["id"], to, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


# ---------------------------------------------------------------------------
# Helper — fetch user + preferences (avoids repeating DB queries)
# ---------------------------------------------------------------------------

def _get_user_and_prefs(db: Session, user_id):
    """
    Returns (user, prefs) or (None, None) if not found.
    Lazy-creates UserPreferences with defaults if missing.
    """
    from src.auth.models.user import User
    from src.auth.models.user_preferences import UserPreferences

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning("notify: user %s not found", user_id)
        return None, None

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        # Lazy creation with defaults (mirrors the GET /me/preferences behaviour)
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    return user, prefs


# ---------------------------------------------------------------------------
# 1. Run COMPLETED notification
# ---------------------------------------------------------------------------

def notify_run_completed(*, db: Session, run) -> bool:
    """
    Send a "run completed" email to the run's owner.

    Gate  : UserPreferences.email_runs == True
    Trigger: called at the end of the Celery run task (status → COMPLETED)

    Args:
        db:  Active SQLAlchemy session.
        run: Run ORM instance (src.runs.models.run.Run).

    Returns:
        True if the email was sent, False otherwise.
    """
    # Traverse: Run → Environment → Project → User
    environment = run.environment
    project     = environment.project
    user_id     = project.user_id

    user, prefs = _get_user_and_prefs(db, user_id)
    if not user or not prefs:
        return False

    if not prefs.email_runs:
        logger.debug("email_runs disabled for user %s — skipping", user_id)
        return False

    run_url = f"https://orcaml.com/projects/{project.id}/environments/{environment.id}/runs/{run.id}"

    run_info = {
        "algorithm":        run.algorithm.value,
        "environment_name": environment.name,
        "project_name":     project.name,
        "duration_seconds": run.duration_seconds,
        # Classification metrics
        "accuracy":         run.accuracy,
        "f1_score":         run.f1_score,
        "precision":        run.precision,
        "recall":           run.recall,
        # Regression metrics
        "rmse":             run.rmse,
        "mae":              run.mae,
        "r2":               run.r2,
        "run_url":          run_url,
    }

    html = run_completed_html(
        user_name=user.full_name or user.email,
        run_info=run_info,
    )

    return _send(
        to=user.email,
        subject=f"✅ Run completed — {run.algorithm.value} on {environment.name}",
        html=html,
    )


# ---------------------------------------------------------------------------
# 2. Deployment notification (success or failure)
# ---------------------------------------------------------------------------

def notify_deployment(*, db: Session, deployment, success: bool) -> bool:
    """
    Send a deployment success or failure email to the environment's owner.

    Gate  : UserPreferences.deployments == True
    Trigger: called after a deployment status update (RUNNING → DEPLOYED / FAILED)

    Args:
        db:         Active SQLAlchemy session.
        deployment: Deployment ORM instance.
        success:    True if the deployment succeeded, False if it failed.

    Returns:
        True if the email was sent, False otherwise.
    """
    environment = deployment.environment
    project     = environment.project
    user_id     = project.user_id

    user, prefs = _get_user_and_prefs(db, user_id)
    if not user or not prefs:
        return False

    if not prefs.deployments:
        logger.debug("deployments notifications disabled for user %s — skipping", user_id)
        return False

    deployment_url = (
        f"https://orcaml.com/projects/{project.id}/environments/{environment.id}/deployments/{deployment.id}"
    )

    deployment_info = {
        "environment_name": environment.name,
        "project_name":     project.name,
        "endpoint_url":     deployment.endpoint_url,
        "error_message":    None,   # populated below on failure
        "deployment_url":   deployment_url,
    }

    if not success:
        deployment_info["error_message"] = (
            f"Deployment reached status: {deployment.status.value}. "
            "Check the deployment logs for details."
        )

    html = deployment_html(
        user_name=user.full_name or user.email,
        deployment_info=deployment_info,
        success=success,
    )

    subject = (
        f"🚀 Deployment successful — {environment.name}"
        if success else
        f"❌ Deployment failed — {environment.name}"
    )

    return _send(to=user.email, subject=subject, html=html)


# ---------------------------------------------------------------------------
# 3. Weekly summary notification
# ---------------------------------------------------------------------------

def notify_weekly_summary(*, db: Session, user_id) -> bool:
    """
    Send a weekly digest to a single user.

    Gate  : UserPreferences.weekly == True
    Trigger: Celery beat task, runs every Monday morning.

    Args:
        db:      Active SQLAlchemy session.
        user_id: UUID of the target user.

    Returns:
        True if the email was sent, False otherwise.
    """
    from src.runs.models.run import Run, RunStatus
    from src.deployments.models.deployment import Deployment
    from src.deployments.models.enums import DeploymentStatus
    from src.project.models.project import Project
    from src.environment.models.Environment import Environment
    from datetime import timedelta, timezone
    from datetime import datetime

    user, prefs = _get_user_and_prefs(db, user_id)
    if not user or not prefs:
        return False

    if not prefs.weekly:
        logger.debug("weekly digest disabled for user %s — skipping", user_id)
        return False

    # Compute stats for the past 7 days
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    runs_q = (
        db.query(Run)
        .join(Environment, Run.environment_id == Environment.id)
        .join(Project,     Environment.project_id == Project.id)
        .filter(Project.user_id == user_id)
        .filter(Run.created_at >= one_week_ago)
    )

    all_runs       = runs_q.all()
    completed_runs = [r for r in all_runs if r.status == RunStatus.COMPLETED]
    failed_runs    = [r for r in all_runs if r.status == RunStatus.FAILED]

    best_accuracy: Optional[float] = None
    best_r2:       Optional[float] = None
    for r in completed_runs:
        if r.accuracy is not None:
            best_accuracy = max(best_accuracy or 0.0, r.accuracy)
        if r.r2 is not None:
            best_r2 = max(best_r2 or float("-inf"), r.r2)

    deployments_q = (
        db.query(Deployment)
        .join(Environment, Deployment.environment_id == Environment.id)
        .join(Project,     Environment.project_id == Project.id)
        .filter(Project.user_id == user_id)
    )
    all_deployments    = deployments_q.all()
    active_deployments = [d for d in all_deployments if d.status == DeploymentStatus.DEPLOYED]

    stats = {
        "total_runs":          len(all_runs),
        "completed_runs":      len(completed_runs),
        "failed_runs":         len(failed_runs),
        "total_deployments":   len(all_deployments),
        "active_deployments":  len(active_deployments),
        "best_accuracy":       best_accuracy,
        "best_r2":             best_r2,
        "profile_url":         "https://orcaml.com/profile",
    }

    html = weekly_summary_html(
        user_name=user.full_name or user.email,
        stats=stats,
    )

    return _send(
        to=user.email,
        subject="📊 Your weekly OrcaML summary",
        html=html,
    )


# ---------------------------------------------------------------------------
# 4. Security alert notification
# ---------------------------------------------------------------------------

def notify_security_event(*, db: Session, user_id, event: str) -> bool:
    """
    Send a security alert email to a user.

    Gate  : UserPreferences.security == True
    Trigger: called inline (not via Celery) from the relevant endpoint:
        - PATCH /users/me/password  → event="password_changed"
        - POST  /users/me/api-keys  → event="api_key_created"
        - DELETE /users/me/api-keys → event="api_key_deleted"

    Args:
        db:      Active SQLAlchemy session.
        user_id: UUID of the target user.
        event:   One of: 'password_changed', 'login_new_device',
                          'api_key_created', 'api_key_deleted'.

    Returns:
        True if the email was sent, False otherwise.
    """
    user, prefs = _get_user_and_prefs(db, user_id)
    if not user or not prefs:
        return False

    if not prefs.security:
        logger.debug("security notifications disabled for user %s — skipping", user_id)
        return False

    html = security_alert_html(
        user_name=user.full_name or user.email,
        event=event,
        profile_url="https://orcaml.com/profile",
    )

    event_subjects = {
        "password_changed":  "🔒 Your OrcaML password was changed",
        "login_new_device":  "🔒 New login detected on your OrcaML account",
        "api_key_created":   "🔒 New API key created on your OrcaML account",
        "api_key_deleted":   "🔒 An API key was revoked on your OrcaML account",
    }
    subject = event_subjects.get(event, "🔒 Security alert — OrcaML")

    return _send(to=user.email, subject=subject, html=html)