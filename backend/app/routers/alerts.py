from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas, state
from app.bot.telegram_bot import send_notification
from app.database import get_db
from app.models import User, UserRole
from app.security import require_manager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", status_code=204)
async def send_alert(
    payload: schemas.AlertRequest,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
):
    """
    Envoie une notification Telegram à un ou plusieurs utilisateurs.
    Si `user_ids` est absent ou vide, le message est diffusé à tous les employés.
    Nécessite le rôle manager.
    """
    if not state.telegram_app:
        raise HTTPException(status_code=503, detail="Telegram bot non configuré")

    if payload.user_ids:
        users = [crud.get_user(db, uid) for uid in payload.user_ids]
        targets = [u for u in users if u and u.role in (UserRole.employee, UserRole.manager)]
    else:
        targets = crud.list_users(db, role=UserRole.employee)

    text = f"🔔 Alerte de {manager.name} :\n{payload.message}"
    for user in targets:
        try:
            await send_notification(state.telegram_app.bot, user.telegram_user_id, text)
        except Exception:
            pass  # Ne pas bloquer si un chat_id est invalide
