"""
backend/app/services/voice.py
Voice pipeline:
  - Speech-to-Text: OpenAI Whisper API (transcribes audio files)
  - Text-to-Speech: ElevenLabs API (converts response text to audio)
"""
from dotenv import load_dotenv
load_dotenv()

import os
import logging
import httpx
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# SPEECH TO TEXT — OpenAI Whisper
# ════════════════════════════════════════════════════════════

async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio using Groq's Whisper API (free, faster than OpenAI).
    Groq hosts whisper-large-v3 at no cost.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in .env")

    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(tmp_path, "rb") as audio_file:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (filename, audio_file, _get_mime_type(filename))},
                    data={
                        "model": "whisper-large-v3",
                        "response_format": "json",
                    },
                )
        response.raise_for_status()
        transcript = response.json().get("text", "").strip()
        logger.info(f"[groq-whisper] Transcribed → '{transcript[:80]}'")
        return transcript

    except httpx.HTTPStatusError as e:
        logger.error(f"[groq-whisper] API error {e.response.status_code}: {e.response.text}")
        raise
    finally:
        os.unlink(tmp_path)


def _get_mime_type(filename: str) -> str:
    """Map file extension to MIME type for Whisper API."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".webm": "audio/webm",
        ".mp4":  "audio/mp4",
        ".wav":  "audio/wav",
        ".mp3":  "audio/mpeg",
        ".ogg":  "audio/ogg",
        ".m4a":  "audio/mp4",
    }
    return mime_map.get(ext, "audio/webm")


# ════════════════════════════════════════════════════════════
# TEXT TO SPEECH — ElevenLabs
# ════════════════════════════════════════════════════════════

# ElevenLabs voice IDs (free tier voices)
ELEVENLABS_VOICES = {
    "aria":    "9BWtsMINqrJLrRacOk9x",   # Aria — warm, professional
    "roger":   "CwhRBWXzGAHq8TQ4Fs17",   # Roger — clear, neutral
    "sarah":   "EXAVITQu4vr4xnSDxMaL",   # Sarah — friendly
    "default": "9BWtsMINqrJLrRacOk9x",   # default to Aria
}


async def text_to_speech(
    text: str,
    voice_id: str = "default",
    model_id: str = "default",
) -> bytes:
    """
    Convert text to speech using gTTS (free, no API key needed).
    Returns MP3 audio bytes.
    """
    import io
    from gtts import gTTS

    # Truncate long responses
    if len(text) > 2500:
        text = text[:2500] + "..."

    tts = gTTS(text=text, lang="en", slow=False)
    
    # Save to bytes buffer instead of file
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    audio_bytes = buf.read()
    
    logger.info(f"[gtts] Generated {len(audio_bytes)} bytes of audio")
    return audio_bytes


async def get_available_voices() -> list[dict]:
    """Fetch available ElevenLabs voices for the account."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return []

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
        )
        response.raise_for_status()

    voices = response.json().get("voices", [])
    return [{"voice_id": v["voice_id"], "name": v["name"]} for v in voices]