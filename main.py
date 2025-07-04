from fastapi import FastAPI, Request
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

class BarkEvent(BaseModel):
    device_id: str
    timestamp: float
    volume: float
    frequency: float
    event: str

# Store events in memory for now
bark_events = []

@app.get("/")
def root():
    return {"status": "ok", "barks": len(bark_events)}

@app.post("/bark")
async def receive_bark(event: BarkEvent):
    bark_events.append(event)
    print(f"[{datetime.now()}] BARK: {event}")
    return {"message": "Bark received"}
