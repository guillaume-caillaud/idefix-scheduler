import logging
from datetime import date, timedelta

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formatage
# ---------------------------------------------------------------------------

def _format_tasks(items: list[dict], label: str) -> str:
    if not items:
        return f"Aucune tâche pour {label}."
    lines = [f"📅 Planning {label} :"]
    for task in items:
        icon = "✅" if task.get("is_fully_staffed") else "⚠️"
        lines.append(f"{icon} {task['start_at'][11:16]}-{task['end_at'][11:16]} | {task['title']}")
    return "\n".join(lines)


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
        task_dicts = [
            {
                "start_at": t.start_at.isoformat(),
                "end_at": t.end_at.isoformat(),
                "title": t.title,
                "is_fully_staffed": counts.get(t.id, 0) >= t.required_people,
            }
            for t in tasks
        ]
    finally:
        db.close()

    label = "aujourd'hui" if target_date == date.today() else "demain"
    return _format_tasks(task_dicts, label)


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
    application.add_handler(CommandHandler("today", cmd_today))
    application.add_handler(CommandHandler("tomorrow", cmd_tomorrow))
    application.add_handler(CommandHandler("alert", cmd_alert))
    return application
