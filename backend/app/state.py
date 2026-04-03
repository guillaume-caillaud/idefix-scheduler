"""
Global mutable state partagé entre main.py et les routeurs.
Évite les imports circulaires pour l'instance du bot Telegram.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telegram.ext import Application

# Initialisé dans le lifespan de FastAPI, None si le bot n'est pas configuré.
telegram_app: Any = None  # telegram.ext.Application | None
