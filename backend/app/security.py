from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.database import get_db
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(subject: str, role: str, token_kind: str = "user") -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "kind": token_kind,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc


def _extract_payload(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return decode_token(credentials.credentials)


def require_admin(payload: dict = Depends(_extract_payload)) -> dict:
    if payload.get("kind") != "admin" and payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin token required")
    return payload


def get_current_user(
    payload: dict = Depends(_extract_payload),
    db: Session = Depends(get_db),
) -> User:
    if payload.get("kind") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token") from exc

    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_assigned_role(user: User = Depends(get_current_user)) -> User:
    if user.role == UserRole.pending:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role not assigned yet")
    return user


def require_manager(user: User = Depends(require_assigned_role)) -> User:
    if user.role != UserRole.manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="manager role required")
    return user


def require_manager_or_admin(
    payload: dict = Depends(_extract_payload),
    db: Session = Depends(get_db),
) -> tuple[str, User | dict]:
    if payload.get("kind") == "admin" and payload.get("role") == "admin":
        return ("admin", payload)

    if payload.get("kind") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token") from exc

    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if user.role != UserRole.manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="manager or admin required")

    return ("manager", user)


def require_user_or_admin(
    payload: dict = Depends(_extract_payload),
    db: Session = Depends(get_db),
) -> tuple[str, User | dict]:
    if payload.get("kind") == "admin":
        return ("admin", payload)

    if payload.get("kind") != "user":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid user token") from exc

    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    if user.role == UserRole.pending:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role not assigned yet")

    return ("user", user)
