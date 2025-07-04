from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from typing import List

app = FastAPI()
templates = Jinja2Templates(directory="templates")


class BarkEvent(BaseModel):
    device_id: str
    timestamp: float
    volume: float
    frequency: float
    event: str


bark_events: List[BarkEvent] = []


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "barks": bark_events[-10:], "now": datetime.now},
    )


@app.post("/bark")
async def receive_bark(event: BarkEvent):
    bark_events.append(event)
    print(f"[{datetime.now()}] BARK: {event}")
    return {"message": "Bark received"}
