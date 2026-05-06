from fastapi import APIRouter

import app.state as state

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def healthcheck():
    return {"status": "ok"}


@router.get("/telegram")
async def telegram_healthcheck():
    if not state.telegram_app:
        return {
            "status": "degraded",
            "telegram_app": "disabled",
            "detail": "Telegram bot non initialisé (token/webhook manquant ou démarrage échoué)",
        }

    me = await state.telegram_app.bot.get_me()
    webhook = await state.telegram_app.bot.get_webhook_info()
    return {
        "status": "ok",
        "telegram_app": "enabled",
        "bot_username": me.username,
        "webhook_url": webhook.url,
        "pending_update_count": webhook.pending_update_count,
        "last_error_date": webhook.last_error_date.isoformat() if webhook.last_error_date else None,
        "last_error_message": webhook.last_error_message,
        "max_connections": webhook.max_connections,
        "ip_address": webhook.ip_address,
    }
