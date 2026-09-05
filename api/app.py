from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent.parent
WEBAPP_DIR = BASE_DIR / "webapp"

app = FastAPI(title="Subscription Scanner API")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "subscription-scanner"}


# Отдаём страницу Mini App
app.mount("/", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")