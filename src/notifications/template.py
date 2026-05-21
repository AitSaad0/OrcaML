# src/notifications/templates.py
"""
HTML email templates for OrcaML notifications.

All templates share a common base layout (header + card + footer).
Call the specific function for each notification type and pass the result
as the `html` parameter to the Resend API.
"""

from datetime import datetime


# ---------------------------------------------------------------------------
# Palette & shared constants
# ---------------------------------------------------------------------------

PRIMARY   = "#6366f1"   # Indigo — main brand color
SUCCESS   = "#22c55e"   # Green
DANGER    = "#ef4444"   # Red
WARNING   = "#f59e0b"   # Amber
BG        = "#f8fafc"   # Page background
CARD_BG   = "#ffffff"
TEXT_MAIN = "#0f172a"
TEXT_SUB  = "#64748b"
BORDER    = "#e2e8f0"


# ---------------------------------------------------------------------------
# Base layout
# ---------------------------------------------------------------------------

def _base(title: str, body: str) -> str:
    """Wraps `body` (inner HTML) in the shared OrcaML email shell."""
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{BG};padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;">

          <!-- ── Header ── -->
          <tr>
            <td align="center" style="padding-bottom:28px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:{PRIMARY};border-radius:12px;padding:10px 20px;">
                    <span style="color:#fff;font-size:20px;font-weight:700;letter-spacing:-0.3px;">
                      🐋 OrcaML
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ── Card ── -->
          <tr>
            <td style="background:{CARD_BG};border-radius:16px;border:1px solid {BORDER};
                        box-shadow:0 1px 3px rgba(0,0,0,.06);padding:40px 40px 32px;">
              {body}
            </td>
          </tr>

          <!-- ── Footer ── -->
          <tr>
            <td align="center" style="padding-top:28px;">
              <p style="margin:0;font-size:12px;color:{TEXT_SUB};line-height:1.6;">
                You're receiving this email because you have notifications enabled on
                <a href="https://orcaml.com" style="color:{PRIMARY};text-decoration:none;">OrcaML</a>.<br/>
                Manage your preferences in your
                <a href="https://orcaml.com/profile" style="color:{PRIMARY};text-decoration:none;">profile settings</a>.
              </p>
              <p style="margin:12px 0 0;font-size:11px;color:#94a3b8;">
                © {year} OrcaML — All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Shared components
# ---------------------------------------------------------------------------

def _heading(text: str) -> str:
    return f'<h1 style="margin:0 0 8px;font-size:22px;font-weight:700;color:{TEXT_MAIN};letter-spacing:-0.3px;">{text}</h1>'


def _subtext(text: str) -> str:
    return f'<p style="margin:0 0 28px;font-size:15px;color:{TEXT_SUB};line-height:1.6;">{text}</p>'


def _divider() -> str:
    return f'<hr style="border:none;border-top:1px solid {BORDER};margin:24px 0;" />'


def _metric_row(label: str, value: str) -> str:
    return f"""
    <tr>
      <td style="padding:10px 0;font-size:14px;color:{TEXT_SUB};border-bottom:1px solid {BORDER};">{label}</td>
      <td style="padding:10px 0;font-size:14px;color:{TEXT_MAIN};font-weight:600;text-align:right;border-bottom:1px solid {BORDER};">{value}</td>
    </tr>"""


def _badge(text: str, color: str) -> str:
    return f'<span style="display:inline-block;background:{color}1a;color:{color};border:1px solid {color}33;border-radius:6px;padding:2px 10px;font-size:12px;font-weight:600;">{text}</span>'


def _cta_button(label: str, url: str, color: str = PRIMARY) -> str:
    return f"""
    <table cellpadding="0" cellspacing="0" style="margin-top:28px;">
      <tr>
        <td style="background:{color};border-radius:8px;">
          <a href="{url}" style="display:inline-block;padding:12px 24px;color:#fff;
             font-size:14px;font-weight:600;text-decoration:none;letter-spacing:0.1px;">
            {label}
          </a>
        </td>
      </tr>
    </table>"""


# ---------------------------------------------------------------------------
# Template 1 — Run COMPLETED
# ---------------------------------------------------------------------------

def run_completed_html(user_name: str, run_info: dict) -> str:
    """
    Email sent after a run reaches COMPLETED status (if email_runs == True).

    Expected run_info keys:
        algorithm (str), environment_name (str), project_name (str),
        duration_seconds (float | None),
        # Classification
        accuracy (float | None), f1_score (float | None),
        precision (float | None), recall (float | None),
        # Regression
        rmse (float | None), mae (float | None), r2 (float | None),
        run_url (str)
    """
    algo      = run_info.get("algorithm", "—")
    env_name  = run_info.get("environment_name", "—")
    proj_name = run_info.get("project_name", "—")
    duration  = run_info.get("duration_seconds")
    run_url   = run_info.get("run_url", "https://orcaml.com")

    duration_str = f"{duration:.1f}s" if duration is not None else "—"

    # Determine task type from available metrics
    is_regression = run_info.get("r2") is not None or run_info.get("rmse") is not None

    if is_regression:
        metrics_rows = ""
        if run_info.get("r2")   is not None: metrics_rows += _metric_row("R²",   f"{run_info['r2']:.4f}")
        if run_info.get("rmse") is not None: metrics_rows += _metric_row("RMSE", f"{run_info['rmse']:.4f}")
        if run_info.get("mae")  is not None: metrics_rows += _metric_row("MAE",  f"{run_info['mae']:.4f}")
    else:
        metrics_rows = ""
        if run_info.get("accuracy")  is not None: metrics_rows += _metric_row("Accuracy",  f"{run_info['accuracy'] * 100:.2f}%")
        if run_info.get("f1_score")  is not None: metrics_rows += _metric_row("F1 Score",  f"{run_info['f1_score']:.4f}")
        if run_info.get("precision") is not None: metrics_rows += _metric_row("Precision", f"{run_info['precision']:.4f}")
        if run_info.get("recall")    is not None: metrics_rows += _metric_row("Recall",    f"{run_info['recall']:.4f}")

    body = f"""
    {_heading("Your run just completed ✅")}
    {_subtext(f"Hi {user_name}, your training run for <strong>{proj_name} / {env_name}</strong> finished successfully.")}

    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
      {_metric_row("Algorithm",  _badge(algo, PRIMARY))}
      {_metric_row("Duration",   duration_str)}
      {metrics_rows}
    </table>

    {_cta_button("View Run Details →", run_url)}
    """

    return _base(f"Run completed — {algo}", body)


# ---------------------------------------------------------------------------
# Template 2 — Deployment (success or failure)
# ---------------------------------------------------------------------------

def deployment_html(user_name: str, deployment_info: dict, success: bool) -> str:
    """
    Email sent after a deployment event (if deployments == True).
    Covers both success and failure states.

    Expected deployment_info keys:
        environment_name (str), project_name (str),
        endpoint_url (str | None),   # only on success
        error_message (str | None),  # only on failure
        deployment_url (str)
    """
    env_name   = deployment_info.get("environment_name", "—")
    proj_name  = deployment_info.get("project_name", "—")
    deploy_url = deployment_info.get("deployment_url", "https://orcaml.com")

    if success:
        endpoint = deployment_info.get("endpoint_url", "—")
        color    = SUCCESS
        icon     = "🚀"
        headline = "Deployment successful"
        detail   = f"Your model for <strong>{proj_name} / {env_name}</strong> is now live and ready to serve predictions."
        extra    = f"""
        {_divider()}
        <p style="margin:0 0 6px;font-size:13px;color:{TEXT_SUB};font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Endpoint URL</p>
        <code style="display:block;background:#f1f5f9;border:1px solid {BORDER};border-radius:6px;
                     padding:10px 14px;font-size:13px;color:{PRIMARY};word-break:break-all;">{endpoint}</code>
        {_cta_button("Open Deployment →", deploy_url, SUCCESS)}
        """
    else:
        error_msg = deployment_info.get("error_message", "An unexpected error occurred.")
        color     = DANGER
        icon      = "❌"
        headline  = "Deployment failed"
        detail    = f"Something went wrong while deploying your model for <strong>{proj_name} / {env_name}</strong>."
        extra     = f"""
        {_divider()}
        <p style="margin:0 0 6px;font-size:13px;color:{TEXT_SUB};font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Error Details</p>
        <code style="display:block;background:#fef2f2;border:1px solid #fecaca;border-radius:6px;
                     padding:10px 14px;font-size:13px;color:{DANGER};word-break:break-all;">{error_msg}</code>
        {_cta_button("View Deployment Logs →", deploy_url, DANGER)}
        """

    body = f"""
    <div style="display:inline-block;background:{color}1a;border:1px solid {color}33;
                border-radius:8px;padding:6px 14px;margin-bottom:20px;">
      <span style="color:{color};font-size:13px;font-weight:600;">{icon} {headline}</span>
    </div>
    {_heading(headline)}
    {_subtext(detail)}
    {extra}
    """

    return _base(headline, body)


# ---------------------------------------------------------------------------
# Template 3 — Weekly summary
# ---------------------------------------------------------------------------

def weekly_summary_html(user_name: str, stats: dict) -> str:
    """
    Weekly digest email (if weekly == True).

    Expected stats keys:
        total_runs (int), completed_runs (int), failed_runs (int),
        total_deployments (int), active_deployments (int),
        best_accuracy (float | None), best_r2 (float | None),
        profile_url (str)
    """
    total_runs         = stats.get("total_runs", 0)
    completed_runs     = stats.get("completed_runs", 0)
    failed_runs        = stats.get("failed_runs", 0)
    total_deployments  = stats.get("total_deployments", 0)
    active_deployments = stats.get("active_deployments", 0)
    best_accuracy      = stats.get("best_accuracy")
    best_r2            = stats.get("best_r2")
    profile_url        = stats.get("profile_url", "https://orcaml.com/profile")

    best_metric_row = ""
    if best_accuracy is not None:
        best_metric_row = _metric_row("Best Accuracy (this week)", f"{best_accuracy * 100:.2f}%")
    elif best_r2 is not None:
        best_metric_row = _metric_row("Best R² (this week)", f"{best_r2:.4f}")

    body = f"""
    {_heading("Your weekly OrcaML summary 📊")}
    {_subtext(f"Hi {user_name}, here's what happened on your workspace this week.")}

    <table width="100%" cellpadding="0" cellspacing="0">
      {_metric_row("Total Runs",          str(total_runs))}
      {_metric_row("Completed",           _badge(str(completed_runs), SUCCESS))}
      {_metric_row("Failed",              _badge(str(failed_runs), DANGER) if failed_runs > 0 else "0")}
      {_metric_row("Total Deployments",   str(total_deployments))}
      {_metric_row("Active Deployments",  _badge(str(active_deployments), PRIMARY))}
      {best_metric_row}
    </table>

    {_cta_button("Go to Dashboard →", profile_url)}
    """

    return _base("Your weekly OrcaML summary", body)


# ---------------------------------------------------------------------------
# Template 4 — Security alert
# ---------------------------------------------------------------------------

_SECURITY_EVENTS: dict[str, dict] = {
    "password_changed": {
        "label":  "Your password was changed",
        "detail": "Your OrcaML account password was successfully updated. If you didn't make this change, please reset your password immediately.",
        "cta":    ("Secure My Account →", WARNING),
    },
    "login_new_device": {
        "label":  "New login detected",
        "detail": "A sign-in to your OrcaML account was detected from a new device or location. If this was you, no action is needed.",
        "cta":    ("Review Active Sessions →", WARNING),
    },
    "api_key_created": {
        "label":  "New API key created",
        "detail": "A new API key was generated for your account. If you didn't create it, revoke it immediately from your profile.",
        "cta":    ("Manage API Keys →", DANGER),
    },
    "api_key_deleted": {
        "label":  "API key revoked",
        "detail": "An API key on your account was deleted. If you didn't do this, please secure your account.",
        "cta":    ("Manage API Keys →", WARNING),
    },
}

_SECURITY_DEFAULT = {
    "label":  "Security alert",
    "detail": "A security event was detected on your OrcaML account. Please review your account activity.",
    "cta":    ("Review Account →", WARNING),
}


def security_alert_html(user_name: str, event: str, profile_url: str = "https://orcaml.com/profile") -> str:
    """
    Email sent on security events (if security == True).

    Args:
        user_name:   Display name of the recipient.
        event:       One of the keys in _SECURITY_EVENTS
                     ('password_changed', 'login_new_device',
                      'api_key_created', 'api_key_deleted').
        profile_url: Deep link to the relevant profile section.
    """
    meta   = _SECURITY_EVENTS.get(event, _SECURITY_DEFAULT)
    label  = meta["label"]
    detail = meta["detail"]
    cta_label, cta_color = meta["cta"]

    body = f"""
    <div style="display:inline-block;background:{WARNING}1a;border:1px solid {WARNING}33;
                border-radius:8px;padding:6px 14px;margin-bottom:20px;">
      <span style="color:{WARNING};font-size:13px;font-weight:600;">🔒 Security Notice</span>
    </div>
    {_heading(label)}
    {_subtext(f"Hi {user_name}, {detail}")}
    {_divider()}
    <p style="margin:0;font-size:14px;color:{TEXT_SUB};line-height:1.6;">
      If you did not initiate this action, please secure your account immediately by changing your password
      and revoking any API keys you don't recognize.
    </p>
    {_cta_button(cta_label, profile_url, cta_color)}
    """

    return _base(label, body)