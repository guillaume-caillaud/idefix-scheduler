from datetime import UTC, datetime, timedelta
import base64
import hashlib
import hmac
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import crud
from app.config import settings
from app.database import get_db
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def hash_admin_password(password: str, iterations: int = 390_000) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    derived_b64 = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_sha256${iterations}${salt_b64}${derived_b64}"


def verify_admin_password(password: str, encoded_hash: str) -> bool:
    # Expected format: pbkdf2_sha256$<iterations>$<salt_b64>$<derived_key_b64>
    try:
        algorithm, iterations_str, salt_b64, expected_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        expected = base64.b64decode(expected_b64.encode("ascii"), validate=True)
    except (ValueError, TypeError, base64.binascii.Error):
        return False

    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived, expected)


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
