"""
SMTP email utility using fastapi-mail.
"""
from typing import List, Union

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

from app import settings


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


async def send_mail(
    recipients: Union[List[str], str],
    subject: str,
    body: str,
    *,
    subtype: MessageType = MessageType.html,
) -> None:
    """
    Send an email using the configured SMTP settings.

    Args:
        recipients: Email address(es) to send to (list or single string).
        subject: Email subject.
        body: Email body (plain text or HTML depending on subtype).
        subtype: MessageType.html or MessageType.plain (default: html).
    """
    if isinstance(recipients, str):
        recipients = [recipients]
    config = _get_mail_config()
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype=subtype,
    )
    fm = FastMail(config)
    print(f"Sending email to {recipients} with subject {subject} and body {body}")
    await fm.send_message(message)
    print(f"Email sent to {recipients} with subject {subject} and body {body}")
