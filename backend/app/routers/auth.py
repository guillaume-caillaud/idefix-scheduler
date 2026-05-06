import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

import app.state as state
from app import crud, schemas
from app.config import settings
from app.database import get_db
from app.models import UserRole
from app.security import (
    create_access_token,
    get_current_user,
    require_admin,
    require_assigned_role,
    verify_admin_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _admin_login_rate_limit_keys(request: Request, username: str) -> list[str]:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else ""
    if not client_ip:
        client_ip = request.client.host if request.client else "unknown"

    normalized_username = (username or "").strip().lower()[:120]
    return [f"ip:{client_ip}", f"ip_user:{client_ip}:{normalized_username}"]


@router.post("/telegram/challenge", response_model=schemas.TelegramChallengeResponse)
def create_telegram_challenge():
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot non configuré")

    challenge_id = state.create_telegram_login_challenge(settings.telegram_auth_challenge_ttl_seconds)
    bot_username = settings.telegram_bot_username.strip().removeprefix("@")
    deep_link = f"https://t.me/{bot_username}" if bot_username else None
    return schemas.TelegramChallengeResponse(
        challenge_id=challenge_id,
        expires_in=settings.telegram_auth_challenge_ttl_seconds,
        deep_link=deep_link,
    )


@router.post("/telegram/challenge/{challenge_id}/exchange", response_model=schemas.TokenResponse)
def exchange_telegram_challenge(challenge_id: str, db: Session = Depends(get_db)):
    challenge = state.get_telegram_login_challenge(challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="challenge introuvable ou expiré")
    if challenge.get("status") != "approved":
        raise HTTPException(status_code=409, detail="challenge en attente")

    approved = state.pop_telegram_login_challenge(challenge_id)
    if not approved or approved.get("status") != "approved":
        raise HTTPException(status_code=409, detail="challenge déjà consommé")

    full_name = f"{approved.get('first_name', '')} {approved.get('last_name') or ''}".strip()
    telegram_user_id = approved.get("telegram_user_id")
    if not telegram_user_id:
        raise HTTPException(status_code=400, detail="challenge invalide")

    user = crud.upsert_telegram_user(
        db,
        telegram_user_id=str(telegram_user_id),
        name=full_name or "Utilisateur Telegram",
        telegram_username=approved.get("username"),
        default_role=UserRole.pending,
    )
    token = create_access_token(subject=str(user.id), role=user.role.value, token_kind="user")
    return schemas.TokenResponse(access_token=token)


def _validate_telegram_payload(payload: schemas.TelegramLoginRequest) -> None:
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN is not configured")

    now_ts = int(datetime.now(UTC).timestamp())
    if now_ts - payload.auth_date > settings.telegram_auth_max_age_seconds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="telegram auth payload is too old")

    data = {
        "auth_date": str(payload.auth_date),
        "first_name": payload.first_name,
        "id": str(payload.id),
    }
    if payload.last_name:
        data["last_name"] = payload.last_name
    if payload.username:
        data["username"] = payload.username

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, payload.hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid telegram signature")


@router.post("/telegram/login", response_model=schemas.TokenResponse)
def telegram_login(payload: schemas.TelegramLoginRequest, db: Session = Depends(get_db)):
    _validate_telegram_payload(payload)
    full_name = f"{payload.first_name} {payload.last_name or ''}".strip()

    user = crud.upsert_telegram_user(
        db,
        telegram_user_id=str(payload.id),
        name=full_name,
        telegram_username=payload.username,
        default_role=UserRole.pending,
    )
    token = create_access_token(subject=str(user.id), role=user.role.value, token_kind="user")
    return schemas.TokenResponse(access_token=token)


@router.post("/admin/login", response_model=schemas.TokenResponse)
def admin_login(payload: schemas.AdminLoginRequest, request: Request):
    keys = _admin_login_rate_limit_keys(request, payload.username)
    retry_after = state.check_admin_login_blocked(keys, settings.admin_login_window_seconds)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many login attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )

    if not settings.admin_password_hash:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="admin auth not configured")

    username_ok = hmac.compare_digest(payload.username, settings.admin_username)
    password_ok = verify_admin_password(payload.password, settings.admin_password_hash)
    if not username_ok or not password_ok:
        retry_after = state.register_admin_login_failure(
            keys=keys,
            max_attempts=settings.admin_login_max_attempts,
            window_seconds=settings.admin_login_window_seconds,
            lockout_seconds=settings.admin_login_lockout_seconds,
        )
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many login attempts, try again later",
                headers={"Retry-After": str(retry_after)},
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    state.register_admin_login_success(keys)
    token = create_access_token(subject="admin", role="admin", token_kind="admin")
    return schemas.TokenResponse(access_token=token)


@router.patch("/admin/users/{user_id}/role", response_model=schemas.UserOut)
def assign_role(
    user_id: int,
    payload: schemas.AssignRoleRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if payload.role == UserRole.pending:
        raise HTTPException(status_code=400, detail="role must be manager or employee")
    user = crud.set_user_role(db, user_id=user_id, role=payload.role)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.get("/me", response_model=schemas.UserOut)
def me(user=Depends(require_assigned_role)):
    return user


@router.patch("/me", response_model=schemas.UserOut)
def update_my_profile(
    payload: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    updated = crud.update_user_name(db, user.id, payload.name)
    if not updated:
        raise HTTPException(status_code=404, detail="user not found")
    return updated
