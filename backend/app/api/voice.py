"""
backend/app/api/voice.py
Voice input/output API endpoints.

Two modes:
1. HTTP upload  — POST /api/v1/voice/transcribe  (simpler, for testing)
2. WebSocket    — WS  /api/v1/voice/ws/{conversation_id}  (real-time, for React UI)

Flow:
  Browser records audio (MediaRecorder API)
    → sends to FastAPI
      → Whisper transcribes
        → LangGraph agent processes
          → ElevenLabs converts response to audio
            → audio sent back to browser
"""

import uuid
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header
from fastapi.responses import Response
import json

from app.services.voice import transcribe_audio, text_to_speech, get_available_voices
from app.agents.graph import run_support_agent
from app.api.conversations import get_tenant

logger = logging.getLogger(__name__)
router = APIRouter()


# ════════════════════════════════════════════════════════════
# HTTP ENDPOINT — Simple file upload (good for testing)
# ════════════════════════════════════════════════════════════

@router.post("/transcribe")
async def transcribe_and_respond(
    audio: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    voice_response: bool = Form(False),   # if True, return audio; else return text
    tenant: dict = Depends(get_tenant),
):
    """
    Upload an audio file, get AI response.

    Steps:
    1. Receive audio file
    2. Whisper transcribes it to text
    3. LangGraph agent generates response
    4. Return JSON with text + optional audio URL

    Test with curl:
        curl -X POST http://localhost:8000/api/v1/voice/transcribe \\
          -H "X-API-Key: acme_test_key_abc123" \\
          -F "audio=@recording.webm" \\
          -F "voice_response=true"
    """
    # Read audio bytes
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    if len(audio_bytes) > 25 * 1024 * 1024:  # 25MB limit (Whisper API limit)
        raise HTTPException(status_code=400, detail="Audio file too large (max 25MB)")

    logger.info(f"[voice] Received audio: {len(audio_bytes)} bytes, format: {audio.filename}")

    # Step 1: Transcribe
    try:
        transcript = await transcribe_audio(audio_bytes, filename=audio.filename or "audio.webm")
    except Exception as e:
        logger.error(f"[voice] Transcription failed: {e}")
        raise HTTPException(status_code=502, detail=f"Transcription failed: {str(e)}")

    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio — no speech detected")

    # Step 2: Run agent
    conv_id = conversation_id or str(uuid.uuid4())
    customer_id = str(uuid.uuid4())

    try:
        result = await run_support_agent(
            user_input=transcript,
            tenant_id=tenant["id"],
            customer_id=customer_id,
            conversation_id=conv_id,
            system_prompt=tenant.get("system_prompt", "You are a helpful support agent."),
            channel="voice",
        )
    except Exception as e:
        logger.error(f"[voice] Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    response_text = result["response"]

    # Step 3: Optional TTS
    audio_b64 = None
    if voice_response:
        try:
            audio_bytes_out = await text_to_speech(response_text)
            import base64
            audio_b64 = base64.b64encode(audio_bytes_out).decode("utf-8")
        except Exception as e:
            logger.warning(f"[voice] TTS failed (returning text only): {e}")

    return {
        "transcript": transcript,
        "response": response_text,
        "intent": result["intent"],
        "confidence": result["confidence"],
        "language": result["language"],
        "conversation_id": conv_id,
        "audio_base64": audio_b64,          # MP3 audio if voice_response=True
        "audio_mime_type": "audio/mpeg" if audio_b64 else None,
    }


@router.get("/tts")
async def text_to_speech_endpoint(
    text: str,
    voice: str = "default",
    tenant: dict = Depends(get_tenant),
):
    """
    Convert text to speech and return MP3 audio.
    Used by the frontend to play back AI responses.

    Example: GET /api/v1/voice/tts?text=Hello+how+can+I+help
    """
    try:
        audio_bytes = await text_to_speech(text, voice_id=voice)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=response.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TTS failed: {str(e)}")


@router.get("/voices")
async def list_voices(tenant: dict = Depends(get_tenant)):
    """List available ElevenLabs voices."""
    voices = await get_available_voices()
    return {"voices": voices}


# ════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT — Real-time voice streaming
# ════════════════════════════════════════════════════════════

@router.websocket("/ws/{conversation_id}")
async def voice_websocket(
    websocket: WebSocket,
    conversation_id: str,
    api_key: str = "",          # passed as query param: /ws/conv-id?api_key=xxx
    tenant_id: str = "a0000000-0000-0000-0000-000000000001",  # demo default
):
    """
    WebSocket endpoint for real-time voice.

    Protocol:
      Client → Server: binary audio chunks (webm blobs from MediaRecorder)
      Client → Server: JSON {"type": "end_recording"} to signal done
      Server → Client: JSON {"type": "transcript", "text": "..."}
      Server → Client: JSON {"type": "response", "text": "...", "intent": "..."}
      Server → Client: binary MP3 audio (if voice mode enabled)
      Server → Client: JSON {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info(f"[voice_ws] Connection opened | conv={conversation_id[:8]}")

    audio_chunks = []
    voice_mode = True   # send audio back by default

    # Demo tenant for WebSocket (in production, validate api_key properly)
    tenant = {
        "id": tenant_id,
        "system_prompt": "You are a helpful customer support agent. Be concise.",
    }

    try:
        while True:
            # Receive either binary audio or JSON control message
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                # Audio chunk received — accumulate
                chunk = message["bytes"]
                audio_chunks.append(chunk)
                logger.debug(f"[voice_ws] Received chunk: {len(chunk)} bytes")

            elif "text" in message:
                # Control message
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "config":
                    # Client sends config at start
                    voice_mode = data.get("voice_mode", True)
                    await websocket.send_json({"type": "ready"})

                elif msg_type == "end_recording":
                    # Client finished recording — process accumulated audio
                    if not audio_chunks:
                        await websocket.send_json({
                            "type": "error",
                            "message": "No audio received"
                        })
                        continue

                    # Combine all chunks
                    full_audio = b"".join(audio_chunks)
                    audio_chunks = []   # reset for next recording
                    logger.info(f"[voice_ws] Processing {len(full_audio)} bytes of audio")

                    # Transcribe
                    await websocket.send_json({"type": "transcribing"})
                    try:
                        transcript = await transcribe_audio(full_audio, "audio.webm")
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"Transcription failed: {e}"})
                        continue

                    # Send transcript back immediately (so user sees what was heard)
                    await websocket.send_json({"type": "transcript", "text": transcript})

                    # Run agent
                    await websocket.send_json({"type": "thinking"})
                    try:
                        result = await run_support_agent(
                            user_input=transcript,
                            tenant_id=tenant["id"],
                            customer_id=str(uuid.uuid4()),
                            conversation_id=conversation_id,
                            system_prompt=tenant["system_prompt"],
                            channel="voice",
                        )
                    except Exception as e:
                        await websocket.send_json({"type": "error", "message": f"Agent error: {e}"})
                        continue

                    # Send text response
                    await websocket.send_json({
                        "type": "response",
                        "text": result["response"],
                        "intent": result["intent"],
                        "confidence": result["confidence"],
                        "language": result["language"],
                    })

                    # Optionally send audio response
                    if voice_mode:
                        try:
                            audio_out = await text_to_speech(result["response"])
                            # Send audio type header first, then binary
                            await websocket.send_json({
                                "type": "audio_start",
                                "mime_type": "audio/mpeg",
                                "size": len(audio_out),
                            })
                            await websocket.send_bytes(audio_out)
                            await websocket.send_json({"type": "audio_end"})
                        except Exception as e:
                            logger.warning(f"[voice_ws] TTS failed: {e}")
                            await websocket.send_json({"type": "tts_unavailable"})

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"[voice_ws] Client disconnected | conv={conversation_id[:8]}")
    except Exception as e:
        logger.error(f"[voice_ws] Error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass