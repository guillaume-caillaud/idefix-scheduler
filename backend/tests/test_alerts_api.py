from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.state as state
from app import crud
from app.database import get_db
from app.main import app
from app.models import UserRole
from app.security import require_user_or_admin


def test_manager_broadcast_alert_targets_only_managed_team_members(db, manager_user, employee_user):
    other_manager = crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_manager_2",
        name="Other Manager",
        telegram_username="other_manager",
        default_role=UserRole.manager,
    )
    other_employee = crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_employee_2",
        name="Other Employee",
        telegram_username="other_employee",
        default_role=UserRole.employee,
    )

    team = crud.create_team(db, name="Equipe A", created_by=manager_user.id)
    crud.add_users_to_team(db, team.id, [manager_user.id, employee_user.id])

    other_team = crud.create_team(db, name="Equipe B", created_by=other_manager.id)
    crud.add_users_to_team(db, other_team.id, [other_manager.id, other_employee.id])

    sent_chat_ids: list[str] = []

    async def fake_send_notification(_bot, chat_id: str, _text: str):
        sent_chat_ids.append(chat_id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_user_or_admin] = lambda: ("manager", manager_user)

    original_telegram_app = state.telegram_app

    import app.routers.alerts as alerts_router

    saved_send_notification = alerts_router.send_notification
    state.telegram_app = SimpleNamespace(bot=object())
    alerts_router.send_notification = fake_send_notification

    client = TestClient(app, raise_server_exceptions=True)
    try:
        resp = client.post("/alerts", json={"message": "Message global"})
        assert resp.status_code == 204, resp.text

        assert manager_user.telegram_user_id in sent_chat_ids
        assert employee_user.telegram_user_id in sent_chat_ids
        assert other_manager.telegram_user_id not in sent_chat_ids
        assert other_employee.telegram_user_id not in sent_chat_ids
    finally:
        alerts_router.send_notification = saved_send_notification
        state.telegram_app = original_telegram_app
        app.dependency_overrides.clear()


def test_admin_broadcast_alert_targets_all_employees_and_managers(db, manager_user, employee_user):
    pending_user = crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_pending_1",
        name="Pending User",
        telegram_username="pending_user",
        default_role=UserRole.pending,
    )

    sent_chat_ids: list[str] = []

    async def fake_send_notification(_bot, chat_id: str, _text: str):
        sent_chat_ids.append(chat_id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_user_or_admin] = lambda: ("admin", {"sub": "admin", "role": "admin", "kind": "admin"})

    original_telegram_app = state.telegram_app

    import app.routers.alerts as alerts_router

    saved_send_notification = alerts_router.send_notification
    state.telegram_app = SimpleNamespace(bot=object())
    alerts_router.send_notification = fake_send_notification

    client = TestClient(app, raise_server_exceptions=True)
    try:
        resp = client.post("/alerts", json={"message": "Message global"})
        assert resp.status_code == 204, resp.text

        assert manager_user.telegram_user_id in sent_chat_ids
        assert employee_user.telegram_user_id in sent_chat_ids
        assert pending_user.telegram_user_id not in sent_chat_ids
    finally:
        alerts_router.send_notification = saved_send_notification
        state.telegram_app = original_telegram_app
        app.dependency_overrides.clear()
