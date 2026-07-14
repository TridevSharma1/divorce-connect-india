import asyncio
import logging
import os
from .broker import broker


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: send via Resend HTTP API (works on Render free tier)
# Sign up free at https://resend.com — 100 emails/day, no card needed.
# Set RESEND_API_KEY in Render's Environment tab.
# ─────────────────────────────────────────────────────────────────────────────
async def _send_via_resend(
    api_key: str,
    from_address: str,
    to_address: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send email through Resend's HTTPS API (bypasses Render SMTP block)."""
    import httpx

    payload = {
        "from": from_address,
        "to": [to_address],
        "subject": subject,
        "html": html_body,
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if resp.status_code in (200, 201):
            logger.info(f"Resend: email sent successfully to {to_address} (id={resp.json().get('id')})")
            return True
        else:
            logger.error(f"Resend: API error {resp.status_code} — {resp.text}")
            return False
    except Exception as exc:
        logger.error(f"Resend: request failed — {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Helper: send via SMTP (works locally / on paid Render plans)
# ─────────────────────────────────────────────────────────────────────────────
def _send_via_smtp(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    smtp_use_tls: bool,
    from_address: str,
    to_address: str,
    subject: str,
    html_body: str,
) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_address
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(
            f"SMTP: sending to {to_address} via {smtp_host}:{smtp_port} (user={smtp_user})"
        )
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if smtp_use_tls:
                server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(from_address, [to_address], msg.as_string())
        server.quit()
        logger.info("SMTP: email sent successfully.")
        return True
    except Exception as exc:
        logger.error(f"SMTP: sending failed to {to_address} — {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Background tasks
# ─────────────────────────────────────────────────────────────────────────────

@broker.task
async def send_welcome_email_task(email: str, first_name: str) -> str:
    """Example background task sent to NATS via Taskiq."""
    logger.info(f"Starting welcome email task for {email}")
    await asyncio.sleep(2)
    logger.info(f"Welcome email sent successfully to {first_name} ({email})")
    return "SUCCESS"


@broker.task
async def process_case_document_task(document_id: int) -> dict:
    """Example background task for heavy processing."""
    logger.info(f"Processing document {document_id}")
    await asyncio.sleep(5)
    logger.info(f"Document {document_id} processed")
    return {"status": "completed", "document_id": document_id}


@broker.task
async def send_email_task(
    to_address: str,
    subject: str,
    html_body: str,
    purpose: str = "operations",
) -> bool:
    """
    Send an email using Resend HTTP API (primary) or SMTP (fallback).

    Priority:
      1. If RESEND_API_KEY is set → use Resend HTTPS (works on Render free tier).
      2. Otherwise → fall back to SMTP credentials for the given purpose.

    Render free tier BLOCKS all outbound SMTP (ports 25, 465, 587).
    Set RESEND_API_KEY in Render → Environment to enable email delivery.
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()

    # Resolve sender & SMTP creds for the given purpose
    if purpose == "auth":
        smtp_host = os.getenv("SMTP_AUTH_HOST") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_AUTH_PORT") or os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_AUTH_USER") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_AUTH_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = (
            os.getenv("SMTP_AUTH_USE_TLS") or os.getenv("SMTP_USE_TLS", "True")
        ).lower() in ("true", "1")
    else:
        smtp_host = os.getenv("SMTP_OPERATIONS_HOST") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_OPERATIONS_PORT") or os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_OPERATIONS_USER") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_OPERATIONS_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = (
            os.getenv("SMTP_OPERATIONS_USE_TLS") or os.getenv("SMTP_USE_TLS", "True")
        ).lower() in ("true", "1")

    # The "from" address shown to recipients
    sender_name = "DivorceConnect India"
    if resend_api_key:
        # Resend requires the domain to be verified on their dashboard.
        # Use onboarding@resend.dev for testing, or your verified domain.
        resend_from = os.getenv(
            "RESEND_FROM_ADDRESS",
            f"{sender_name} <onboarding@resend.dev>",
        )
        logger.info(f"Using Resend API to send email to {to_address}")
        return await _send_via_resend(
            api_key=resend_api_key,
            from_address=resend_from,
            to_address=to_address,
            subject=subject,
            html_body=html_body,
        )

    # ── SMTP fallback ──────────────────────────────────────────────────────
    if not smtp_user or not smtp_password:
        logger.error(
            f"Email not sent: no RESEND_API_KEY and no SMTP credentials "
            f"configured for purpose='{purpose}'. "
            f"Add RESEND_API_KEY to Render → Environment."
        )
        return False

    from_address = f"{sender_name} <{smtp_user}>"
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _send_via_smtp,
        smtp_host, smtp_port, smtp_user, smtp_password,
        smtp_use_tls, from_address, to_address, subject, html_body,
    )
