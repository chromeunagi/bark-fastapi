from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from typing import List
from google.cloud import firestore

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
        "event": event.event,
    }

    print(f"[{datetime.now()}] BARK: {event}")

    db.collection("barks").add(doc)
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