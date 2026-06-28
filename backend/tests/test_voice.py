"""
scripts/test_voice.py
Tests the voice transcription endpoint with a generated test audio file.
Requires: pip install gtts requests

Usage:
    python scripts/test_voice.py
"""

import requests
import os
import sys
import tempfile

API_URL = "http://localhost:8000"
API_KEY = "acme_test_key_abc123"


def test_transcribe_endpoint():
    """Test the HTTP voice upload endpoint."""
    print("=" * 50)
    print("Voice Pipeline Test")
    print("=" * 50)

    # Generate a test audio file using gTTS (free, no API key)
    try:
        from gtts import gTTS
        tts = gTTS("Where is my order? I need help tracking my package.", lang="en")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tts.save(f.name)
            audio_path = f.name
        print(f"✅ Generated test audio: {audio_path}")
    except ImportError:
        print("gTTS not installed. Install with: pip install gtts")
        print("Alternatively, provide your own audio file.")
        sys.exit(1)

    # Test transcription endpoint
    print("\n[1] Testing POST /api/v1/voice/transcribe ...")
    with open(audio_path, "rb") as f:
        response = requests.post(
            f"{API_URL}/api/v1/voice/transcribe",
            headers={"X-API-Key": API_KEY},
            files={"audio": ("test.mp3", f, "audio/mpeg")},
            data={"voice_response": "false"},
            timeout=200,
        )

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Transcript : {data.get('transcript')}")
        print(f"✅ Intent     : {data.get('intent')}")
        print(f"✅ Response   : {data.get('response', '')[:100]}...")
        print(f"✅ Language   : {data.get('language')}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

    # Test TTS endpoint
    print("\n[2] Testing GET /api/v1/voice/tts ...")
    response = requests.get(
        f"{API_URL}/api/v1/voice/tts",
        headers={"X-API-Key": API_KEY},
        params={"text": "Hello! How can I help you today?"},
        timeout=15,
    )

    if response.status_code == 200:
        out_path = "/tmp/tts_test_output.mp3"
        with open(out_path, "wb") as f:
            f.write(response.content)
        print(f"✅ TTS audio saved to {out_path} ({len(response.content)} bytes)")
        print("   Play it to verify the audio sounds correct.")
    else:
        print(f"❌ TTS error {response.status_code}: {response.text[:200]}")

    # Cleanup
    os.unlink(audio_path)
    print("\n✅ Voice pipeline test complete!")


def test_whatsapp_webhook():
    """Simulate a Twilio WhatsApp webhook POST."""
    print("\n[3] Testing POST /webhooks/whatsapp (Twilio simulation)...")

    # This mimics exactly what Twilio sends
    twilio_payload = {
        "MessageSid": "SMtest123456789",
        "Body": "I want to return my order and get a refund",
        "From": "whatsapp:+923001234567",
        "To": "whatsapp:+14155238886",
        "ProfileName": "Test User",
        "NumMedia": "0",
    }

    response = requests.post(
        f"{API_URL}/webhooks/whatsapp",
        data=twilio_payload,   # form-encoded, just like Twilio sends
        timeout=30,
    )

    if response.status_code == 200:
        print(f"✅ Webhook handled (status 200)")
        print(f"   Response body: '{response.text}' (empty = correct, reply sent via REST API)")
        print("   Check your WhatsApp sandbox to see the reply!")
    else:
        print(f"❌ Webhook error {response.status_code}: {response.text}")


if __name__ == "__main__":
    test_transcribe_endpoint()
    test_whatsapp_webhook()