from fastapi.testclient import TestClient

from app import crud
from app.database import get_db
from app.main import app
from app.security import require_manager_or_admin


def test_manager_can_be_added_as_team_member(db, manager_user):
    team = crud.create_team(db, name="Equipe A", created_by=manager_user.id)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_manager_or_admin] = lambda: (
        "admin",
        {"sub": "admin", "role": "admin", "kind": "admin"},
    )

    client = TestClient(app, raise_server_exceptions=True)
    try:
        resp = client.post(f"/teams/{team.id}/members", json={"user_ids": [manager_user.id]})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        member_ids = [m["id"] for m in data["members"]]
        assert manager_user.id in member_ids

        manager_member = [m for m in data["members"] if m["id"] == manager_user.id][0]
        assert manager_member["role"] == "manager"
    finally:
        app.dependency_overrides.clear()
