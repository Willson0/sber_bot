"""
FastAPI-сервер для Telegram Mini App «Полная аналитика подписок».

Ничего не пересчитывает с нуля бизнес-логикой парсинга — переиспользует
УЖЕ сохранённые ботом данные из MySQL (таблица statements) и считает по ним
агрегаты для графиков через тот же chart_generator, что и бот. Один
источник правды.

Запуск:
    uvicorn webapp.server:app --host 0.0.0.0 --port 8080

Важно: запускать из КОРНЯ проекта (там же, где bot.py / database.py),
чтобы сработали импорты `database`, `chart_generator` и т.д.
"""
import os
import sys
from pathlib import Path

# Позволяем импортировать модули из корня проекта, даже если uvicorn
# запущен из другой директории.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import BOT_TOKEN
from database import get_statement, init_db, close_pool
from webapp.tg_auth import validate_init_data, InitDataError
from webapp.analytics import build_analytics

app = FastAPI(title="Subscriptions Analytics WebApp")

# Mini App грузится с домена Telegram, поэтому CORS открыт на чтение.
# Защита строится не на CORS, а на проверке initData (см. ниже).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

STATIC_DIR = ROOT / "webapp" / "static"


@app.on_event("startup")
async def _startup():
    await init_db()


@app.on_event("shutdown")
async def _shutdown():
    await close_pool()


@app.get("/")
async def index():
    """Отдаём саму страницу Mini App."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/analytics/{statement_id}")
async def analytics(statement_id: int, x_init_data: str = Header(default="")):
    """
    Главный эндпоинт. Требует заголовок X-Init-Data (Telegram.WebApp.initData).
    Проверяет подпись, затем — что запрошенная выписка принадлежит
    именно этому пользователю. Иначе 403.
    """
    try:
        payload = validate_init_data(x_init_data, BOT_TOKEN)
    except InitDataError as e:
        raise HTTPException(status_code=401, detail=f"auth failed: {e}")

    tg_user = payload.get("user") or {}
    tg_user_id = tg_user.get("id")
    if tg_user_id is None:
        raise HTTPException(status_code=401, detail="no user in init_data")

    statement = await get_statement(statement_id)
    if statement is None:
        raise HTTPException(status_code=404, detail="statement not found")

    # КЛЮЧЕВАЯ проверка доступа: выписку может смотреть только её владелец.
    if int(statement["user_id"]) != int(tg_user_id):
        raise HTTPException(status_code=403, detail="forbidden")

    data = build_analytics(statement)
    return JSONResponse(data)
