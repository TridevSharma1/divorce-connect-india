import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from ..database import get_db
from ..models import User, Reminder, CaseRequest
from ..security import get_current_user
from ..notifications import manager, send_email

router = APIRouter()

# --- Schemas ---
class ReminderCreate(BaseModel):
    title: str
    message: str
    remind_at: datetime.datetime
    case_request_id: Optional[int] = None

class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    remind_at: Optional[datetime.datetime] = None
    sent: Optional[bool] = None

class ReminderResponse(BaseModel):
    id: int
    user_id: int
    case_request_id: Optional[int]
    title: str
    message: str
    remind_at: datetime.datetime
    sent: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# --- Endpoints ---

@router.post("/", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder_in: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify CaseRequest if provided
    if reminder_in.case_request_id:
        res = await db.execute(select(CaseRequest).where(CaseRequest.id == reminder_in.case_request_id))
        case = res.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail="Case request not found")

    # Create Reminder
    reminder = Reminder(
        user_id=current_user.id,
        case_request_id=reminder_in.case_request_id,
        title=reminder_in.title,
        message=reminder_in.message,
        remind_at=reminder_in.remind_at,
        sent=False
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)

    # Websocket notification for confirmation
    await manager.send_personal_message(f"Reminder '{reminder.title}' scheduled for {reminder.remind_at}.", user_id=current_user.id)

    return reminder


@router.get("/", response_model=List[ReminderResponse])
async def list_reminders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Retrieve reminders for this user
    query = select(Reminder).where(Reminder.user_id == current_user.id).order_by(Reminder.remind_at.asc())
    res = await db.execute(query)
    reminders = res.scalars().all()

    # Auto check due reminders on fetch to guarantee real-time updates for active sessions
    now = datetime.datetime.utcnow()
    any_updated = False
    for reminder in reminders:
        # If the reminder is due but not yet sent, process it immediately!
        # Convert remind_at to naive datetime for comparison if needed
        remind_time = reminder.remind_at
        if remind_time.tzinfo is not None:
            remind_time = remind_time.replace(tzinfo=None)
            
        if not reminder.sent and remind_time <= now:
            reminder.sent = True
            any_updated = True
            
            # 1. WS notification
            await manager.send_personal_message(f"🔔 REMINDER: {reminder.title} - {reminder.message}", user_id=current_user.id)
            
            # 2. Email alert
            if current_user.email:
                email_body = f"""
                <html>
                    <body>
                        <h2>Reminder Alert</h2>
                        <p>This is an automated reminder for your account.</p>
                        <h3><b>{reminder.title}</b></h3>
                        <p>{reminder.message}</p>
                        <br>
                        <p>DivorceConnect India</p>
                    </body>
                </html>
                """
                send_email(to_address=current_user.email, subject=f"Reminder: {reminder.title}", html_body=email_body)
                
    if any_updated:
        await db.commit()

    return reminders


@router.get("/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = res.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.user_id != current_user.id and not current_user.is_staff:
        raise HTTPException(status_code=403, detail="Not authorized to access this reminder")

    return reminder


@router.put("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    reminder_in: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = res.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.user_id != current_user.id and not current_user.is_staff:
        raise HTTPException(status_code=403, detail="Not authorized to update this reminder")

    # Apply updates
    if reminder_in.title is not None:
        reminder.title = reminder_in.title
    if reminder_in.message is not None:
        reminder.message = reminder_in.message
    if reminder_in.remind_at is not None:
        reminder.remind_at = reminder_in.remind_at
    if reminder_in.sent is not None:
        reminder.sent = reminder_in.sent

    await db.commit()
    await db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = res.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.user_id != current_user.id and not current_user.is_staff:
        raise HTTPException(status_code=403, detail="Not authorized to delete this reminder")

    await db.delete(reminder)
    await db.commit()
    return None


@router.post("/check-due", status_code=status.HTTP_200_OK)
async def trigger_due_check(
    db: AsyncSession = Depends(get_db)
):
    """
    Dedicated endpoint to trigger processing of all unsent due reminders globally.
    Ideal for Cron scheduler or task triggers.
    """
    now = datetime.datetime.utcnow()
    query = select(Reminder).where(Reminder.sent == False, Reminder.remind_at <= now)
    res = await db.execute(query)
    due_reminders = res.scalars().all()

    count = 0
    for reminder in due_reminders:
        reminder.sent = True
        count += 1
        
        # Websocket Broadcast / Personal message
        await manager.send_personal_message(f"🔔 REMINDER: {reminder.title} - {reminder.message}", user_id=reminder.user_id)
        
        # Fetch email address for user
        user_res = await db.execute(select(User).where(User.id == reminder.user_id))
        reminder_user = user_res.scalar_one_or_none()
        if reminder_user and reminder_user.email:
            email_body = f"""
            <html>
                <body>
                    <h2>Reminder Alert</h2>
                    <p>This is an automated reminder for your account.</p>
                    <h3><b>{reminder.title}</b></h3>
                    <p>{reminder.message}</p>
                    <br>
                    <p>DivorceConnect India</p>
                </body>
            </html>
            """
            send_email(to_address=reminder_user.email, subject=f"Reminder: {reminder.title}", html_body=email_body)

    if count > 0:
        await db.commit()

    return {"message": f"Processed {count} due reminder(s) successfully"}
