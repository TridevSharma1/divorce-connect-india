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
    from .tasks import send_email_task
    import asyncio
    
    async def safe_kiq():
        try:
            await send_email_task.kiq(to_address, subject, html_body, purpose)
        except Exception as e:
            logger.error(f"Taskiq SendTaskError in background email task: {e}")
            
    logger.info(f"Scheduling background task to send {purpose} email to {to_address}")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(safe_kiq())
    except RuntimeError:
        asyncio.run(safe_kiq())

async def create_and_broadcast_notification(
    db,
    user_id: int,
    title: str,
    message: str,
    url: str = None
):
    from .models import Notification
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        url=url,
        is_read=False
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    
    # Broadcast in real-time via WebSocket
    ws_msg = f"{title}: {message}"
    await manager.send_personal_message(ws_msg, user_id=user_id)
    return notification


