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
    }

    try:
        wav_bytes = save_as_wav(base64.b64decode(event.audio_base64))
        filename = f"bark_{int(event.timestamp)}_{event.device_id}.wav"

        public_url = upload_wav_to_gcs(wav_bytes, filename)
        print(f"✅ Uploaded to GCS: {public_url}")
        doc["audio_url"] = public_url

    except Exception as e:
        print(f"❌ Failed to decode or save audio: {e}")
        raise e

    db.collection("barks").add(doc)
    print(f"[{datetime.now()}] BARK: {event}")
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


def save_as_wav(decoded_bytes: bytes, sample_rate=10000, sample_width=2):

    # Parse CSV-style raw samples
    samples_str = decoded_bytes.decode("utf-8")
    samples = list(map(int, samples_str.strip().split(",")))

    # Build .wav in memory
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)  # mono
        wf.setsampwidth(sample_width)  # 2 bytes = 16-bit
        wf.setframerate(sample_rate)
        for sample in samples:
            packed = struct.pack("<h", sample)  # little-endian 16-bit
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
