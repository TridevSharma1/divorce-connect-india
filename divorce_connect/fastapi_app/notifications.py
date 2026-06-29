import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map user_id to list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user_id={user_id}. Active connections: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user_id={user_id}")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending WebSocket message to user_id={user_id}: {e}")

    async def broadcast(self, message: str):
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting WebSocket message to user_id={user_id}: {e}")

# Global Connection Manager Instance
manager = ConnectionManager()

def send_email(to_address: str, subject: str, html_body: str, purpose: str = "operations"):
    if purpose == "auth":
        smtp_host = os.getenv("SMTP_AUTH_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_AUTH_PORT", "587"))
        smtp_user = os.getenv("SMTP_AUTH_USER", "")
        smtp_password = os.getenv("SMTP_AUTH_PASSWORD", "")
        smtp_use_tls = os.getenv("SMTP_AUTH_USE_TLS", "True").lower() in ("true", "1")
    else:
        smtp_host = os.getenv("SMTP_OPERATIONS_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_OPERATIONS_PORT", "587"))
        smtp_user = os.getenv("SMTP_OPERATIONS_USER", "")
        smtp_password = os.getenv("SMTP_OPERATIONS_PASSWORD", "")
        smtp_use_tls = os.getenv("SMTP_OPERATIONS_USE_TLS", "True").lower() in ("true", "1")

    # Fallback to general SMTP settings if specific settings are empty
    if not smtp_user or not smtp_password:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        smtp_use_tls = os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"DivorceConnect India <{smtp_user or 'noreply@divorceconnect.in'}>"
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        logger.info(f"Sending email via {purpose} SMTP to {to_address} (Host: {smtp_host}, User: {smtp_user})")
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        if smtp_use_tls:
            server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(msg["From"], [to_address], msg.as_string())
        server.quit()
        logger.info("Email sent successfully.")
    except Exception as e:
        logger.warning(f"SMTP sending failed ({e}). Logging email to console instead.")
        logger.info(f"\n--- [DEV EMAIL LOG] ---\nTo: {to_address}\nSubject: {subject}\nBody:\n{html_body}\n-----------------------\n")

