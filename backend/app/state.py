"""
Global mutable state partagé entre main.py et les routeurs.
Évite les imports circulaires pour l'instance du bot Telegram.
"""
from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING, Any

import secrets

if TYPE_CHECKING:
    from telegram.ext import Application

# Initialisé dans le lifespan de FastAPI, None si le bot n'est pas configuré.
telegram_app: Any = None  # telegram.ext.Application | None


_telegram_login_lock = Lock()
telegram_login_challenges: dict[str, dict[str, Any]] = {}

_admin_login_lock = Lock()
admin_login_attempts: dict[str, dict[str, Any]] = {}


def _now_ts() -> int:
    return int(datetime.now(UTC).timestamp())


def _prune_admin_attempts_locked(record: dict[str, Any], now_ts: int, window_seconds: int) -> None:
    failures = record.get("failures", [])
    record["failures"] = [ts for ts in failures if now_ts - ts <= window_seconds]


def clear_admin_login_attempts() -> None:
    with _admin_login_lock:
        admin_login_attempts.clear()


def check_admin_login_blocked(keys: list[str], window_seconds: int) -> int:
    now_ts = _now_ts()
    retry_after = 0
    with _admin_login_lock:
        for key in keys:
            record = admin_login_attempts.get(key)
            if not record:
                continue
            _prune_admin_attempts_locked(record, now_ts, window_seconds)
            blocked_until = int(record.get("blocked_until", 0))
            if blocked_until > now_ts:
                retry_after = max(retry_after, blocked_until - now_ts)
            elif not record.get("failures"):
                admin_login_attempts.pop(key, None)
    return retry_after


def register_admin_login_failure(
    keys: list[str],
    max_attempts: int,
    window_seconds: int,
    lockout_seconds: int,
) -> int:
    now_ts = _now_ts()
    retry_after = 0
    with _admin_login_lock:
        for key in keys:
            record = admin_login_attempts.setdefault(key, {"failures": [], "blocked_until": 0})
            _prune_admin_attempts_locked(record, now_ts, window_seconds)
            blocked_until = int(record.get("blocked_until", 0))
            if blocked_until > now_ts:
                retry_after = max(retry_after, blocked_until - now_ts)
                continue

            failures = record.setdefault("failures", [])
            failures.append(now_ts)
            if len(failures) >= max_attempts:
                record["failures"] = []
                record["blocked_until"] = now_ts + lockout_seconds
                retry_after = max(retry_after, lockout_seconds)

    return retry_after


def register_admin_login_success(keys: list[str]) -> None:
    with _admin_login_lock:
        for key in keys:
            admin_login_attempts.pop(key, None)


def _cleanup_telegram_login_challenges_locked() -> None:
    now_ts = _now_ts()
    expired_ids = [
        challenge_id
        for challenge_id, payload in telegram_login_challenges.items()
        if payload.get("expires_at", 0) <= now_ts
    ]
    for challenge_id in expired_ids:
        telegram_login_challenges.pop(challenge_id, None)


def create_telegram_login_challenge(ttl_seconds: int) -> str:
    code = f"{secrets.randbelow(100_000_000):08d}"
    with _telegram_login_lock:
        _cleanup_telegram_login_challenges_locked()
        # If this 8-digit code already exists (active challenge), retry once
        if code in telegram_login_challenges:
            code = f"{secrets.randbelow(100_000_000):08d}"
        telegram_login_challenges[code] = {
            "status": "pending",
            "expires_at": _now_ts() + ttl_seconds,
        }
    return code


def approve_telegram_login_challenge(
    challenge_id: str,
    telegram_user_id: str,
    first_name: str,
    last_name: str | None,
    username: str | None,
) -> bool:
    with _telegram_login_lock:
        _cleanup_telegram_login_challenges_locked()
        challenge = telegram_login_challenges.get(challenge_id)
        if not challenge or challenge.get("status") != "pending":
            return False

        challenge["status"] = "approved"
        challenge["telegram_user_id"] = telegram_user_id
        challenge["first_name"] = first_name
        challenge["last_name"] = last_name
        challenge["username"] = username
        challenge["approved_at"] = _now_ts()
        return True


def get_telegram_login_challenge(challenge_id: str) -> dict[str, Any] | None:
    with _telegram_login_lock:
        _cleanup_telegram_login_challenges_locked()
        challenge = telegram_login_challenges.get(challenge_id)
        if not challenge:
            return None
        return dict(challenge)


def pop_telegram_login_challenge(challenge_id: str) -> dict[str, Any] | None:
    with _telegram_login_lock:
        _cleanup_telegram_login_challenges_locked()
        challenge = telegram_login_challenges.pop(challenge_id, None)
        if not challenge:
            return None
        return dict(challenge)
