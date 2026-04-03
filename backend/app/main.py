import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

import app.database as database
import app.state as state
from app.bot.telegram_bot import build_application
from app.config import settings
from app.routers import admin, alerts, assignments, auth, health, tasks, teams, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)

    if settings.telegram_bot_token and settings.webhook_url:
        state.telegram_app = build_application(settings.telegram_bot_token)
        await state.telegram_app.initialize()
        await state.telegram_app.bot.set_webhook(
            url=f"{settings.webhook_url.rstrip('/')}/webhook/telegram",
            secret_token=settings.webhook_secret,
        )
        await state.telegram_app.start()
        logger.info("Telegram webhook configured at %s", settings.webhook_url)
    else:
        logger.warning("WEBHOOK_URL or TELEGRAM_BOT_TOKEN not set — bot disabled")

    yield

    if state.telegram_app:
        await state.telegram_app.bot.delete_webhook()
        await state.telegram_app.stop()
        await state.telegram_app.shutdown()
        state.telegram_app = None


app = FastAPI(title="Team Scheduler API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(tasks.router)
app.include_router(assignments.router)
app.include_router(alerts.router)


@app.post("/webhook/telegram", include_in_schema=False)
async def telegram_webhook(request: Request):
    if not state.telegram_app:
        raise HTTPException(status_code=503, detail="Bot non configuré")

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not settings.webhook_secret or not secrets.compare_digest(secret, settings.webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    update = Update.de_json(data, state.telegram_app.bot)
    await state.telegram_app.process_update(update)
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "Team Scheduler API"}
