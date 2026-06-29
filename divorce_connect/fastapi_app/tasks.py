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
