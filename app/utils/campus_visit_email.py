"""Confirmation emails for public campus visit bookings."""

import html
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from app import settings
from app.utils.smtp import send_mail

logger = logging.getLogger(__name__)


def _mail_configured() -> bool:
    if not settings.MAIL_FROM:
        return False
    if getattr(settings, "MAIL_USE_API", False):
        return bool(settings.MAIL_PASSWORD)
    return bool(settings.MAIL_SERVER and settings.MAIL_USERNAME and settings.MAIL_PASSWORD)


def _format_range_local(starts_at: datetime, ends_at: datetime, tz_name: str) -> tuple[str, str]:
    tz = ZoneInfo(tz_name or "UTC")
    s = starts_at.astimezone(tz)
    e = ends_at.astimezone(tz)
    fmt = "%Y-%m-%d %H:%M"
    return s.strftime(fmt), e.strftime(fmt)


async def send_campus_visit_booking_confirmation_email(
    *,
    to_email: str,
    visitor_name: str,
    institute_name: str,
    campus_name: str,
    campus_timezone: str,
    slot_title: Optional[str],
    starts_at: datetime,
    ends_at: datetime,
    booking_id: UUID,
) -> None:
    if not _mail_configured():
        logger.warning("Mail not configured; skipping campus visit booking confirmation")
        return

    safe_name = html.escape(visitor_name.strip())
    safe_institute = html.escape(institute_name)
    safe_campus = html.escape(campus_name)
    title_line = ""
    if slot_title:
        title_line = f"<p><strong>Visit:</strong> {html.escape(slot_title)}</p>"

    start_str, end_str = _format_range_local(starts_at, ends_at, campus_timezone)
    safe_tz = html.escape(campus_timezone or "UTC")

    subject = f"Campus visit confirmed — {institute_name}"
    body = f"""
    <p>Hello {safe_name},</p>
    <p>Your campus visit is booked.</p>
    <p><strong>Institute:</strong> {safe_institute}<br/>
    <strong>Campus:</strong> {safe_campus}</p>
    {title_line}
    <p><strong>Start:</strong> {html.escape(start_str)} ({safe_tz})<br/>
    <strong>End:</strong> {html.escape(end_str)} ({safe_tz})</p>
    <p>If you need to change or cancel, please contact the institute.</p>
    """

    try:
        await send_mail(to_email, subject, body.strip())
    except Exception:
        logger.exception("Failed to send campus visit booking confirmation to %s", to_email)
