"""
backend/app/services/whatsapp.py
Twilio WhatsApp integration.
Handles incoming WhatsApp messages and sends replies.
"""

import os
import logging
import httpx
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


async def send_whatsapp_message(to: str, body: str) -> bool:
    """
    Send a WhatsApp message via Twilio API.

    Args:
        to: Recipient WhatsApp number in format 'whatsapp:+1234567890'
        body: Message text (max 1600 chars for WhatsApp)

    Returns:
        True if sent successfully
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")  # Twilio sandbox default

    if not account_sid or not auth_token:
        logger.error("[twilio] TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set")
        return False

    # Ensure numbers have whatsapp: prefix
    if not to.startswith("whatsapp:"):
        to = f"whatsapp:{to}"
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"

    # Truncate long messages (WhatsApp limit)
    if len(body) > 1600:
        body = body[:1597] + "..."

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": to, "Body": body},
        )

    if response.status_code == 201:
        msg_sid = response.json().get("sid", "unknown")
        logger.info(f"[twilio] Sent WhatsApp to {to} | SID: {msg_sid}")
        return True
    else:
        logger.error(f"[twilio] Failed to send: {response.status_code} {response.text}")
        return False


def parse_twilio_webhook(form_data: dict) -> dict:
    """
    Parse incoming Twilio WhatsApp webhook payload.

    Twilio sends form-encoded POST with these key fields:
        Body      — the message text
        From      — sender's WhatsApp number (whatsapp:+1234567890)
        To        — your Twilio number
        ProfileName — sender's WhatsApp display name
        NumMedia  — number of media files attached
        MediaUrl0 — URL of first media file (if any)

    Returns parsed dict with normalized fields.
    """
    return {
        "message":      form_data.get("Body", "").strip(),
        "from_number":  form_data.get("From", ""),       # whatsapp:+1234567890
        "to_number":    form_data.get("To", ""),
        "sender_name":  form_data.get("ProfileName", "WhatsApp User"),
        "num_media":    int(form_data.get("NumMedia", 0)),
        "media_url":    form_data.get("MediaUrl0"),       # first attachment if any
        "message_sid":  form_data.get("MessageSid", ""),
        # Extract clean phone number for DB storage
        "phone":        form_data.get("From", "").replace("whatsapp:", ""),
    }


def build_twiml_response(message: str) -> str:
    """
    Build a TwiML XML response.
    Twilio can use this instead of the REST API for synchronous replies.
    For WhatsApp we use the REST API (send_whatsapp_message) instead,
    but this is useful for SMS fallback.
    """
    # Escape XML special characters
    message = (message
               .replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;"))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""