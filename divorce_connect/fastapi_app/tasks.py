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
        smtp_port = int(os.getenv("SMTP_AUTH_PORT") or os.getenv("SMTP_PORT", "465"))
        smtp_user = os.getenv("SMTP_AUTH_USER") or os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_AUTH_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = (os.getenv("SMTP_AUTH_USE_TLS") or os.getenv("SMTP_USE_TLS", "True")).lower() in ("true", "1")
    else:
        smtp_host = os.getenv("SMTP_OPERATIONS_HOST") or os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_OPERATIONS_PORT") or os.getenv("SMTP_PORT", "465"))
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
        logger.info(f"Taskiq: Sending email via {purpose} SMTP to {to_address} (Host: {smtp_host}:{smtp_port}, User: {smtp_user})")
        # Port 465 uses SSL from the start (SMTP_SSL); port 587 uses STARTTLS.
        # Render free tier blocks 587, so we default to 465 with SMTP_SSL.
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
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

