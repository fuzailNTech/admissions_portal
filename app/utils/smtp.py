"""
Email utility: SMTP (fastapi-mail) or Postmark HTTP API.
Use MAIL_USE_API=True to send via Postmark API (HTTPS), e.g. on Render where port 587 is blocked.
"""
import asyncio
from typing import List, Union

import httpx
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

from app import settings

POSTMARK_EMAIL_URL = "https://api.postmarkapp.com/email"


def _get_mail_config() -> ConnectionConfig:
    """Build ConnectionConfig from application settings."""
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=True,
    )


def _send_via_postmark_api_sync(
    recipients: List[str],
    subject: str,
    body: str,
    *,
    is_html: bool = True,
) -> None:
    """Send a single email via Postmark HTTP API (sync)."""
    token = settings.MAIL_PASSWORD
    if not token:
        raise ValueError("MAIL_PASSWORD is required when MAIL_USE_API=True")
    payload = {
        "From": settings.MAIL_FROM,
        "To": ",".join(recipients),
        "Subject": subject,
        "MessageStream": "outbound",
    }
    if is_html:
        payload["HtmlBody"] = body
    else:
        payload["TextBody"] = body
    resp = httpx.post(
        POSTMARK_EMAIL_URL,
        json=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": token,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("ErrorCode", 0) != 0:
        raise RuntimeError(data.get("Message", "Postmark API error"))


async def _send_via_postmark_api_async(
    recipients: List[str],
    subject: str,
    body: str,
    *,
    is_html: bool = True,
) -> None:
    """Send a single email via Postmark HTTP API (async)."""
    token = settings.MAIL_PASSWORD
    if not token:
        raise ValueError("MAIL_PASSWORD is required when MAIL_USE_API=True")
    payload = {
        "From": settings.MAIL_FROM,
        "To": ",".join(recipients),
        "Subject": subject,
        "MessageStream": "outbound",
    }
    if is_html:
        payload["HtmlBody"] = body
    else:
        payload["TextBody"] = body
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            POSTMARK_EMAIL_URL,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": token,
            },
            timeout=30.0,
        )
    resp.raise_for_status()
    data = resp.json()
    if data.get("ErrorCode", 0) != 0:
        raise RuntimeError(data.get("Message", "Postmark API error"))


async def send_mail(
    recipients: Union[List[str], str],
    subject: str,
    body: str,
    *,
    subtype: MessageType = MessageType.html,
) -> None:
    """
    Send an email using SMTP or Postmark HTTP API (when MAIL_USE_API=True).

    Args:
        recipients: Email address(es) to send to (list or single string).
        subject: Email subject.
        body: Email body (plain text or HTML depending on subtype).
        subtype: MessageType.html or MessageType.plain (default: html).
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    if getattr(settings, "MAIL_USE_API", False) and getattr(settings, "MAIL_PASSWORD", None):
        await _send_via_postmark_api_async(
            recipients=recipients,
            subject=subject,
            body=body,
            is_html=(subtype == MessageType.html),
        )
        return
    config = _get_mail_config()
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype=subtype,
    )
    fm = FastMail(config)
    await fm.send_message(message)


def send_mail_sync(
    recipients: Union[List[str], str],
    subject: str,
    body: str,
    *,
    subtype: MessageType = MessageType.html,
) -> None:
    """
    Synchronous send: uses Postmark API when MAIL_USE_API=True, else SMTP.
    Use from sync code (e.g. workflow handlers).
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    if getattr(settings, "MAIL_USE_API", False) and getattr(settings, "MAIL_PASSWORD", None):
        _send_via_postmark_api_sync(
            recipients=recipients,
            subject=subject,
            body=body,
            is_html=(subtype == MessageType.html),
        )
        return
    asyncio.run(send_mail(recipients=recipients, subject=subject, body=body, subtype=subtype))
