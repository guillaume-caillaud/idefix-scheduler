import logging
from datetime import date, timedelta

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import app.state as state
from app.config import settings

logger = logging.getLogger(__name__)

_awaiting_login_code_chats: set[int] = set()


# ---------------------------------------------------------------------------
# Formatage
# ---------------------------------------------------------------------------

def _format_tasks(items: list[dict], label: str, include_date: bool = False) -> str:
    if not items:
        return f"Aucune tâche pour {label}."
    lines = [f"📅 Planning {label} :"]
    for task in items:
        icon = "✅" if task.get("is_fully_staffed") else "⚠️"
        date_prefix = f"{task['start_at'][:10]} " if include_date else ""
        lines.append(f"{icon} {date_prefix}{task['start_at'][11:16]}-{task['end_at'][11:16]} | {task['title']}")
        others = task.get("other_assignees", [])
        if others:
            lines.append(f"   👥 Avec: {', '.join(others)}")
    return "\n".join(lines)


def _help_text() -> str:
    return "\n".join(
        [
            "🤖 Commandes disponibles :",
            "- /login : connecter ton compte avec le code à 8 chiffres affiché sur le site.",
            "- /today : afficher tes tâches d'aujourd'hui.",
            "- /tomorrow : afficher tes tâches de demain.",
            "- /next : afficher tes 5 prochaines tâches.",
            "- /help : afficher cette aide.",
            "- /alert <message> : envoyer une alerte (managers uniquement).",
        ]
    )


# ---------------------------------------------------------------------------
# Récupération du planning via l'API interne
# ---------------------------------------------------------------------------

async def _get_schedule_text(telegram_user_id: str, target_date: date) -> str:
    # Import local pour éviter les imports circulaires au démarrage
    from app import crud
    from app.database import SessionLocal
    from app.models import UserRole

    db = SessionLocal()
    try:
        user = crud.get_user_by_telegram_user_id(db, telegram_user_id)
        if not user or user.role == UserRole.pending:
            return "Utilisateur non reconnu ou rôle non encore assigné. Contacte un administrateur."

        tasks = crud.get_user_tasks_for_day(db, user.id, target_date)
        counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
        assignees = crud.get_assignees_by_task(db, [t.id for t in tasks])
        task_dicts = [
            {
                "start_at": t.start_at.isoformat(),
                "end_at": t.end_at.isoformat(),
                "title": t.title,
                "is_fully_staffed": counts.get(t.id, 0) >= t.required_people,
                "other_assignees": [u.name for u in assignees.get(t.id, []) if u.id != user.id],
            }
            for t in tasks
        ]
    finally:
        db.close()

    label = "aujourd'hui" if target_date == date.today() else "demain"
    return _format_tasks(task_dicts, label)


async def _get_next_tasks_text(telegram_user_id: str) -> str:
    from app import crud
    from app.database import SessionLocal
    from app.models import UserRole

    db = SessionLocal()
    try:
        user = crud.get_user_by_telegram_user_id(db, telegram_user_id)
        if not user or user.role == UserRole.pending:
            return "Utilisateur non reconnu ou rôle non encore assigné. Contacte un administrateur."

        tasks = crud.get_next_user_tasks(db, user.id, limit=5)
        counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
        assignees = crud.get_assignees_by_task(db, [t.id for t in tasks])
        task_dicts = [
            {
                "start_at": t.start_at.isoformat(),
                "end_at": t.end_at.isoformat(),
                "title": t.title,
                "is_fully_staffed": counts.get(t.id, 0) >= t.required_people,
                "other_assignees": [u.name for u in assignees.get(t.id, []) if u.id != user.id],
            }
            for t in tasks
        ]
    finally:
        db.close()

    return _format_tasks(task_dicts, "des prochaines tâches", include_date=True)


# ---------------------------------------------------------------------------
# Gestionnaires de commandes
# ---------------------------------------------------------------------------

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return
    text = await _get_schedule_text(str(update.effective_chat.id), date.today())
    await update.message.reply_text(text)


async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return
    text = await _get_schedule_text(str(update.effective_chat.id), date.today() + timedelta(days=1))
    await update.message.reply_text(text)


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return
    text = await _get_next_tasks_text(str(update.effective_chat.id))
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(_help_text())


async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /alert <message>
    Réservé aux managers : diffuse un message à tous les employés.
    """
    if not update.effective_chat or not update.message:
        return

    message_text = " ".join(context.args) if context.args else ""
    if not message_text:
        await update.message.reply_text("Usage : /alert <message>")
        return

    from app import crud
    from app.database import SessionLocal
    from app.models import UserRole

    db = SessionLocal()
    try:
        sender = crud.get_user_by_telegram_user_id(db, str(update.effective_chat.id))
        if not sender or sender.role != UserRole.manager:
            await update.message.reply_text("⛔ Seuls les managers peuvent envoyer des alertes.")
            return

        employees = crud.list_users(db, role=UserRole.employee)
        text = f"🔔 Alerte de {sender.name} :\n{message_text}"
        sent = 0
        for emp in employees:
            try:
                await context.bot.send_message(chat_id=int(emp.telegram_user_id), text=text)
                sent += 1
            except Exception as exc:
                logger.warning("Impossible d'envoyer à %s : %s", emp.telegram_user_id, exc)

        await update.message.reply_text(f"✅ Alerte envoyée à {sent} employé(s).")
    finally:
        db.close()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    arg = context.args[0] if context.args else ""
    if arg.startswith("login_"):
        challenge_id = arg.removeprefix("login_").strip()
        user = update.effective_user
        if not challenge_id or not user:
            await update.message.reply_text("❌ Lien de connexion invalide.")
            return

        approved = state.approve_telegram_login_challenge(
            challenge_id=challenge_id,
            telegram_user_id=str(user.id),
            first_name=user.first_name or "",
            last_name=user.last_name,
            username=user.username,
        )
        if not approved:
            await update.message.reply_text("❌ Ce lien est expiré ou déjà utilisé.")
            return

        await update.message.reply_text(
            "✅ Connexion validée. Tu peux revenir sur le site, la session va se finaliser automatiquement."
        )
        return

    await update.message.reply_text(
        "Bonjour ! Utilise /login pour te connecter puis /help pour voir toutes les commandes."
    )


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    _awaiting_login_code_chats.add(update.effective_chat.id)
    await update.message.reply_text(
        "🔐 Envoie ton code de connexion à 8 chiffres (valable 5 minutes)."
    )


async def handle_login_code_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    if chat_id not in _awaiting_login_code_chats:
        return

    user = update.effective_user
    code = (update.message.text or "").strip()

    if not user:
        await update.message.reply_text("❌ Impossible de récupérer l'utilisateur Telegram.")
        return

    if not (len(code) == 8 and code.isdigit()):
        await update.message.reply_text("❌ Code invalide. Envoie exactement 8 chiffres.")
        return

    approved = state.approve_telegram_login_challenge(
        challenge_id=code,
        telegram_user_id=str(user.id),
        first_name=user.first_name or "",
        last_name=user.last_name,
        username=user.username,
    )

    if not approved:
        await update.message.reply_text("❌ Code expiré, inconnu, ou déjà utilisé. Génère un nouveau code sur le site.")
        return

    _awaiting_login_code_chats.discard(chat_id)
    await update.message.reply_text(
        "✅ Connexion validée. Tu peux revenir sur le site, la session va se finaliser automatiquement."
    )


# ---------------------------------------------------------------------------
# Envoi d'une notification depuis le code Python (utilisé par POST /alerts)
# ---------------------------------------------------------------------------

async def send_notification(bot: Bot, telegram_user_id: str, text: str) -> None:
    await bot.send_message(chat_id=int(telegram_user_id), text=text)


# ---------------------------------------------------------------------------
# Constructeur de l'Application (appelé par le lifespan FastAPI)
# ---------------------------------------------------------------------------

def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("login", cmd_login))
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("tomorrow", cmd_tomorrow))
    application.add_handler(CommandHandler("next", cmd_next))
    application.add_handler(CommandHandler("alert", cmd_alert))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_login_code_message))
    return application
