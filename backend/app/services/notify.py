"""Outbound notifications (email) — best-effort, never blocks the request.

Currently used to alert on new user feedback. SMTP is optional: when not
configured, calls are no-ops (feedback is still persisted), so local/dev runs
don't fail. Uses the stdlib `smtplib` (no extra dependency).
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_email(subject: str, body: str, to: str | None = None) -> bool:
    """Send a plain-text email. Returns True on success, False otherwise.

    Best-effort: any failure (or missing config) is swallowed and returns False.
    """
    recipient = (to or settings.feedback_alert_email or "").strip()
    if not recipient or not email_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject[:200]
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = recipient
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
        return True
    except Exception:
        return False


def notify_feedback(fb: dict) -> None:
    """Email an alert for one feedback submission (best-effort background task)."""
    rating = fb.get("rating", 0)
    stars = "★" * int(rating or 0) + "☆" * (5 - int(rating or 0))
    note = (fb.get("note") or "").strip() or "(no note)"
    low = int(rating or 0) <= 2
    flag = "⚠️ LOW RATING " if low else ""
    subject = f"{flag}Travel Agent feedback: {rating}/5"
    body = (
        f"New feedback received.\n\n"
        f"Rating:      {rating}/5  {stars}\n"
        f"Note:        {note}\n"
        f"Query:       {fb.get('query') or '-'}\n"
        f"Destination: {fb.get('destination') or '-'}\n"
        f"Page:        {fb.get('page') or '-'}\n"
        f"User:        {fb.get('user_email') or 'anonymous'}\n"
        f"Time (UTC):  {fb.get('ts') or '-'}\n"
    )
    send_email(subject, body)
