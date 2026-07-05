from __future__ import annotations

import smtplib
from email.message import EmailMessage
from flask import current_app
import logging

from ..db import execute, query_all, query_one, utcnow
from .email_templates import render_email
from .validators import normalize_email

logger = logging.getLogger(__name__)

VALID_EMAIL_STATUSES = {"queued", "sent", "retry_pending", "failed", "suppressed"}
VALID_EMAIL_MODES = {"queue", "console", "smtp"}


def normalize_message_type(value):
    cleaned = str(value or "transactional").strip().lower().replace(" ", "_")
    allowed = {"transactional", "workspace_invite", "password_reset", "sales_lead", "trial", "test", "system"}
    return cleaned if cleaned in allowed else "transactional"


def queue_email(school_id, recipient, subject, body, message_type="transactional", metadata=""):
    recipient = normalize_email(recipient)
    if not recipient:
        raise ValueError("A recipient email is required before queueing an outbox message.")
    subject = str(subject or "").strip()
    body = str(body or "").strip()
    if not subject or not body:
        raise ValueError("Email subject and body are required before queueing an outbox message.")
    try:
        return execute(
            """
            INSERT INTO outbox_messages (
                school_id, recipient, subject, body, status, message_type, metadata,
                attempt_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'queued', ?, ?, 0, ?, ?)
            """,
            (
                school_id,
                recipient,
                subject[:180],
                body[:8000],
                normalize_message_type(message_type),
                str(metadata or "")[:1000],
                utcnow(),
                utcnow(),
            ),
        ).lastrowid
    except Exception as exc:
        logger.error(
            "queue_email_failed",
            extra={"school_id": school_id, "recipient": recipient, "error": str(exc)},
            exc_info=True,
        )
        raise


def queue_template_email(school_id, recipient, template_key, context=None, message_type="transactional", metadata=""):
    subject, body = render_email(template_key, context or {})
    return queue_email(school_id, recipient, subject, body, message_type=message_type, metadata=metadata or template_key)


def queue_test_email(school_id, recipient):
    return queue_template_email(school_id, recipient, "test_email", {}, message_type="test", metadata="manual_test_email")


def email_mode():
    return str(current_app.config.get("EMAIL_DELIVERY_MODE", "queue") or "queue").strip().lower()


def smtp_configured():
    return bool(current_app.config.get("SMTP_HOST") and current_app.config.get("SMTP_FROM"))


def email_delivery_health(school_id=None):
    mode = email_mode()
    counts = {"queued": 0, "retry_pending": 0, "failed": 0, "sent": 0, "suppressed": 0}
    params = ()
    where = ""
    if school_id is not None:
        where = "WHERE school_id = ?"
        params = (school_id,)
    for row in query_all(f"SELECT status, COUNT(*) AS total FROM outbox_messages {where} GROUP BY status", params):
        counts[str(row["status"])] = int(row["total"])
    configured = mode in VALID_EMAIL_MODES and (mode in {"queue", "console"} or smtp_configured())
    production_ready = mode == "smtp" and smtp_configured()
    warnings = []
    if mode == "queue":
        warnings.append("Email delivery is queue-only. Messages are stored but not delivered until console or SMTP mode is configured.")
    elif mode == "console":
        warnings.append("Email delivery is console-only. This is useful for testing but not acceptable for production school leads or invites.")
    elif mode == "smtp" and not smtp_configured():
        warnings.append("SMTP mode is selected, but SMTP_HOST and SMTP_FROM are not fully configured.")
    elif mode not in VALID_EMAIL_MODES:
        warnings.append("EMAIL_DELIVERY_MODE is invalid. Use queue, console, or smtp.")
    if counts.get("failed", 0):
        warnings.append("Failed email messages exist and need review before relying on this workspace for live operations.")
    if counts.get("retry_pending", 0):
        warnings.append("Some email messages are pending retry.")
    return {
        "mode": mode,
        "configured": configured,
        "smtp_configured": smtp_configured(),
        "production_ready": production_ready,
        "counts": counts,
        "warnings": warnings,
    }


def dispatch_queued(limit=25):
    """
    Process queued emails with basic retry accounting.

    Queue mode intentionally does not deliver messages. Console mode prints messages for local QA.
    SMTP mode delivers real transactional email only when SMTP is configured.
    """
    limit = max(1, min(int(limit or 25), 100))
    rows = query_all(
        """
        SELECT * FROM outbox_messages
        WHERE status IN ('queued', 'retry_pending')
        ORDER BY CASE status WHEN 'retry_pending' THEN 0 ELSE 1 END, created_at ASC
        LIMIT ?
        """,
        (limit,),
    )
    sent = 0
    failed = 0
    skipped = 0
    for row in rows:
        ok, reference = deliver_message(row)
        try:
            if ok:
                sent += 1
                execute(
                    """
                    UPDATE outbox_messages
                    SET status = 'sent', provider_reference = ?, sent_at = ?, last_attempt_at = ?, updated_at = ?,
                        attempt_count = attempt_count + 1, last_error = ''
                    WHERE id = ?
                    """,
                    (reference[:240], utcnow(), utcnow(), utcnow(), row["id"]),
                )
            else:
                failed += 1
                current_attempts = int(row["attempt_count"] or 0) + 1 if "attempt_count" in row.keys() else 1
                next_status = "failed" if current_attempts >= 3 else "retry_pending"
                execute(
                    """
                    UPDATE outbox_messages
                    SET status = ?, provider_reference = ?, last_attempt_at = ?, updated_at = ?,
                        attempt_count = attempt_count + 1, last_error = ?
                    WHERE id = ?
                    """,
                    (next_status, reference[:240], utcnow(), utcnow(), reference[:500], row["id"]),
                )
        except Exception as exc:
            skipped += 1
            logger.error("dispatch_queued_update_failed", extra={"message_id": row["id"], "ok": ok, "error": str(exc)}, exc_info=True)
    logger.info("dispatch_queued_completed", extra={"sent": sent, "failed": failed, "skipped": skipped, "total": len(rows)})
    return {"sent": sent, "failed": failed, "skipped": skipped, "total": len(rows)}


def deliver_message(row):
    mode = email_mode()
    if mode == "queue":
        logger.warning("deliver_message_queue_mode", extra={"message_id": row["id"]})
        return False, "EMAIL_DELIVERY_MODE=queue stores messages only; switch to console or smtp to dispatch."
    if mode == "console":
        print(f"[SchoolMind AI email] To: {row['recipient']} | Subject: {row['subject']}\n{row['body']}")
        return True, "console"
    if mode != "smtp":
        logger.warning("deliver_message_invalid_mode", extra={"mode": mode})
        return False, "EMAIL_DELIVERY_MODE must be queue, console, or smtp."
    if not smtp_configured():
        logger.warning("deliver_message_smtp_not_configured")
        return False, "SMTP is not configured"
    try:
        msg = EmailMessage()
        msg["From"] = current_app.config["SMTP_FROM"]
        msg["To"] = row["recipient"]
        msg["Subject"] = row["subject"]
        msg.set_content(row["body"])
        host = current_app.config["SMTP_HOST"]
        port = int(current_app.config.get("SMTP_PORT", 587))
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if current_app.config.get("SMTP_USE_TLS", True):
                smtp.starttls()
            username = current_app.config.get("SMTP_USERNAME")
            password = current_app.config.get("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(msg)
        return True, f"smtp:{host}"
    except smtplib.SMTPAuthenticationError:
        logger.error("deliver_message_auth_failed", extra={"host": current_app.config.get("SMTP_HOST"), "message_id": row["id"]}, exc_info=True)
        return False, f"SMTP authentication failed: {current_app.config.get('SMTP_HOST')}"
    except smtplib.SMTPException as exc:
        logger.error("deliver_message_smtp_error", extra={"host": current_app.config.get("SMTP_HOST"), "message_id": row["id"], "error": str(exc)}, exc_info=True)
        return False, f"SMTP error: {str(exc)[:100]}"
    except TimeoutError:
        logger.error("deliver_message_timeout", extra={"host": current_app.config.get("SMTP_HOST"), "message_id": row["id"]}, exc_info=True)
        return False, f"SMTP timeout connecting to {current_app.config.get('SMTP_HOST')}"
    except Exception as exc:
        logger.error("deliver_message_unexpected_error", extra={"message_id": row["id"], "error": str(exc)}, exc_info=True)
        return False, f"Unexpected error: {str(exc)[:100]}"


def latest_outbox_messages(school_id, limit=100):
    return query_all(
        "SELECT * FROM outbox_messages WHERE school_id = ? ORDER BY created_at DESC LIMIT ?",
        (school_id, max(1, min(int(limit or 100), 200))),
    )


def latest_global_outbox_messages(limit=100):
    return query_all(
        "SELECT * FROM outbox_messages WHERE school_id IS NULL ORDER BY created_at DESC LIMIT ?",
        (max(1, min(int(limit or 100), 200)),),
    )
