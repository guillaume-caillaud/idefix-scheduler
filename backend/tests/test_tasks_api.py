"""
Tests API pour les tâches : création, listing, tâches non remplies, édition.
"""
from datetime import datetime

import pytest

from app import crud


TASK_9_11 = {
    "title": "Morning shift",
    "start_at": "2026-04-01T09:00:00",
    "end_at": "2026-04-01T11:00:00",
    "required_people": 2,
}


class TestCreateTask:
    def test_manager_can_create(self, manager_client):
        resp = manager_client.post("/tasks", json=TASK_9_11)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Morning shift"
        assert data["required_people"] == 2
        assert data["assigned_people"] == 0
        assert data["missing_people"] == 2
        assert data["is_fully_staffed"] is False

    def test_employee_cannot_create(self, employee_client):
        resp = employee_client.post("/tasks", json=TASK_9_11)
        assert resp.status_code == 403

    def test_end_before_start_rejected(self, manager_client):
        payload = {**TASK_9_11, "start_at": "2026-04-01T11:00:00", "end_at": "2026-04-01T09:00:00"}
        resp = manager_client.post("/tasks", json=payload)
        assert resp.status_code == 422

    def test_required_people_zero_rejected(self, manager_client):
        resp = manager_client.post("/tasks", json={**TASK_9_11, "required_people": 0})
        assert resp.status_code == 422


class TestListTasks:
    def test_returns_tasks_for_day(self, manager_client):
        manager_client.post("/tasks", json=TASK_9_11)
        resp = manager_client.get("/tasks", params={"date_value": "2026-04-01"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_staffing_counts_are_present(self, manager_client):
        manager_client.post("/tasks", json=TASK_9_11)
        resp = manager_client.get("/tasks", params={"date_value": "2026-04-01"})
        task = resp.json()[0]
        assert "assigned_people" in task
        assert "missing_people" in task
        assert "is_fully_staffed" in task


class TestUpdateTask:
    def test_manager_can_update_title(self, manager_client):
        create_resp = manager_client.post("/tasks", json=TASK_9_11)
        task_id = create_resp.json()["id"]
        resp = manager_client.patch(f"/tasks/{task_id}", json={"title": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_manager_can_change_required_people(self, manager_client):
        create_resp = manager_client.post("/tasks", json=TASK_9_11)
        task_id = create_resp.json()["id"]
        resp = manager_client.patch(f"/tasks/{task_id}", json={"required_people": 5})
        assert resp.status_code == 200
        assert resp.json()["required_people"] == 5
        assert resp.json()["missing_people"] == 5

    def test_update_nonexistent_task(self, manager_client):
        resp = manager_client.patch("/tasks/99999", json={"title": "Ghost"})
        assert resp.status_code == 404

    def test_employee_cannot_update(self, employee_client, manager_client):
        create_resp = manager_client.post("/tasks", json=TASK_9_11)
        task_id = create_resp.json()["id"]
        resp = employee_client.patch(f"/tasks/{task_id}", json={"title": "Hack"})
        assert resp.status_code == 403


class TestUnfilledTasks:
    def test_new_task_is_unfilled(self, manager_client):
        manager_client.post("/tasks", json=TASK_9_11)
        resp = manager_client.get("/tasks/unfilled", params={"date_value": "2026-04-01"})
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) == 1

    def test_fully_staffed_task_not_in_unfilled(self, manager_client, db, manager_user, employee_user):
        payload = {**TASK_9_11, "required_people": 1}
        create_resp = manager_client.post("/tasks", json=payload)
        task_id = create_resp.json()["id"]
        crud.create_assignment(db, task_id, employee_user.id)
        resp = manager_client.get("/tasks/unfilled", params={"date_value": "2026-04-01"})
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_partially_staffed_task_is_unfilled(self, manager_client, db, manager_user, employee_user):
        create_resp = manager_client.post("/tasks", json=TASK_9_11)  # required=2
        task_id = create_resp.json()["id"]
        crud.create_assignment(db, task_id, employee_user.id)
        resp = manager_client.get("/tasks/unfilled", params={"date_value": "2026-04-01"})
        assert len(resp.json()["tasks"]) == 1
