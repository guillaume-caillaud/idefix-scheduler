"""
Tests API pour les affectations : créer, conflits, planning, suppression,
et gestion des droits d'accès.
"""
from datetime import datetime

import pytest

from app import crud


def _task(db, manager_user, start_h=9, end_h=11, required=1, day=1):
    return crud.create_task(
        db,
        title=f"Task {start_h}-{end_h}",
        description=None,
        start_at=datetime(2026, 4, day, start_h, 0),
        end_at=datetime(2026, 4, day, end_h, 0),
        required_people=required,
        created_by=manager_user.id,
        team_id=None,
    )


class TestAssignUser:
    def test_manager_assigns_employee(self, manager_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        resp = manager_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        assert resp.status_code == 200
        assert resp.json()["assignee_id"] == employee_user.id
        assert resp.json()["conflicts"] == []

    def test_employee_assigns_self(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        resp = employee_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        assert resp.status_code == 200

    def test_employee_cannot_assign_other(self, employee_client, db, manager_user, employee_user2):
        task = _task(db, manager_user)
        resp = employee_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user2.id})
        assert resp.status_code == 403

    def test_duplicate_assignment_rejected(self, manager_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        manager_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        resp = manager_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        assert resp.status_code == 409

    def test_assign_nonexistent_task(self, manager_client, db, manager_user, employee_user):
        resp = manager_client.post("/assignments", json={"task_id": 99999, "assignee_id": employee_user.id})
        assert resp.status_code == 404

    def test_assign_to_fully_staffed_task_blocked_for_employee(
        self, employee_client, db, manager_user, employee_user, employee_user2
    ):
        task = _task(db, manager_user, required=1)
        crud.create_assignment(db, task.id, employee_user2.id)
        resp = employee_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        assert resp.status_code == 409

    def test_manager_can_overstaff(self, manager_client, db, manager_user, employee_user, employee_user2):
        task = _task(db, manager_user, required=1)
        manager_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user.id})
        resp = manager_client.post("/assignments", json={"task_id": task.id, "assignee_id": employee_user2.id})
        assert resp.status_code == 200


class TestConflictDetection:
    def test_overlapping_assignment_returns_conflicts(self, manager_client, db, manager_user, employee_user):
        t1 = _task(db, manager_user, start_h=9, end_h=11)
        t2 = _task(db, manager_user, start_h=10, end_h=12)
        manager_client.post("/assignments", json={"task_id": t1.id, "assignee_id": employee_user.id})
        resp = manager_client.post("/assignments", json={"task_id": t2.id, "assignee_id": employee_user.id})
        assert resp.status_code == 200
        conflicts = resp.json()["conflicts"]
        assert len(conflicts) == 1
        assert conflicts[0]["task_id"] == t1.id

    def test_non_overlapping_assignment_no_conflicts(self, manager_client, db, manager_user, employee_user):
        t1 = _task(db, manager_user, start_h=9, end_h=11)
        t2 = _task(db, manager_user, start_h=11, end_h=13)
        manager_client.post("/assignments", json={"task_id": t1.id, "assignee_id": employee_user.id})
        resp = manager_client.post("/assignments", json={"task_id": t2.id, "assignee_id": employee_user.id})
        assert resp.status_code == 200
        assert resp.json()["conflicts"] == []


class TestScheduleAndConflicts:
    def test_my_schedule_returns_assigned_tasks(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        crud.create_assignment(db, task.id, employee_user.id)
        resp = employee_client.get("/assignments/me/schedule", params={"date_value": "2026-04-01"})
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) == 1
        assert resp.json()["tasks"][0]["id"] == task.id

    def test_my_schedule_other_day_is_empty(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        crud.create_assignment(db, task.id, employee_user.id)
        resp = employee_client.get("/assignments/me/schedule", params={"date_value": "2026-04-02"})
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_my_conflicts_endpoint(self, employee_client, db, manager_user, employee_user):
        t1 = _task(db, manager_user, start_h=9, end_h=12)
        t2 = _task(db, manager_user, start_h=11, end_h=14)
        crud.create_assignment(db, t1.id, employee_user.id)
        crud.create_assignment(db, t2.id, employee_user.id)
        resp = employee_client.get("/assignments/me/conflicts", params={"date_value": "2026-04-01"})
        assert resp.status_code == 200
        assert len(resp.json()["conflicts"]) == 2


class TestGetAssignment:
    def test_get_existing_assignment(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        assignment = crud.create_assignment(db, task.id, employee_user.id)
        resp = employee_client.get(f"/assignments/{assignment.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == assignment.id
        assert resp.json()["assignee_id"] == employee_user.id

    def test_get_nonexistent_assignment(self, employee_client):
        resp = employee_client.get("/assignments/99999")
        assert resp.status_code == 404


class TestDeleteAssignment:
    def test_employee_deletes_own_assignment(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        assignment = crud.create_assignment(db, task.id, employee_user.id)
        resp = employee_client.delete(f"/assignments/{assignment.id}")
        assert resp.status_code == 204

    def test_employee_cannot_delete_others_assignment(
        self, employee_client, db, manager_user, employee_user2
    ):
        task = _task(db, manager_user)
        assignment = crud.create_assignment(db, task.id, employee_user2.id)
        resp = employee_client.delete(f"/assignments/{assignment.id}")
        assert resp.status_code == 403

    def test_manager_can_delete_any_assignment(self, manager_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        assignment = crud.create_assignment(db, task.id, employee_user.id)
        resp = manager_client.delete(f"/assignments/{assignment.id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_assignment(self, employee_client):
        resp = employee_client.delete("/assignments/99999")
        assert resp.status_code == 404

    def test_double_delete_returns_404(self, employee_client, db, manager_user, employee_user):
        task = _task(db, manager_user)
        assignment = crud.create_assignment(db, task.id, employee_user.id)
        employee_client.delete(f"/assignments/{assignment.id}")
        resp = employee_client.delete(f"/assignments/{assignment.id}")
        assert resp.status_code == 404


class TestAdminUsers:
    def test_list_all_users(self, admin_client, db, manager_user, employee_user):
        resp = admin_client.get("/users")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_role_employee(self, admin_client, db, manager_user, employee_user):
        resp = admin_client.get("/users", params={"role": "employee"})
        assert resp.status_code == 200
        assert all(u["role"] == "employee" for u in resp.json())

    def test_filter_by_role_manager(self, admin_client, db, manager_user, employee_user):
        resp = admin_client.get("/users", params={"role": "manager"})
        assert resp.status_code == 200
        assert all(u["role"] == "manager" for u in resp.json())

    def test_non_admin_cannot_list_users(self, employee_client):
        # Sans token admin, l'API retourne 401 (bearer absent) ou 403
        resp = employee_client.get("/users")
        assert resp.status_code in (401, 403)
