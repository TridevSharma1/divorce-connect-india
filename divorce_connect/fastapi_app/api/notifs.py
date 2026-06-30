from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from ..database import get_db
from ..models import User, Notification
from ..schemas import NotificationCreate, NotificationResponse
from ..security import get_current_user

router = APIRouter()

@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all unread notifications for the authenticated user.
    """
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .order_by(Notification.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification_in: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new notification for the authenticated user.
    """
    notification = Notification(
        user_id=current_user.id,
        title=notification_in.title,
        message=notification_in.message,
        url=notification_in.url,
        is_read=False
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Custom action to mark all unread notifications as read.
    """
    # Use an update statement for efficiency
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    
    # SQLAlchemy's result.rowcount gives the number of rows updated
    return {"message": f"Successfully marked {result.rowcount} notification(s) as read."}

@router.patch("/{notification_id}", response_model=NotificationResponse)
@router.patch("/{notification_id}/", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Notification)
        .where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification
