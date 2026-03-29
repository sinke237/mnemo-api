"""Simple email enqueue/send scaffolding.

This module provides a minimal placeholder for enqueuing outbound emails.
Production deployments should replace this with an async queue or external
email provider integration.
"""

import logging
import smtplib
from email.message import EmailMessage
from importlib import resources

from mnemo.core.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, reset_url: str, *, user_id: str | None = None) -> None:
    """Enqueue/send a password reset email.

    This is a placeholder implementation that logs the action. In production
    this should enqueue a job or call an external email service.
    """
    # IMPORTANT: do not log the raw token or include it in telemetry.
    settings = get_settings()
    logger.info("Password reset requested for %s (user_id=%s)", email, user_id)
    # Do NOT log the raw reset URL or token. Log only that a link was generated
    # and the destination domain for telemetry.
    try:
        settings = get_settings()
        logger.debug("Reset link domain: %s", settings.frontend_base_url)
    except Exception:
        logger.debug("Reset link generated")

    if not settings.smtp_enabled:
        logger.info("SMTP disabled; skipping actual send for %s", email)
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
        if settings.smtp_use_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(msg)
        else:
            # Use SMTP_SSL only if a TLS connection is desired at the socket layer.
            try:
                with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                    if settings.smtp_username and settings.smtp_password:
                        smtp.login(settings.smtp_username, settings.smtp_password)
                    smtp.send_message(msg)
            except smtplib.SMTPException:
                # Fall back to plain SMTP if SSL connection refused
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                    if settings.smtp_username and settings.smtp_password:
                        smtp.login(settings.smtp_username, settings.smtp_password)
                    smtp.send_message(msg)
        logger.info("Password reset email sent to %s", email)
    except Exception:
        logger.exception("Failed to send password reset email to %s", email)
