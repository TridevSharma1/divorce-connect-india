from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict

from ..database import get_db, AsyncSessionLocal
from ..models import User, ChatMessage, CaseRequest
from ..security import get_current_user

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps case_id -> list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, case_id: int):
        await websocket.accept()
        if case_id not in self.active_connections:
            self.active_connections[case_id] = []
        self.active_connections[case_id].append(websocket)

    def disconnect(self, websocket: WebSocket, case_id: int):
        if case_id in self.active_connections:
            self.active_connections[case_id].remove(websocket)
            if not self.active_connections[case_id]:
                del self.active_connections[case_id]

    async def broadcast(self, message: dict, case_id: int):
        if case_id in self.active_connections:
            for connection in self.active_connections[case_id]:
                await connection.send_json(message)

manager = ConnectionManager()

@router.get("/{case_id}/history")
async def get_chat_history(case_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Check if user is part of the case
    res = await db.execute(select(CaseRequest).where(CaseRequest.id == case_id))
    case = res.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    if user.role == "client":
        from ..models import ClientProfile
        cp_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user.id))
        cp = cp_res.scalars().first()
        if not cp or case.client_id != cp.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif user.role == "lawyer":
        from ..models import LawyerProfile
        lp_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user.id))
        lp = lp_res.scalars().first()
        if not lp or case.lawyer_id != lp.id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
    msgs_res = await db.execute(select(ChatMessage).where(ChatMessage.case_request_id == case_id).order_by(ChatMessage.created_at.asc()))
    msgs = msgs_res.scalars().all()
    
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "message": m.message,
            "file_url": m.file_url,
            "created_at": m.created_at
        } for m in msgs
    ]

@router.websocket("/ws/{case_id}")
async def websocket_endpoint(websocket: WebSocket, case_id: int):
    await manager.connect(websocket, case_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Expecting {"sender_id": int, "message": str, "file_url": str}
            sender_id = data.get("sender_id")
            message = data.get("message")
            file_url = data.get("file_url")
            
            async with AsyncSessionLocal() as db:
                new_msg = ChatMessage(
                    case_request_id=case_id,
                    sender_id=sender_id,
                    message=message,
                    file_url=file_url
                )
                db.add(new_msg)
                await db.commit()
                await db.refresh(new_msg)
                
            await manager.broadcast({
                "id": new_msg.id,
                "sender_id": new_msg.sender_id,
                "message": new_msg.message,
                "file_url": new_msg.file_url,
                "created_at": new_msg.created_at.isoformat()
            }, case_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, case_id)
