"""Notification delivery (§26.2, SEC-014, ADR-0025).

Every notification is persisted as an in-app row (durable, readable via `GET /notifications`).
When the alert's channel is `email`, it is *also* sent through the configured email backend:
- `LogEmailBackend` (default) — no SMTP provider is configured in this project, so email is
  logged (PII-safe: recipient + subject, never body secrets) rather than silently dropped.
- `SmtpEmailBackend` — real SMTP when the SMTP_* settings are provided.

Keeping email behind an interface means the alert-dispatch job never knows which backend is live,
and tests use the log backend with zero network.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import User
from app.repositories import notifications as notif_repo
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)


class EmailBackend(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, body: str) -> None: ...


class LogEmailBackend(EmailBackend):
    """Logs the delivery instead of sending (no provider configured). PII-safe: no body in logs."""

    def send(self, *, to: str, subject: str, body: str) -> None:
        log_event(logger, logging.INFO, "notification.email.logged", to=to, subject=subject)


class SmtpEmailBackend(EmailBackend):
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def send(self, *, to: str, subject: str, body: str) -> None:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self._s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port) as smtp:
            smtp.starttls()
            if self._s.smtp_user:
                smtp.login(self._s.smtp_user, self._s.smtp_password)
            smtp.send_message(msg)


def get_email_backend(settings: Settings | None = None) -> EmailBackend:
    settings = settings or get_settings()
    if settings.notification_email_backend == "smtp" and settings.smtp_host:
        return SmtpEmailBackend(settings)
    return LogEmailBackend()


class NotificationSender:
    """Persists an in-app notification and, for the `email` channel, also sends an email."""

    def __init__(self, email_backend: EmailBackend | None = None) -> None:
        self._email = email_backend or get_email_backend()

    def send(
        self,
        session: Session,
        *,
        user: User,
        alert_id: int | None,
        company_id: int | None,
        title: str,
        body: str,
        channel: str,
    ) -> None:
        notif_repo.create(
            session,
            user_id=user.id,
            alert_id=alert_id,
            company_id=company_id,
            title=title,
            body=body,
            channel=channel,
        )
        if channel == "email":
            self._email.send(to=user.email, subject=title, body=body)
