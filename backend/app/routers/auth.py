import hashlib
import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.config import settings
from app.database import get_db
from app.models import UserRole
from app.security import create_access_token, get_current_user, require_admin, require_assigned_role

router = APIRouter(prefix="/auth", tags=["auth"])


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
def admin_login(payload: schemas.AdminLoginRequest):
    if payload.username != settings.admin_username or payload.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
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
