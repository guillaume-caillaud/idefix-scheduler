import asyncio
import logging
import secrets
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

import app.database as database
import app.state as state
from app.bot.telegram_bot import build_application
from app.config import settings
from app.routers import admin, alerts, assignments, auth, health, tasks, teams, users

logger = logging.getLogger(__name__)


def _expected_webhook_url() -> str:
    return f"{settings.webhook_url.rstrip('/')}/webhook/telegram"


async def _configure_telegram_webhook() -> None:
    if not state.telegram_app or not settings.webhook_url:
        return

    await state.telegram_app.bot.set_webhook(
        url=_expected_webhook_url(),
        secret_token=settings.webhook_secret,
    )


async def _webhook_self_heal_loop() -> None:
    interval = max(15, settings.telegram_webhook_self_heal_interval_seconds)
    while state.telegram_app and settings.webhook_url:
        try:
            info = await state.telegram_app.bot.get_webhook_info()
            expected_url = _expected_webhook_url()
            needs_repair = info.url != expected_url or bool(info.last_error_message)
            if needs_repair:
                logger.warning(
                    "Telegram webhook drift detected (current=%s, expected=%s, last_error=%s). Reapplying.",
                    info.url,
                    expected_url,
                    info.last_error_message,
                )
                await _configure_telegram_webhook()
                repaired = await state.telegram_app.bot.get_webhook_info()
                logger.info(
                    "Telegram webhook repaired (url=%s, pending=%s)",
                    repaired.url,
                    repaired.pending_update_count,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram webhook self-heal check failed")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.Base.metadata.create_all(bind=database.engine)
    webhook_self_heal_task: asyncio.Task | None = None

    if settings.telegram_bot_token:
        state.telegram_app = build_application(settings.telegram_bot_token)
        await state.telegram_app.initialize()

        if settings.webhook_url:
            # Webhook mode (production): keep webhook registered across restarts.
            await _configure_telegram_webhook()
            await state.telegram_app.start()
            info = await state.telegram_app.bot.get_webhook_info()
            logger.info(
                "Telegram webhook configured at %s (pending=%s)",
                info.url,
                info.pending_update_count,
            )
            webhook_self_heal_task = asyncio.create_task(_webhook_self_heal_loop())
        else:
            # Polling mode fallback (development or localhost)
            await state.telegram_app.start()
            logger.warning("WEBHOOK_URL not set — using polling mode (dev only)")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")

    yield

    if webhook_self_heal_task:
        webhook_self_heal_task.cancel()
        with suppress(asyncio.CancelledError):
            await webhook_self_heal_task

    if state.telegram_app:
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
        logger.warning("Telegram webhook rejected: invalid secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    update = Update.de_json(data, state.telegram_app.bot)
    logger.info("Telegram update received: update_id=%s", getattr(update, "update_id", None))
    try:
        await state.telegram_app.process_update(update)
    except Exception:
        # Avoid endless Telegram retries on transient handler errors.
        logger.exception("Error while processing telegram update_id=%s", getattr(update, "update_id", None))
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "Team Scheduler API"}
