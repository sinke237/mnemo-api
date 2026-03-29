"""Simple email enqueue/send scaffolding.

This module provides a minimal placeholder for enqueuing outbound emails.
Production deployments should replace this with an async queue or external
email provider integration.
"""

import logging
import smtplib
from email.message import EmailMessage
from importlib import resources
from urllib.parse import urlparse

from mnemo.core.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, reset_url: str, *, user_id: str | None = None) -> None:
    """Enqueue/send a password reset email.

    This is a placeholder implementation that logs the action. In production
    this should enqueue a job or call an external email service.
    """
    # IMPORTANT: do not log the raw token or include it in telemetry.
    settings = get_settings()

    def mask_email(addr: str) -> str:
        try:
            local, domain = addr.split("@", 1)
        except Exception:
            return "***"
        if not local:
            return f"***@{domain}"
        return f"{local[0]}***@{domain}"

    masked = mask_email(email)
    logger.info("Password reset requested (user_id=%s, recipient=%s)", user_id, masked)
    # Do NOT log the raw reset URL or token. Log only that a link was generated
    # and the destination domain for telemetry.
    try:
        settings = get_settings()
        # Log only the frontend domain for telemetry to avoid leaking full URLs
        try:
            parsed = urlparse(settings.frontend_base_url)
            frontend_domain = parsed.netloc or settings.frontend_base_url
        except Exception:
            frontend_domain = settings.frontend_base_url
        logger.debug("Reset link domain: %s", frontend_domain)
    except Exception:
        logger.debug("Reset link generated")

    if not settings.smtp_enabled:
        logger.info("SMTP disabled; skipping actual send for %s", masked)
        return

    # Render email from template stored in package resources. Template must not
    # include the raw token in logs; only the front-end link is placed in the
    # email body.
    try:
        tpl = resources.files("mnemo").joinpath("templates", "password_reset.txt").read_text()
    except Exception:
        # Fallback to inline text if template not available
        tpl = (
            "Hi,\n\nWe received a request to reset your Mnemo account password.\n\n"
            "To reset your password, open the link below (expires in 1 hour):\n\n{reset_link}\n\n"
            "If you did not request this, you can safely ignore this email.\n\n"
            "Thanks,\nMnemo"
        )

    body = tpl.format(reset_link=reset_url)

    msg = EmailMessage()
    msg["Subject"] = "Reset your Mnemo password"
    msg["From"] = settings.smtp_from_address
    msg["To"] = email
    msg.set_content(body)

    try:
        if getattr(settings, "smtp_implicit_ssl", False):
            # Implicit SSL (SMTPS), typically on port 465
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp_ssl:
                if settings.smtp_username and settings.smtp_password:
                    smtp_ssl.login(settings.smtp_username, settings.smtp_password)
                smtp_ssl.send_message(msg)
        elif settings.smtp_use_tls:
            # Use STARTTLS: open plain connection then upgrade
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp_tls:
                smtp_tls.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp_tls.login(settings.smtp_username, settings.smtp_password)
                smtp_tls.send_message(msg)
        else:
            # Plain SMTP (no implicit SSL)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp_plain:
                if settings.smtp_username and settings.smtp_password:
                    smtp_plain.login(settings.smtp_username, settings.smtp_password)
                smtp_plain.send_message(msg)
        logger.info("Password reset email sent to %s", email)
    except Exception:
        # Log exception with masked recipient to avoid leaking PII
        logger.exception(
            "Failed to send password reset email (user_id=%s, recipient=%s)", user_id, masked
        )
