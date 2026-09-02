"""
Superuser API Router — /api/superuser
Full CRUD + bulk actions for all 14 platform models.
Protected by check_superuser dependency (is_superuser=True required).
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import (
    AdminPanelProfile,
    AdminPanelProfileUpdateRequest,
    CaseDocument,
    CaseDocumentVerification,
    CaseMessage,
    CaseRequest,
    ClientProfile,
    DeleteAccountToken,
    GetInTouch,
    LawyerProfile,
    LawyerProfileUpdateRequest,
    LawyerRating,
    LawyerVerificationRequest,
    Notification,
    OTPCode,
    Payment,
    Reminder,
    SystemIssue,
    TrustReport,
    User,
    WithdrawRequest,
)
from ..notifications import create_and_broadcast_notification
from ..security import get_current_user

router = APIRouter()


# ─── Superuser Guard ──────────────────────────────────────────────────────────

async def check_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Allow access only to users with is_superuser=True."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser credentials required",
        )
    return current_user


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _paginate(query, page: int, page_size: int = 25):
    """Apply LIMIT/OFFSET pagination to a SQLAlchemy query."""
    offset = (page - 1) * page_size
    return query.offset(offset).limit(page_size)


def _serialize(obj) -> Dict[str, Any]:
    """
    Safe generic row → dict serialiser.
    Only reads __table__.columns (no relationship traversal).
    Converts dates/decimals to JSON-safe types.
    """
    result: Dict[str, Any] = {}
    import decimal
    for col in obj.__table__.columns:
        try:
            val = getattr(obj, col.name)
        except Exception:
            val = None
        if isinstance(val, (datetime.datetime, datetime.date)):
            val = val.isoformat()
        elif isinstance(val, decimal.Decimal):
            val = float(val)
        result[col.name] = val
    return result


async def _inject_custom_fields(model_path: str, record, d: Dict[str, Any], db: AsyncSession):
    if model_path == "case-document-verifications" and getattr(record, "verified_by_id", None):
        admin_profile_res = await db.execute(
            select(AdminPanelProfile.custom_id, AdminPanelProfile.id)
            .where(AdminPanelProfile.user_id == record.verified_by_id)
        )
        ap = admin_profile_res.one_or_none()
        if ap:
            d["verified_by_custom_id"] = ap[0] or f"ad:{ap[1]:05d}"
        else:
            d["verified_by_custom_id"] = None
    elif model_path == "case-document-verifications":
        d["verified_by_custom_id"] = None
    elif model_path == "system-issues":
        if not d.get("ticket_id") and getattr(record, "id", None):
            d["ticket_id"] = f"ti:{record.id:05d}"
    elif model_path == "payments":
        d["invoice_number"] = getattr(record, "invoice_number", None)
    return d


def _delete_system_issue_file(record):
    if hasattr(record, "evidence_file") and record.evidence_file:
        from pathlib import Path
        file_path = Path("media") / record.evidence_file
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass



# ─── Pydantic Payloads ────────────────────────────────────────────────────────

class IdsPayload(BaseModel):
    ids: List[int]


class UserUpdatePayload(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_staff: Optional[bool] = None
    is_superuser: Optional[bool] = None
    razorpay_customer_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNTS APP
# ═══════════════════════════════════════════════════════════════════════════════

# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(User.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/users/{user_id}")
async def get_user(user_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize(user)


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdatePayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(user, field, val)
    user.updated_at = datetime.datetime.utcnow()
    await db.commit()
    return _serialize(user)


# ─── User cascade-delete helper ──────────────────────────────────────────────

async def _cascade_delete_user(user_id: int, db: AsyncSession) -> None:
    """
    Deletes a User and ALL related data in the correct FK dependency order so
    no constraint is ever violated. Called by both the single-record endpoint
    and the bulk-delete endpoint when model='users'.

    Order:
      CaseDocVerifications → CaseDocuments → CaseMessages → Payments → Reminders
      → CaseRequests → LawyerRatings → TrustReports → LawyerVerificationRequests
      → LawyerProfileUpdateRequests → LawyerProfile → AdminPanelProfileUpdateRequests
      → AdminPanelProfile → ClientProfile → loose FKs (null-out / delete)
      → DeleteAccountTokens → Reminders → OTPCodes → Notifications → User
    """
    # ── 1. Resolve profile IDs ────────────────────────────────────────────────
    client_res = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user_id))
    client     = client_res.scalar_one_or_none()
    lawyer_res = await db.execute(select(LawyerProfile).where(LawyerProfile.user_id == user_id))
    lawyer     = lawyer_res.scalar_one_or_none()
    admin_res  = await db.execute(select(AdminPanelProfile).where(AdminPanelProfile.user_id == user_id))
    admin_prof = admin_res.scalar_one_or_none()

    client_id = client.id if client else None
    lawyer_id = lawyer.id if lawyer else None

    # ── 2. Collect all CaseRequest IDs linked to this user ───────────────────
    case_ids: list[int] = []
    if client_id:
        cr = await db.execute(select(CaseRequest.id).where(CaseRequest.client_id == client_id))
        case_ids += list(cr.scalars())
    if lawyer_id:
        cr = await db.execute(select(CaseRequest.id).where(CaseRequest.lawyer_id == lawyer_id))
        case_ids += list(cr.scalars())
    case_ids = list(set(case_ids))

    # ── 3. Delete CaseRequest subtree (deepest children first) ───────────────
    if case_ids:
        doc_res = await db.execute(
            select(CaseDocument.id).where(CaseDocument.case_request_id.in_(case_ids))
        )
        doc_ids = list(doc_res.scalars())

        if doc_ids:
            await db.execute(
                CaseDocumentVerification.__table__.delete().where(
                    CaseDocumentVerification.document_id.in_(doc_ids)
                )
            )
        await db.execute(
            CaseDocument.__table__.delete().where(CaseDocument.case_request_id.in_(case_ids))
        )
        await db.execute(
            CaseMessage.__table__.delete().where(CaseMessage.case_id.in_(case_ids))
        )
        await db.execute(
            Payment.__table__.delete().where(Payment.case_request_id.in_(case_ids))
        )
        await db.execute(
            Reminder.__table__.delete().where(Reminder.case_request_id.in_(case_ids))
        )
        await db.execute(
            CaseRequest.__table__.delete().where(CaseRequest.id.in_(case_ids))
        )

    # ── 4. LawyerProfile children ─────────────────────────────────────────────
    if lawyer_id:
        await db.execute(
            LawyerRating.__table__.delete().where(LawyerRating.lawyer_id == lawyer_id)
        )
        await db.execute(
            TrustReport.__table__.delete().where(TrustReport.reported_lawyer_id == lawyer_id)
        )
        await db.execute(
            LawyerVerificationRequest.__table__.delete().where(
                LawyerVerificationRequest.lawyer_id == lawyer_id
            )
        )
        await db.execute(
            LawyerProfileUpdateRequest.__table__.delete().where(
                LawyerProfileUpdateRequest.lawyer_id == lawyer_id
            )
        )
        await db.execute(
            LawyerProfile.__table__.delete().where(LawyerProfile.id == lawyer_id)
        )

    # ── 5. AdminPanelProfile children ────────────────────────────────────────
    if admin_prof:
        await db.execute(
            AdminPanelProfileUpdateRequest.__table__.delete().where(
                AdminPanelProfileUpdateRequest.admin_profile_id == admin_prof.id
            )
        )
        await db.execute(
            AdminPanelProfile.__table__.delete().where(AdminPanelProfile.id == admin_prof.id)
        )

    # ── 6. ClientProfile children ─────────────────────────────────────────────
    if client_id:
        await db.execute(
            LawyerRating.__table__.delete().where(LawyerRating.client_id == client_id)
        )
        await db.execute(
            TrustReport.__table__.delete().where(TrustReport.reported_client_id == client_id)
        )
        await db.execute(
            ClientProfile.__table__.delete().where(ClientProfile.id == client_id)
        )

    # ── 7. Loose user-level FK references ─────────────────────────────────────
    # reporter_id is NOT NULL → delete those reports
    await db.execute(
        TrustReport.__table__.delete().where(TrustReport.reporter_id == user_id)
    )
    # nullable reviewer/sender references → null out to preserve audit trail
    await db.execute(
        TrustReport.__table__.update()
        .where(TrustReport.reviewed_by_id == user_id)
        .values(reviewed_by_id=None)
    )
    await db.execute(
        CaseDocumentVerification.__table__.update()
        .where(CaseDocumentVerification.verified_by_id == user_id)
        .values(verified_by_id=None)
    )
    await db.execute(
        CaseMessage.__table__.update()
        .where(CaseMessage.sender_user_id == user_id)
        .values(sender_user_id=None)
    )
    await db.execute(
        LawyerVerificationRequest.__table__.update()
        .where(LawyerVerificationRequest.reviewed_by_id == user_id)
        .values(reviewed_by_id=None)
    )
    await db.execute(
        AdminPanelProfileUpdateRequest.__table__.update()
        .where(AdminPanelProfileUpdateRequest.reviewed_by_id == user_id)
        .values(reviewed_by_id=None)
    )

    # ── 8. Direct user-level children ────────────────────────────────────────
    await db.execute(
        DeleteAccountToken.__table__.delete().where(DeleteAccountToken.user_id == user_id)
    )
    await db.execute(
        Reminder.__table__.delete().where(Reminder.user_id == user_id)
    )
    await db.execute(OTPCode.__table__.delete().where(OTPCode.user_id == user_id))
    await db.execute(Notification.__table__.delete().where(Notification.user_id == user_id))

    # ── 9. Delete the User row itself ─────────────────────────────────────────
    await db.execute(User.__table__.delete().where(User.id == user_id))


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    """Single-user cascade delete — delegates to _cascade_delete_user helper."""
    if not await db.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await _cascade_delete_user(user_id, db)
    await db.commit()


# ── Delete Account Tokens ─────────────────────────────────────────────────────

@router.get("/delete-tokens")
async def list_delete_tokens(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(DeleteAccountToken)
    if search:
        q = q.where(DeleteAccountToken.token.ilike(f"%{search}%"))
    q = q.order_by(DeleteAccountToken.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.delete("/delete-tokens/{token_id}", status_code=204)
async def delete_token(token_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError, DBAPIError
    token = await db.get(DeleteAccountToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    try:
        await db.delete(token)
        await db.commit()
    except (IntegrityError, DBAPIError):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete: FK constraint violation.")


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
async def list_notifications(
    search: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(Notification)
    if search:
        q = q.where(
            or_(Notification.title.ilike(f"%{search}%"), Notification.message.ilike(f"%{search}%"))
        )
    if user_id:
        q = q.where(Notification.user_id == user_id)
    q = q.order_by(Notification.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.delete("/notifications/{notif_id}", status_code=204)
async def delete_notification(notif_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError, DBAPIError
    n = await db.get(Notification, notif_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    try:
        await db.delete(n)
        await db.commit()
    except (IntegrityError, DBAPIError):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete: FK constraint violation.")


# ── OTP Codes ─────────────────────────────────────────────────────────────────

@router.get("/otp-codes")
async def list_otp_codes(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(OTPCode)
    if search:
        q = q.where(OTPCode.code.ilike(f"%{search}%"))
    q = q.order_by(OTPCode.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    otp_records = rows.scalars().all()

    user_ids = [otp.user_id for otp in otp_records if otp.user_id]
    user_map = {}
    if user_ids:
        users_res = await db.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
        user_map = {uid: email for uid, email in users_res.all()}

    results = []
    for otp in otp_records:
        item = _serialize(otp)
        item["email"] = user_map.get(otp.user_id)
        results.append(item)

    return {"total": total, "page": page, "results": results}


@router.delete("/otp-codes/{otp_id}", status_code=204)
async def delete_otp(otp_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError, DBAPIError
    otp = await db.get(OTPCode, otp_id)
    if not otp:
        raise HTTPException(status_code=404, detail="OTP not found")
    try:
        await db.delete(otp)
        await db.commit()
    except (IntegrityError, DBAPIError):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Cannot delete: FK constraint violation.")


# ═══════════════════════════════════════════════════════════════════════════════
# ADMINPANEL APP
# ═══════════════════════════════════════════════════════════════════════════════

# ── Admin Panel Profiles ──────────────────────────────────────────────────────

@router.get("/admin-profiles")
async def list_admin_profiles(
    search: Optional[str] = Query(None),
    is_verified: Optional[bool] = Query(None),
    is_deleted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(AdminPanelProfile)
    if search:
        q = q.where(
            or_(
                AdminPanelProfile.full_name.ilike(f"%{search}%"),
                AdminPanelProfile.mobile_number.ilike(f"%{search}%"),
            )
        )
    if is_verified is not None:
        q = q.where(AdminPanelProfile.is_verified_by_superuser == is_verified)
    if is_deleted is not None:
        q = q.where(AdminPanelProfile.is_deleted == is_deleted)
    q = q.order_by(AdminPanelProfile.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/admin-profiles/{profile_id}")
async def get_admin_profile(profile_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    p = await db.get(AdminPanelProfile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Admin profile not found")
    return _serialize(p)


# ── Admin Profile Update Requests ─────────────────────────────────────────────

@router.get("/admin-update-requests")
async def list_admin_update_requests(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(AdminPanelProfileUpdateRequest)
    if search:
        q = q.where(AdminPanelProfileUpdateRequest.full_name.ilike(f"%{search}%"))
    if status_filter:
        q = q.where(AdminPanelProfileUpdateRequest.status == status_filter.upper())
    q = q.order_by(AdminPanelProfileUpdateRequest.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(_paginate(q, page))
    requests = result.scalars().all()

    admin_ids = [r.admin_profile_id for r in requests]
    admin_profiles_res = await db.execute(
        select(AdminPanelProfile.id, AdminPanelProfile.custom_id).where(AdminPanelProfile.id.in_(admin_ids))
    )
    admin_map = {ap[0]: ap[1] for ap in admin_profiles_res.all()}

    results = []
    for req in requests:
        item = _serialize(req)
        custom_id = admin_map.get(req.admin_profile_id)
        item['custom_id'] = custom_id or (f"ad:{req.admin_profile_id:05d}" if req.admin_profile_id else None)
        results.append(item)

    return {"total": total, "page": page, "results": results}


# ── Lawyer Verification Requests ──────────────────────────────────────────────

@router.get("/lawyer-verification-requests")
async def list_lawyer_verification_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(LawyerVerificationRequest)
    if status_filter:
        q = q.where(LawyerVerificationRequest.status == status_filter.lower())
    q = q.order_by(LawyerVerificationRequest.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


# ── Trust Reports ─────────────────────────────────────────────────────────────

@router.get("/trust-reports")
async def list_trust_reports(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(TrustReport)
    if search:
        q = q.where(
            or_(TrustReport.reason.ilike(f"%{search}%"), TrustReport.description.ilike(f"%{search}%"))
        )
    if status_filter:
        q = q.where(TrustReport.status == status_filter.upper())
    q = q.order_by(TrustReport.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/trust-reports/{report_id}")
async def get_trust_report(report_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    r = await db.get(TrustReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Trust report not found")
    return _serialize(r)


# ── Groups (static — single "Staff" group) ────────────────────────────────────

@router.get("/groups")
async def list_groups(_su: User = Depends(check_superuser)):
    return {"total": 1, "page": 1, "results": [{"id": 1, "name": "Staff"}]}


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENTS APP
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/client-profiles")
async def list_client_profiles(
    search: Optional[str] = Query(None),
    is_deleted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(ClientProfile)
    if search:
        q = q.where(
            or_(
                ClientProfile.first_name.ilike(f"%{search}%"),
                ClientProfile.last_name.ilike(f"%{search}%"),
                ClientProfile.mobile_number.ilike(f"%{search}%"),
                ClientProfile.custom_id.ilike(f"%{search}%"),
            )
        )
    if is_deleted is not None:
        q = q.where(ClientProfile.is_deleted == is_deleted)
    q = q.order_by(ClientProfile.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/client-profiles/{profile_id}")
async def get_client_profile(profile_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    p = await db.get(ClientProfile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Client profile not found")
    return _serialize(p)


# ═══════════════════════════════════════════════════════════════════════════════
# LAWYERS APP
# ═══════════════════════════════════════════════════════════════════════════════

# ── Lawyer Profiles ───────────────────────────────────────────────────────────

@router.get("/lawyer-profiles")
async def list_lawyer_profiles(
    search: Optional[str] = Query(None),
    verified: Optional[bool] = Query(None),
    is_deleted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(LawyerProfile)
    if search:
        q = q.where(
            or_(
                LawyerProfile.full_name.ilike(f"%{search}%"),
                LawyerProfile.bar_registration_number.ilike(f"%{search}%"),
                LawyerProfile.office_city.ilike(f"%{search}%"),
                LawyerProfile.custom_id.ilike(f"%{search}%"),
            )
        )
    if verified is not None:
        q = q.where(LawyerProfile.verified == verified)
    if is_deleted is not None:
        q = q.where(LawyerProfile.is_deleted == is_deleted)
    q = q.order_by(LawyerProfile.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/lawyer-profiles/{profile_id}")
async def get_lawyer_profile(profile_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    p = await db.get(LawyerProfile, profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Lawyer profile not found")
    return _serialize(p)


# ── Case Document Verifications ───────────────────────────────────────────────

@router.get("/case-document-verifications")
async def list_case_document_verifications(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(CaseDocumentVerification)
    if status_filter:
        q = q.where(CaseDocumentVerification.status == status_filter.upper())
    q = q.order_by(CaseDocumentVerification.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    verifications = rows.scalars().all()
    
    # Pre-fetch all AdminPanelProfiles to map user_id -> custom_id
    admin_profiles_res = await db.execute(select(AdminPanelProfile.user_id, AdminPanelProfile.id, AdminPanelProfile.custom_id))
    admin_map = {}
    for user_id, profile_id, custom_id in admin_profiles_res.all():
        admin_map[user_id] = custom_id or f"ad:{profile_id:05d}"
        
    serialized_results = []
    for r in verifications:
        d = _serialize(r)
        d["verified_by_custom_id"] = admin_map.get(r.verified_by_id) if r.verified_by_id else None
        serialized_results.append(d)
        
    return {"total": total, "page": page, "results": serialized_results}


# ── Case Documents ────────────────────────────────────────────────────────────

@router.get("/case-documents")
async def list_case_documents(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(CaseDocument)
    if search:
        q = q.where(CaseDocument.document_type.ilike(f"%{search}%"))
    q = q.order_by(CaseDocument.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


# ── Case Requests ─────────────────────────────────────────────────────────────

@router.get("/case-requests")
async def list_case_requests(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(CaseRequest)
    if search:
        q = q.where(
            or_(
                CaseRequest.custom_id.ilike(f"%{search}%"),
                CaseRequest.message.ilike(f"%{search}%"),
            )
        )
    if status_filter:
        q = q.where(CaseRequest.status == status_filter.upper())
    q = q.order_by(CaseRequest.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/case-requests/{case_id}")
async def get_case_request(case_id: int, _su: User = Depends(check_superuser), db: AsyncSession = Depends(get_db)):
    c = await db.get(CaseRequest, case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case request not found")
    return _serialize(c)


# ── Case Messages ─────────────────────────────────────────────────────────────

@router.get("/case-messages")
async def list_case_messages(
    case_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(CaseMessage)
    if case_id:
        q = q.where(CaseMessage.case_id == case_id)
    q = q.order_by(CaseMessage.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


# ── Lawyer Ratings ────────────────────────────────────────────────────────────

@router.get("/lawyer-ratings")
async def list_lawyer_ratings(
    lawyer_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(LawyerRating)
    if lawyer_id:
        q = q.where(LawyerRating.lawyer_id == lawyer_id)
    q = q.order_by(LawyerRating.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


# ── Lawyer Profile Update Requests ───────────────────────────────────────────

@router.get("/lawyer-update-requests")
async def list_lawyer_update_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(LawyerProfileUpdateRequest)
    if status_filter:
        q = q.where(LawyerProfileUpdateRequest.status == status_filter.upper())
    q = q.order_by(LawyerProfileUpdateRequest.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/get-in-touch")
async def list_get_in_touch(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(GetInTouch)
    if search:
        q = q.where(
            or_(
                GetInTouch.full_name.ilike(f"%{search}%"),
                GetInTouch.email.ilike(f"%{search}%"),
                GetInTouch.subject.ilike(f"%{search}%"),
                GetInTouch.message.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(GetInTouch.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    return {"total": total, "page": page, "results": [_serialize(r) for r in rows.scalars()]}


@router.get("/system-issues")
async def list_system_issues(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(SystemIssue)
    if search:
        q = q.where(
            or_(
                SystemIssue.full_name.ilike(f"%{search}%"),
                SystemIssue.email.ilike(f"%{search}%"),
                SystemIssue.subject.ilike(f"%{search}%"),
                SystemIssue.description.ilike(f"%{search}%"),
                SystemIssue.category.ilike(f"%{search}%"),
                SystemIssue.ticket_id.ilike(f"%{search}%"),
            )
        )
    q = q.order_by(SystemIssue.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    issues = rows.scalars().all()
    
    serialized_results = []
    for r in issues:
        d = _serialize(r)
        await _inject_custom_fields("system-issues", r, d, db)
        serialized_results.append(d)
        
    return {"total": total, "page": page, "results": serialized_results}


# ═══════════════════════════════════════════════════════════════════════════════
# BULK ACTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/verify-admin")
async def bulk_verify_admin(
    payload: IdsPayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Set is_verified_by_superuser=True on AdminPanelProfiles.
    Auto-syncs is_staff=True and is_active=True on associated User.
    """
    results = []
    for profile_id in payload.ids:
        profile = await db.get(AdminPanelProfile, profile_id)
        if not profile:
            results.append({"id": profile_id, "status": "not_found"})
            continue
        profile.is_verified_by_superuser = True
        profile.updated_at = datetime.datetime.utcnow()

        user = await db.get(User, profile.user_id)
        if user:
            user.is_staff = True
            user.is_active = True
            user.updated_at = datetime.datetime.utcnow()

        await db.commit()

        # Broadcast notification
        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=profile.user_id,
                title="Profile Verified",
                message="Your admin profile has been verified and activated by the superuser.",
                url="/admin_dashboard/",
            )
        except Exception:
            pass

        results.append({"id": profile_id, "status": "verified"})

    return {"results": results}


@router.post("/unverify-admin")
async def bulk_unverify_admin(
    payload: IdsPayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """Reverse verification: is_verified_by_superuser=False, is_staff=False on User."""
    results = []
    for profile_id in payload.ids:
        profile = await db.get(AdminPanelProfile, profile_id)
        if not profile:
            results.append({"id": profile_id, "status": "not_found"})
            continue
        profile.is_verified_by_superuser = False
        profile.updated_at = datetime.datetime.utcnow()

        user = await db.get(User, profile.user_id)
        if user:
            user.is_staff = False
            user.updated_at = datetime.datetime.utcnow()

        await db.commit()

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=profile.user_id,
                title="Admin Access Revoked",
                message="Your admin verification has been revoked by the superuser.",
                url="/admin_dashboard/",
            )
        except Exception:
            pass

        results.append({"id": profile_id, "status": "unverified"})

    return {"results": results}


@router.post("/approve-admin-update")
async def bulk_approve_admin_update(
    payload: IdsPayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Merge AdminPanelProfileUpdateRequest shadow fields → AdminPanelProfile.
    Only non-null shadow values are applied.
    """
    results = []
    for req_id in payload.ids:
        req = await db.get(AdminPanelProfileUpdateRequest, req_id)
        if not req or req.status != "PENDING":
            results.append({"id": req_id, "status": "skipped"})
            continue

        profile = await db.get(AdminPanelProfile, req.admin_profile_id)
        if not profile:
            results.append({"id": req_id, "status": "profile_not_found"})
            continue

        # Merge non-null shadow fields
        for field in ("full_name", "gender", "date_of_birth", "mobile_number",
                      "alternate_mobile_number", "profile_picture"):
            val = getattr(req, field, None)
            if val is not None:
                setattr(profile, field, val)

        profile.updated_at = datetime.datetime.utcnow()
        req.status = "APPROVED"
        req.reviewed_at = datetime.datetime.utcnow()
        req.reviewed_by_id = _su.id

        user = await db.get(User, profile.user_id)
        if user and profile.full_name:
            parts = profile.full_name.strip().split(None, 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ""
            user.updated_at = datetime.datetime.utcnow()

        await db.commit()

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=profile.user_id,
                title="Profile Update Approved",
                message="Your admin profile update request has been approved and applied.",
                url="/admin_dashboard/",
            )
        except Exception:
            pass

        results.append({"id": req_id, "status": "approved"})

    return {"results": results}


@router.post("/approve-lawyer-update")
async def bulk_approve_lawyer_update(
    payload: IdsPayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Merge LawyerProfileUpdateRequest shadow fields → LawyerProfile.
    Only non-null shadow values are applied.
    """
    results = []
    for req_id in payload.ids:
        req = await db.get(LawyerProfileUpdateRequest, req_id)
        if not req or req.status != "PENDING":
            results.append({"id": req_id, "status": "skipped"})
            continue

        lawyer = await db.get(LawyerProfile, req.lawyer_id)
        if not lawyer:
            results.append({"id": req_id, "status": "profile_not_found"})
            continue

        for field in (
            "full_name", "gender", "date_of_birth", "bar_registration_number",
            "state_bar_council", "years_of_experience", "specialization",
            "bio", "consultation_fee", "office_city", "mobile_number",
            "alternate_mobile_number", "profile_picture", "bar_council_license",
        ):
            val = getattr(req, field, None)
            if val is not None:
                setattr(lawyer, field, val)

        lawyer.updated_at = datetime.datetime.utcnow()
        req.status = "APPROVED"
        req.reviewed_at = datetime.datetime.utcnow()
        req.admin_notes = f"Approved by superuser {_su.email}"

        await db.commit()

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=lawyer.user_id,
                title="Profile Update Approved",
                message="Your lawyer profile update has been approved and applied.",
                url="/lawyer_profile/",
            )
        except Exception:
            pass

        results.append({"id": req_id, "status": "approved"})

    return {"results": results}


class SoftDeletePayload(BaseModel):
    ids: List[int]
    model: str  # "client" | "lawyer" | "admin"


@router.post("/soft-delete")
async def bulk_soft_delete(
    payload: SoftDeletePayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Soft-delete client/lawyer/admin profiles:
    sets is_deleted=True on profile + is_active=False on associated User.
    """
    results = []
    model_map = {"client": ClientProfile, "lawyer": LawyerProfile, "admin": AdminPanelProfile}
    ProfileModel = model_map.get(payload.model.lower())
    if not ProfileModel:
        raise HTTPException(status_code=400, detail=f"Unknown model: {payload.model}")

    for profile_id in payload.ids:
        profile = await db.get(ProfileModel, profile_id)
        if not profile:
            results.append({"id": profile_id, "status": "not_found"})
            continue

        profile.is_deleted = True
        user = await db.get(User, profile.user_id)
        if user:
            user.is_active = False
            user.updated_at = datetime.datetime.utcnow()

        await db.commit()
        results.append({"id": profile_id, "status": "soft_deleted"})

    return {"results": results}


@router.post("/restore")
async def bulk_restore(
    payload: SoftDeletePayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore soft-deleted profiles:
    sets is_deleted=False on profile + is_active=True on associated User.
    """
    results = []
    model_map = {"client": ClientProfile, "lawyer": LawyerProfile, "admin": AdminPanelProfile}
    ProfileModel = model_map.get(payload.model.lower())
    if not ProfileModel:
        raise HTTPException(status_code=400, detail=f"Unknown model: {payload.model}")

    for profile_id in payload.ids:
        profile = await db.get(ProfileModel, profile_id)
        if not profile:
            results.append({"id": profile_id, "status": "not_found"})
            continue

        profile.is_deleted = False
        user = await db.get(User, profile.user_id)
        if user:
            user.is_active = True
            user.updated_at = datetime.datetime.utcnow()

        await db.commit()

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=profile.user_id,
                title="Account Restored",
                message="Your account has been reactivated by the superuser.",
                url="/",
            )
        except Exception:
            pass

        results.append({"id": profile_id, "status": "restored"})

    return {"results": results}


# ─── Superuser Auth / Login Endpoint ──────────────────────────────────────────

from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login", tags=["Auth"])
async def superuser_login_endpoint(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.future import select
    from ..security import pwd_context, create_access_token
    
    result = await db.execute(select(User).where(User.email == form_data.username.strip().lower()))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
        
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Access denied. Superuser privileges required.")
        
    if not pwd_context.verify(form_data.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
        
    token_data = {"sub": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    
    return {"access_token": access_token, "token_type": "bearer"}


# ── Payments ──────────────────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(Payment)
    if search:
        q = q.where(
            or_(
                Payment.razorpay_payment_id.ilike(f"%{search}%"),
                Payment.status.ilike(f"%{search}%")
            )
        )
    q = q.order_by(Payment.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    
    results = []
    for r in rows.scalars():
        d = _serialize(r)
        d = await _inject_custom_fields("payments", r, d, db)
        results.append(d)
        
    return {"total": total, "page": page, "results": results}


# ── Withdraw Requests ─────────────────────────────────────────────────────────

@router.get("/withdraw-requests")
async def list_withdraw_requests(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    q = select(WithdrawRequest)
    if search:
        q = q.where(
            or_(
                WithdrawRequest.method.ilike(f"%{search}%"),
                WithdrawRequest.status.ilike(f"%{search}%")
            )
        )
    q = q.order_by(WithdrawRequest.id.desc())
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    rows = await db.execute(_paginate(q, page))
    
    results = []
    for r in rows.scalars():
        d = _serialize(r)
        d = await _inject_custom_fields("withdraw-requests", r, d, db)
        results.append(d)
        
    return {"total": total, "page": page, "results": results}


# ─── Quick Admin User & Profile Creation ──────────────────────────────────────

class CreateAdminPayload(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    gender: str = "other"
    mobile_number: str = ""
    alternate_mobile_number: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None

@router.post("/create-admin")
async def create_admin_user(
    payload: CreateAdminPayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    import re
    from ..security import pwd_context
    
    # Validate password requirements
    if (
        len(payload.password) < 10
        or not re.search(r"[A-Z]", payload.password)
        or not re.search(r"[a-z]", payload.password)
        or not re.search(r"\d", payload.password)
        or not re.search(r"[@$!%*?&_#^()\-+={}\[\]|\\:;\"'<>,.?/~`]", payload.password)
    ):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 10 characters long, and contain at least one uppercase letter, one lowercase letter, one number, and one special character."
        )

    # Check if email already registered
    email_clean = payload.email.strip().lower()
    result = await db.execute(select(User).where(User.email == email_clean))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Create User
    hashed_password = pwd_context.hash(payload.password)
    new_user = User(
        email=email_clean,
        password=hashed_password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role="admin",
        is_active=True,
        is_staff=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Create AdminPanelProfile
    profile = AdminPanelProfile(
        user_id=new_user.id,
        full_name=f"{payload.first_name} {payload.last_name}".strip(),
        gender=payload.gender,
        mobile_number=payload.mobile_number,
        alternate_mobile_number=payload.alternate_mobile_number,
        date_of_birth=payload.date_of_birth,
        is_profile_complete=True,
        is_verified_by_superuser=True
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Set custom ID based on database primary key
    profile.custom_id = f"ad:{profile.id:05d}"
    await db.commit()
    await db.refresh(profile)

    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "profile_id": profile.id,
        "full_name": profile.full_name,
        "custom_id": profile.custom_id
    }


# ─── MODEL MAPPINGS (shared by all generic handlers) ─────────────────────────


MODEL_MAPPINGS = {
    "users": User,
    "delete-tokens": DeleteAccountToken,
    "notifications": Notification,
    "otp-codes": OTPCode,
    "get-in-touch": GetInTouch,
    "system-issues": SystemIssue,
    "admin-profiles": AdminPanelProfile,
    "admin-update-requests": AdminPanelProfileUpdateRequest,
    "lawyer-verification-requests": LawyerVerificationRequest,
    "lawyer-update-requests": LawyerProfileUpdateRequest,  # was missing — caused link crash + bulk-delete 500
    "trust-reports": TrustReport,
    "client-profiles": ClientProfile,
    "lawyer-profiles": LawyerProfile,
    "case-document-verifications": CaseDocumentVerification,
    "case-documents": CaseDocument,
    "case-messages": CaseMessage,
    "lawyer-ratings": LawyerRating,
    "case-requests": CaseRequest,
    "payments": Payment,
    "withdraw-requests": WithdrawRequest,
}


# ─── Bulk Delete ──────────────────────────────────────────────────────────────

class BulkDeletePayload(BaseModel):
    ids: List[int]
    model: str  # any key from MODEL_MAPPINGS


@router.post("/bulk-delete")
async def bulk_delete_records(
    payload: BulkDeletePayload,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete multiple records from any model.
    Registered BEFORE the generic POST /{model_path} catch-all.
    When model='users', uses the full cascade-delete helper so all
    FK-linked child data is removed automatically — no "deleted 0" failures.
    """
    from sqlalchemy.exc import IntegrityError, DBAPIError

    model_cls = MODEL_MAPPINGS.get(payload.model)
    if not model_cls:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model '{payload.model}'. "
                   f"Valid: {', '.join(MODEL_MAPPINGS.keys())}",
        )

    results = []
    deleted_count = 0

    for record_id in payload.ids:
        try:
            # ── Users: full cascade delete ────────────────────────────────────
            if payload.model == "users":
                user_exists = await db.get(User, record_id)
                if user_exists is None:
                    results.append({"id": record_id, "status": "not_found"})
                    continue
                await _cascade_delete_user(record_id, db)
                await db.commit()
                results.append({"id": record_id, "status": "deleted"})
                deleted_count += 1

            # ── All other models: simple delete ───────────────────────────────
            else:
                result = await db.execute(
                    select(model_cls).where(model_cls.id == record_id)
                )
                record = result.scalar_one_or_none()
                if record is None:
                    results.append({"id": record_id, "status": "not_found"})
                    continue
                if payload.model == "system-issues":
                    _delete_system_issue_file(record)
                await db.delete(record)
                await db.commit()
                results.append({"id": record_id, "status": "deleted"})
                deleted_count += 1

        except (IntegrityError, DBAPIError) as exc:
            await db.rollback()
            results.append({
                "id": record_id,
                "status": "error",
                "detail": "FK constraint — delete child records first.",
            })
        except Exception as exc:
            await db.rollback()
            results.append({"id": record_id, "status": "error", "detail": str(exc)})

    return {"deleted": deleted_count, "results": results}


# ─── Dynamic Edit & Add Handlers ──────────────────────────────────────────────

@router.post("/{model_path}")
async def create_any_record(
    model_path: str,
    payload: Dict[str, Any] = Body(...),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    model_cls = MODEL_MAPPINGS.get(model_path)
    if not model_cls:
        raise HTTPException(status_code=404, detail=f"Model path '{model_path}' not found")
        
    record = model_cls()
    
    # Set attributes dynamically
    for field, val in payload.items():
        if field in ["id", "created_at", "updated_at"]:
            continue
        if not hasattr(model_cls, field):
            continue
            
        col_type = getattr(model_cls, field).property.columns[0].type
        import datetime
        from sqlalchemy import DateTime, Date
        import sqlalchemy
        
        if isinstance(col_type, (DateTime, Date)) and isinstance(val, str):
            try:
                val = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                pass
        elif isinstance(col_type, sqlalchemy.types.Boolean) and isinstance(val, str):
            val = val.lower() in ("true", "1", "yes")
        elif isinstance(col_type, sqlalchemy.types.Integer) and val is not None:
            try:
                val = int(val)
            except ValueError:
                pass
        elif isinstance(col_type, sqlalchemy.types.Float) and val is not None:
            try:
                val = float(val)
            except ValueError:
                pass
                
        setattr(record, field, val)
        
    if hasattr(record, "created_at") and getattr(record, "created_at") is None:
        record.created_at = datetime.datetime.utcnow()
    if hasattr(record, "updated_at") and getattr(record, "updated_at") is None:
        record.updated_at = datetime.datetime.utcnow()
        
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return await _inject_custom_fields(model_path, record, _serialize(record), db)


@router.put("/{model_path}/{record_id}")
async def update_any_record(
    model_path: str,
    record_id: int,
    payload: Dict[str, Any] = Body(...),
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    import sqlalchemy
    from sqlalchemy import DateTime, Date
    from sqlalchemy.exc import IntegrityError

    model_cls = MODEL_MAPPINGS.get(model_path)
    if not model_cls:
        raise HTTPException(status_code=404, detail=f"Model '{model_path}' not found in MODEL_MAPPINGS")

    result = await db.execute(select(model_cls).where(model_cls.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"Record #{record_id} not found")

    SKIP = {"id", "created_at", "updated_at", "date_joined", "submitted_at",
            "reviewed_at", "verified_at", "uploaded_at"}

    for field, val in payload.items():
        if field in SKIP:
            continue
        if not hasattr(model_cls, field):
            continue
        try:
            col_attr = getattr(model_cls, field)
            col_type = col_attr.property.columns[0].type
        except Exception:
            continue

        if isinstance(col_type, (DateTime, Date)):
            if isinstance(val, str) and val:
                try:
                    val = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
                except ValueError:
                    pass
            elif not val:
                val = None
        elif isinstance(col_type, sqlalchemy.types.Boolean):
            if isinstance(val, str):
                val = val.lower() in ("true", "1", "yes")
            else:
                val = bool(val) if val is not None else False
        elif isinstance(col_type, sqlalchemy.types.Integer):
            if val is not None:
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = None
        elif isinstance(col_type, sqlalchemy.types.Numeric):
            if val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = None

        setattr(record, field, val)

    if hasattr(record, "updated_at"):
        record.updated_at = datetime.datetime.utcnow()

    # ── Handle side effects / field syncing when status is updated via modal or PUT ──
    if model_path == "admin-update-requests" and getattr(record, "status", None) == "APPROVED":
        profile = await db.get(AdminPanelProfile, record.admin_profile_id)
        if profile:
            for f in ("full_name", "gender", "date_of_birth", "mobile_number",
                      "alternate_mobile_number", "profile_picture"):
                v = getattr(record, f, None)
                if v is not None:
                    setattr(profile, f, v)
            profile.updated_at = datetime.datetime.utcnow()
            user = await db.get(User, profile.user_id)
            if user and profile.full_name:
                parts = profile.full_name.strip().split(None, 1)
                user.first_name = parts[0]
                user.last_name = parts[1] if len(parts) > 1 else ""
                user.updated_at = datetime.datetime.utcnow()
        if not getattr(record, "reviewed_at", None):
            record.reviewed_at = datetime.datetime.utcnow()
        if not getattr(record, "reviewed_by_id", None):
            record.reviewed_by_id = _su.id

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=profile.user_id,
                title="Profile Update Approved",
                message="Your admin profile update request has been approved and applied.",
                url="/admin_dashboard/",
            )
        except Exception:
            pass

    elif model_path == "lawyer-update-requests" and getattr(record, "status", None) in ("APPROVED", "approved"):
        lawyer = await db.get(LawyerProfile, record.lawyer_id)
        if lawyer:
            for f in (
                "full_name", "gender", "date_of_birth", "bar_registration_number",
                "state_bar_council", "years_of_experience", "specialization",
                "bio", "consultation_fee", "office_city", "mobile_number",
                "alternate_mobile_number", "profile_picture", "bar_council_license"
            ):
                v = getattr(record, f, None)
                if v is not None:
                    setattr(lawyer, f, v)
            lawyer.updated_at = datetime.datetime.utcnow()
            user = await db.get(User, lawyer.user_id)
            if user and lawyer.full_name:
                parts = lawyer.full_name.strip().split(None, 1)
                user.first_name = parts[0]
                user.last_name = parts[1] if len(parts) > 1 else ""
                user.updated_at = datetime.datetime.utcnow()
        if not getattr(record, "reviewed_at", None):
            record.reviewed_at = datetime.datetime.utcnow()

        try:
            await create_and_broadcast_notification(
                db=db,
                user_id=lawyer.user_id,
                title="Profile Update Approved",
                message="Your lawyer profile update has been approved and applied.",
                url="/lawyer_profile/",
            )
        except Exception:
            pass

    elif model_path == "lawyer-verification-requests" and getattr(record, "status", None) in ("approved", "APPROVED"):
        lawyer = await db.get(LawyerProfile, record.lawyer_id)
        if lawyer:
            lawyer.verified = True
            lawyer.is_profile_complete = True
            lawyer.updated_at = datetime.datetime.utcnow()
            user = await db.get(User, lawyer.user_id)
            if user:
                user.is_active = True
                user.updated_at = datetime.datetime.utcnow()
        if not getattr(record, "reviewed_at", None):
            record.reviewed_at = datetime.datetime.utcnow()
        if not getattr(record, "reviewed_by_id", None):
            record.reviewed_by_id = _su.id

    elif model_path == "admin-profiles":
        if getattr(record, "is_verified_by_superuser", False):
            user = await db.get(User, record.user_id)
            if user:
                user.is_staff = True
                user.is_active = True
                user.updated_at = datetime.datetime.utcnow()

    try:
        await db.commit()
        await db.refresh(record)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Integrity error: {exc.orig}")
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return await _inject_custom_fields(model_path, record, _serialize(record), db)


# ─── Generic GET single record ────────────────────────────────────────────────

@router.get("/{model_path}/{record_id}")
async def get_any_record(
    model_path: str,
    record_id: int,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Generic single-record fetch. Specific endpoints (e.g. /users/{id})
    registered earlier take precedence; this handles all remaining models.
    """
    model_cls = MODEL_MAPPINGS.get(model_path)
    if not model_cls:
        raise HTTPException(status_code=404, detail=f"Model path '{model_path}' not found")
    record = await db.get(model_cls, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return await _inject_custom_fields(model_path, record, _serialize(record), db)


# ─── Generic DELETE single record ────────────────────────────────────────────

@router.delete("/{model_path}/{record_id}", status_code=204)
async def delete_any_record(
    model_path: str,
    record_id: int,
    _su: User = Depends(check_superuser),
    db: AsyncSession = Depends(get_db),
):
    """
    Generic delete. Specific delete endpoints registered earlier take precedence.
    Returns 409 instead of 500 on FK constraint violations.
    """
    from sqlalchemy.exc import IntegrityError, DBAPIError

    model_cls = MODEL_MAPPINGS.get(model_path)
    if not model_cls:
        raise HTTPException(status_code=404, detail=f"Model path '{model_path}' not found")
    record = await db.get(model_cls, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if model_path == "system-issues":
        _delete_system_issue_file(record)
    try:
        await db.delete(record)
        await db.commit()
    except (IntegrityError, DBAPIError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete record #{record_id} from '{model_path}': it has dependent child records. "
                   f"Delete related records first (e.g. case requests, notifications, profiles).",
        )
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")
