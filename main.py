from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from typing import List
from google.cloud import firestore
from google.cloud import storage
import base64
import os
import wave
import io
import struct

app = FastAPI()
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
templates = Jinja2Templates(directory="templates")

db = firestore.Client()


class BarkEvent(BaseModel):
    device_id: str
    timestamp: float
    volume: float
    frequency: float
    event: str
    audio_base64: str
    sample_rate: int = 5000
    duration_seconds: int = 2
    num_samples: int = 10000


@app.get("/")
def root(request: Request):
    recent_barks_query = (
        db.collection("barks")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(10)
    )
    snapshots = list(recent_barks_query.stream())
    barks = [snap.to_dict() for snap in snapshots]

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "barks": barks, "now": datetime.now},
    )


@app.post("/bark")
async def receive_bark(event: BarkEvent):
    doc = {
        "device_id": event.device_id,
        "timestamp": event.timestamp,
        "volume": event.volume,
        "frequency": event.frequency,
        "audio_base64": event.audio_base64,
        "event": event.event,
        "sample_rate": event.sample_rate,
        "duration_seconds": event.duration_seconds,
        "num_samples": event.num_samples,
    }

    try:
        wav_bytes = save_as_wav(
            base64.b64decode(event.audio_base64),
            sample_rate=event.sample_rate,
            num_samples=event.num_samples,
        )
        filename = f"bark_{int(event.timestamp)}_{event.device_id}.wav"
        public_url = upload_wav_to_gcs(wav_bytes, filename)
        print(f"✅ Uploaded {event.duration_seconds}s audio to GCS: {public_url}")
        doc["audio_url"] = public_url
    except Exception as e:
        print(f"❌ Failed to decode or save audio: {e}")
        raise e

    db.collection("barks").add(doc)
    print(
        f"[{datetime.now()}] BARK: {event.device_id} - {event.duration_seconds}s audio"
    )
    return {"message": "Bark received and added to firestore"}


@app.get("/barks-json")
def get_barks():
    recent_barks_query = (
        db.collection("barks")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(10)
    )
    snapshots = list(recent_barks_query.stream())
    barks = [snap.to_dict() for snap in snapshots]
    return barks


def save_as_wav(
    decoded_bytes: bytes, sample_rate=5000, num_samples=None, sample_width=2
):
    """
    Convert binary audio data from ESP32 to WAV format.
    Now handles longer audio clips (2 seconds at 5kHz = 10,000 samples)
    """
    # Unpack binary data (2 bytes per sample, little-endian)
    expected_samples = len(decoded_bytes) // 2
    if num_samples and num_samples != expected_samples:
        print(
            f"⚠️  Sample count mismatch: expected {num_samples}, got {expected_samples}"
        )

    samples = struct.unpack(f"<{expected_samples}H", decoded_bytes)

    # Debug info
    print(f"📊 Audio: {len(samples)} samples, {len(samples)/sample_rate:.1f}s duration")
    print(
        f"📊 Range: {min(samples)}-{max(samples)}, Avg: {sum(samples)/len(samples):.1f}"
    )

    # Build .wav in memory
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(sample_width)  # 2 bytes = 16-bit
        wf.setframerate(sample_rate)

        # Convert ESP32 ADC values (0-4095) to 16-bit audio
        for sample in samples:
            # Center around 0 and scale appropriately
            centered = sample - 2048  # Center around 0 (-2048 to +2047)
            scaled = int(centered * 8)  # Scale up for better volume
            scaled = max(-32768, min(32767, scaled))  # Clamp to int16 range

            packed = struct.pack("<h", scaled)
            wf.writeframesraw(packed)

    return buffer.getvalue()


def upload_wav_to_gcs(wav_bytes: bytes, filename: str) -> str:
    bucket_name = "bark-audio-clips"  # ⬅️ Update to your actual bucket name
    gcs_path = f"barks/{filename}"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)

    blob.upload_from_string(wav_bytes, content_type="audio/wav")
    blob.make_public()  # or generate signed URL if you want it private

    return blob.public_url
