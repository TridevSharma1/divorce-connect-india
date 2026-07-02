import asyncio
import logging
from .broker import broker


logger = logging.getLogger(__name__)

@broker.task
async def send_welcome_email_task(email: str, first_name: str) -> str:
    """
    Example background task sent to NATS via Taskiq.
    """
    logger.info(f"Starting welcome email task for {email}")
    # Simulate email sending delay
    await asyncio.sleep(2)
    logger.info(f"Welcome email sent successfully to {first_name} ({email})")
    return "SUCCESS"

@broker.task
async def process_case_document_task(document_id: int) -> dict:
    """
    Example background task for heavy processing.
    """
    logger.info(f"Processing document {document_id}")
    # Simulate processing delay
    await asyncio.sleep(5)
    logger.info(f"Document {document_id} processed")
    return {"status": "completed", "document_id": document_id}

@broker.task
async def send_email_task(to_address: str, subject: str, html_body: str, purpose: str = "operations") -> bool:
    """
    Taskiq background task to send an email using smtplib.
    """
    import smtplib
    import os
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    if purpose == "auth":
        smtp_host = os.getenv("SMTP_AUTH_HOST") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_AUTH_PORT") or os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_AUTH_USER") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_AUTH_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = (os.getenv("SMTP_AUTH_USE_TLS") or os.getenv("SMTP_USE_TLS", "True")).lower() in ("true", "1")
    else:
        smtp_host = os.getenv("SMTP_OPERATIONS_HOST") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_OPERATIONS_PORT") or os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_OPERATIONS_USER") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_OPERATIONS_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = (os.getenv("SMTP_OPERATIONS_USE_TLS") or os.getenv("SMTP_USE_TLS", "True")).lower() in ("true", "1")
        
    if not smtp_user or not smtp_password:
        logger.error(f"Taskiq: SMTP credentials are not configured for {purpose}. Cannot send email.")
        return False
        
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"DivorceConnect India <{smtp_user}>"
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html"))
    
    try:
        logger.info(f"Taskiq: Sending email via {purpose} SMTP to {to_address} (Host: {smtp_host}, User: {smtp_user})")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        if smtp_use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], [to_address], msg.as_string())
        server.quit()
        logger.info("Taskiq: Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Taskiq: SMTP sending failed to {to_address} ({e})")
        return False

@broker.task
async def task_purge_deleted_accounts():
    """
    Background task to purge accounts that have been deactivated for 14+ days.
    """
    logger.info("Starting purge of deleted accounts...")
    from .database import AsyncSessionLocal
    from .models import User, DeleteAccountToken
    from sqlalchemy import select
    import datetime
    
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=14)
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(DeleteAccountToken).where(
                DeleteAccountToken.is_used == True,
                DeleteAccountToken.created_at <= cutoff
            )
        )
        tokens = res.scalars().all()
        count = 0
        for token in tokens:
            user_res = await db.execute(select(User).where(User.id == token.user_id))
            user = user_res.scalars().first()
            if user and not user.is_active:
                await db.delete(user) # Cascade deletes other models ideally
                count += 1
        await db.commit()
    logger.info(f"Purged {count} accounts.")
    return count

@broker.task
async def task_send_bug_report_email(issue_text: str, reporter_email: str):
    """
    Email superusers about a new bug report.
    """
    subject = f"New Bug Report from {reporter_email}"
    html_body = f"<p>A new bug report was submitted:</p><p>{issue_text}</p>"
    
    # Ideally fetch all superusers, but hardcoding for example or fetching from env
    import os
    admin_email = os.getenv("ADMIN_EMAIL", "admin@divorceconnect.in")
    
    await send_email_task.kiq(
        to_address=admin_email,
        subject=subject,
        html_body=html_body,
        purpose="operations"
    )
    return True
