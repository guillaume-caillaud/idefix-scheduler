from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas, state
from app.bot.telegram_bot import send_notification
from app.database import get_db
from app.models import User, UserRole
from app.security import require_user_or_admin

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", status_code=204)
async def send_alert(
    payload: schemas.AlertRequest,
    db: Session = Depends(get_db),
    auth: tuple[str, User | dict] = Depends(require_user_or_admin),
):
    """
    Envoie une notification Telegram à un ou plusieurs utilisateurs.
    Si un responsable envoie l'alerte, la cible est limitée aux membres de ses équipes.
    Si `user_ids` est absent ou vide:
    - admin: diffusion à tous les bénévoles et responsables
    - responsable: diffusion aux membres de ses équipes
    Nécessite le rôle manager ou admin.
    """
    auth_type, auth_obj = auth
    if auth_type != "admin":
        if not isinstance(auth_obj, User) or auth_obj.role != UserRole.manager:
            raise HTTPException(status_code=403, detail="manager or admin required")

    if not state.telegram_app:
        raise HTTPException(status_code=503, detail="Telegram bot non configuré")

    sender_name = auth_obj.name if isinstance(auth_obj, User) else "Admin"

    if auth_type == "admin":
        if payload.user_ids:
            users = [crud.get_user(db, uid) for uid in payload.user_ids]
            targets = [u for u in users if u and u.role in (UserRole.employee, UserRole.manager)]
        else:
            targets = [
                u for u in crud.list_users(db)
                if u.role in (UserRole.employee, UserRole.manager)
            ]
    else:
        team_targets = crud.list_alert_targets_for_manager(db, auth_obj.id)
        if payload.user_ids:
            requested_ids = set(payload.user_ids)
            targets = [u for u in team_targets if u.id in requested_ids]
        else:
            targets = team_targets

    text = f"🔔 Alerte de {sender_name} :\n{payload.message}"
    for user in targets:
        try:
            await send_notification(state.telegram_app.bot, user.telegram_user_id, text)
        except Exception:
            pass  # Ne pas bloquer si un chat_id est invalide
