"""
Dual SMTP email utility.
Auth emails  → sharikahmed731@gmail.com
Operations emails → tridevx9@gmail.com
"""
import os
import django

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "divorce_connect.settings")

try:
    django.setup()
except Exception:
    pass

from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

# ── Purpose constants ────────────────────────────────────────────────────────
PURPOSE_AUTH = "auth"
PURPOSE_OPERATIONS = "operations"


def _send_html_email(subject, template_name, context, recipient_email, purpose):
    """Internal helper: render an HTML template and send it asynchronously via Taskiq."""
    html_body = render_to_string(template_name, context)

    from fastapi_app.tasks import send_email_task
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_email_task(recipient_email, subject, html_body, purpose))
    except RuntimeError:
        asyncio.run(send_email_task(recipient_email, subject, html_body, purpose))



# ── Auth emails ───────────────────────────────────────────────────────────────

def send_otp_email(user, otp_code):
    """Send login OTP to the user via auth SMTP."""
    now = timezone.localtime(timezone.now())
    _send_html_email(
        subject="🔐 Your Login OTP — DivorceConnect India",
        template_name="emails/otp_email.html",
        context={
            "user_name": user.get_full_name() or user.email,
            "otp_code": otp_code,
            "login_time": now.strftime("%d %b %Y, %I:%M %p"),
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_register_otp_email(user, otp_code):
    """Send registration verification OTP via auth SMTP."""
    _send_html_email(
        subject="✉️ Verify Your Email — DivorceConnect India",
        template_name="emails/register_otp_email.html",
        context={
            "user_name": user.get_full_name() or user.first_name or user.email,
            "otp_code": otp_code,
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_password_reset_otp_email(user, otp_code):
    """Send a password reset verification code via auth SMTP."""
    _send_html_email(
        subject="🔐 Password Reset Verification Code — DivorceConnect India",
        template_name="emails/otp_email.html",
        context={
            "user_name": user.get_full_name() or user.email,
            "otp_code": otp_code,
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_welcome_back_email(user):
    """Send a Welcome Back email after successful OTP-verified login."""
    now = timezone.localtime(timezone.now())
    _send_html_email(
        subject="👋 Welcome Back — DivorceConnect India",
        template_name="emails/welcome_back_email.html",
        context={
            "user_name": user.get_full_name() or user.email,
            "user_email": user.email,
            "login_time": now.strftime("%d %b %Y, %I:%M %p"),
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_registration_email(user, role):
    """Send a welcome email upon successful registration via auth SMTP."""
    role_labels = {
        "client": "Client Account",
        "lawyer": "Lawyer Account",
        "admin": "Admin Account",
    }
    _send_html_email(
        subject="🎉 Welcome to DivorceConnect India — Registration Successful",
        template_name="emails/registration_email.html",
        context={
            "user_name": user.get_full_name() or user.email,
            "role_label": role_labels.get(role, "User Account"),
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_logout_email(user_name, user_email):
    """Send a logout confirmation via auth SMTP."""
    now = timezone.localtime(timezone.now())
    _send_html_email(
        subject="🔒 You've been signed out — DivorceConnect India",
        template_name="emails/logout_email.html",
        context={
            "user_name": user_name,
            "user_email": user_email,
            "logout_time": now.strftime("%d %b %Y, %I:%M %p"),
        },
        recipient_email=user_email,
        purpose=PURPOSE_AUTH,
    )


# ── Operations emails ─────────────────────────────────────────────────────────

def send_case_accepted_email(case_request):
    """Send case-accepted email to client with lawyer details."""
    lawyer = case_request.lawyer
    client = case_request.client
    now = timezone.localtime(timezone.now())
    _send_html_email(
        subject="✅ Your Case Has Been Accepted — DivorceConnect India",
        template_name="emails/case_accepted_email.html",
        context={
            "client_name": client.get_full_name(),
            "lawyer_name": lawyer.full_name,
            "lawyer_specialization": getattr(lawyer, "specialization", "Divorce Law"),
            "lawyer_city": getattr(lawyer, "office_city", "India"),
            "lawyer_mobile": getattr(lawyer, "mobile_number", "N/A"),
            "lawyer_experience": getattr(lawyer, "years_of_experience", "N/A"),
            "case_id": case_request.id,
            "accepted_date": now.strftime("%d %b %Y"),
        },
        recipient_email=client.user.email,
        purpose=PURPOSE_OPERATIONS,
    )


def send_report_submitted_email(reporter_name, reporter_email, reported_name, report_reason, report_id=None):
    """Send report confirmation email to the reporter via operations SMTP."""
    now = timezone.localtime(timezone.now())
    _send_html_email(
        subject="🛡️ Report Received — DivorceConnect India",
        template_name="emails/report_submitted_email.html",
        context={
            "reporter_name": reporter_name,
            "reported_name": reported_name,
            "report_reason": report_reason,
            "submitted_date": now.strftime("%d %b %Y"),
            "report_id": report_id,
        },
        recipient_email=reporter_email,
        purpose=PURPOSE_OPERATIONS,
    )


def send_delete_account_email(user, confirm_url):
    """Send a secure account deletion confirmation link via auth SMTP."""
    _send_html_email(
        subject="⚠️ Confirm Account Deletion — DivorceConnect India",
        template_name="emails/delete_account_email.html",
        context={
            "user_name": user.get_full_name() or user.email,
            "user_email": user.email,
            "confirm_url": confirm_url,
        },
        recipient_email=user.email,
        purpose=PURPOSE_AUTH,
    )


def send_report_action_to_reporter(report):
    """Send action notification to the reporter."""
    reporter = report.reporter
    reporter_name = reporter.get_full_name() or reporter.email
    reported_name = report.target_name
    action_label = report.get_status_display()
    
    _send_html_email(
        subject="🛡️ Action Taken on Your Report — DivorceConnect India",
        template_name="emails/report_action_reporter_email.html",
        context={
            "reporter_name": reporter_name,
            "reported_name": reported_name,
            "action_status": report.status,
            "action_label": action_label,
            "admin_notes": report.admin_notes or "No additional comments from admin.",
            "report_reason": report.reason,
            "action_date": timezone.localtime(timezone.now()).strftime("%d %b %Y, %I:%M %p"),
        },
        recipient_email=reporter.email,
        purpose=PURPOSE_OPERATIONS,
    )


def send_report_action_to_reported(report):
    """Send action/warning/ban notification to the reported party."""
    reported_user = None
    reported_name = ""
    if report.reported_client:
        reported_user = report.reported_client.user
        reported_name = report.reported_client.get_full_name()
    elif report.reported_lawyer:
        reported_user = report.reported_lawyer.user
        reported_name = report.reported_lawyer.full_name
        
    if not reported_user:
        return
        
    action_label = report.get_status_display()
    
    _send_html_email(
        subject="🛡️ Important Account Notification — DivorceConnect India",
        template_name="emails/report_action_reported_email.html",
        context={
            "reported_name": reported_name,
            "action_status": report.status,
            "action_label": action_label,
            "admin_notes": report.admin_notes or "No additional comments from admin.",
            "action_date": timezone.localtime(timezone.now()).strftime("%d %b %Y, %I:%M %p"),
        },
        recipient_email=reported_user.email,
        purpose=PURPOSE_OPERATIONS,
    )


def send_lawyer_reported_notification_email(lawyer_name, lawyer_email, report_reason, report_description, report_id=None):
    """Send report notification email to the reported lawyer via operations SMTP."""
    _send_html_email(
        subject="🛡️ Notice of Report Filed — DivorceConnect India",
        template_name="emails/reported_notification_email.html",
        context={
            "lawyer_name": lawyer_name,
            "recipient_name": lawyer_name,
            "report_reason": report_reason,
            "report_description": report_description,
            "report_id": report_id,
        },
        recipient_email=lawyer_email,
        purpose=PURPOSE_OPERATIONS,
    )


def send_client_reported_notification_email(client_name, client_email, report_reason, report_description, report_id=None):
    """Send report notification email to the reported client via operations SMTP."""
    _send_html_email(
        subject="🛡️ Notice of Report Filed — DivorceConnect India",
        template_name="emails/reported_notification_email.html",
        context={
            "recipient_name": client_name,
            "report_reason": report_reason,
            "report_description": report_description,
            "report_id": report_id,
        },
        recipient_email=client_email,
        purpose=PURPOSE_OPERATIONS,
    )

