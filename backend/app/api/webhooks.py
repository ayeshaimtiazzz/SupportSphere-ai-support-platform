"""
backend/app/api/webhooks.py
Twilio WhatsApp webhook endpoint.

How it works:
1. Customer sends WhatsApp message to your Twilio number
2. Twilio POSTs to this endpoint with the message details
3. We parse it, run the LangGraph agent, reply via Twilio REST API

Setup in Twilio Console:
  Messaging → Try it out → Send a WhatsApp message
  Sandbox Settings → When a message comes in:
    URL: https://your-ngrok-url.ngrok.io/webhooks/whatsapp
    Method: HTTP POST
"""

import uuid
import logging
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse

from app.services.whatsapp import parse_twilio_webhook, send_whatsapp_message, build_twiml_response
from app.agents.graph import run_support_agent

logger = logging.getLogger(__name__)
router = APIRouter()

# Default tenant for WhatsApp (in production, map Twilio numbers to tenants)
WHATSAPP_TENANT = {
    "id":           "a0000000-0000-0000-0000-000000000001",
    "name":         "Acme Corp",
    "system_prompt": (
        "You are a helpful WhatsApp customer support agent for Acme Corp. "
        "Keep responses concise — WhatsApp users prefer short messages. "
        "Use simple language. If you need to list things, use emojis as bullets."
    ),
}


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receives incoming WhatsApp messages from Twilio.

    Twilio expects either:
    - HTTP 200 with empty body (we send reply separately via REST API)
    - HTTP 200 with TwiML XML body (Twilio sends it directly)

    We use the REST API approach (send_whatsapp_message) so we can
    send the response asynchronously after agent processing.
    """
    # Parse form-encoded Twilio payload
    form_data = await request.form()
    payload = parse_twilio_webhook(dict(form_data))

    logger.info(
        f"[whatsapp] Incoming from {payload['from_number']} "
        f"({payload['sender_name']}): '{payload['message'][:80]}'"
    )

    # Ignore empty messages or media-only messages
    if not payload["message"]:
        if payload["num_media"] > 0:
            await send_whatsapp_message(
                payload["from_number"],
                "Thanks for the media! I can only process text messages right now. "
                "Please describe your issue in text."
            )
        return PlainTextResponse("", status_code=200)

    # Create conversation/customer IDs
    # In production: look up by phone number in DB
    conversation_id = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{WHATSAPP_TENANT['id']}:{payload['phone']}"
    ))  # deterministic UUID per tenant+phone combo

    customer_id = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        payload["phone"]
    ))

    # Try to save customer/conversation to DB
    try:
        from app.database import get_or_create_customer, create_conversation, save_message
        customer = await get_or_create_customer(
            tenant_id=WHATSAPP_TENANT["id"],
            phone=payload["phone"],
            name=payload["sender_name"],
            channel="whatsapp",
        )
        customer_id = str(customer["id"])
    except Exception as e:
        logger.warning(f"[whatsapp] DB skip: {e}")

    # Run the support agent
    try:
        result = await run_support_agent(
            user_input=payload["message"],
            tenant_id=WHATSAPP_TENANT["id"],
            customer_id=customer_id,
            conversation_id=conversation_id,
            system_prompt=WHATSAPP_TENANT["system_prompt"],
            channel="whatsapp",
        )
        response_text = result["response"]

        # Add escalation note for WhatsApp
        if result.get("should_escalate"):
            response_text += "\n\n⚠️ A human agent will follow up with you shortly."

    except Exception as e:
        logger.error(f"[whatsapp] Agent error: {e}", exc_info=True)
        response_text = (
            "Sorry, I'm having trouble processing your request right now. "
            "Please try again in a moment or call us directly."
        )

    # Send reply via Twilio REST API
    sent = await send_whatsapp_message(payload["from_number"], response_text)
    if not sent:
        logger.error(f"[whatsapp] Failed to send reply to {payload['from_number']}")

    # Return 200 with empty body (we already sent reply via REST API)
    return PlainTextResponse("", status_code=200)


@router.get("/whatsapp/health")
async def whatsapp_health():
    """Simple health check for the WhatsApp webhook URL."""
    return {"status": "ok", "webhook": "whatsapp"}