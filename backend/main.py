import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

app = FastAPI(title="AWBS Backend", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
