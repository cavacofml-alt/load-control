import os

from dotenv import load_dotenv
from fastapi import FastAPI

from api.routes import aircraft, load_control

load_dotenv()

app = FastAPI(title="AWBS Backend", version="0.1.0")
app.include_router(aircraft.router)
app.include_router(load_control.router)


@app.get("/health")
def health():
    return {"status": "ok"}
