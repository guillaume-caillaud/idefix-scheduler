"""
Tests unitaires du service de détection de conflits.
Ces tests n'utilisent pas la DB : les objets Task sont des simples dataclasses.
"""
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from app.services.conflicts import find_conflicts_for_task, find_day_conflicts, tasks_overlap


@dataclass
class FakeTask:
    id: int
    start_at: datetime
    end_at: datetime


def t(id: int, start_h: int, end_h: int) -> FakeTask:
    return FakeTask(id=id, start_at=datetime(2026, 4, 1, start_h, 0), end_at=datetime(2026, 4, 1, end_h, 0))


# ---------------------------------------------------------------------------
# tasks_overlap
# ---------------------------------------------------------------------------

class TestTasksOverlap:
    def test_no_overlap_sequential(self):
        assert not tasks_overlap(t(1, 9, 11), t(2, 11, 13))

    def test_no_overlap_gap(self):
        assert not tasks_overlap(t(1, 9, 10), t(2, 11, 12))

    def test_partial_overlap(self):
        assert tasks_overlap(t(1, 9, 11), t(2, 10, 12))

    def test_contained_fully(self):
        assert tasks_overlap(t(1, 9, 14), t(2, 10, 12))

    def test_identical_slots(self):
        assert tasks_overlap(t(1, 9, 11), t(2, 9, 11))

    def test_touching_boundary_is_not_overlap(self):
        # end_at == start_at of the other is NOT an overlap (open interval [start, end))
        assert not tasks_overlap(t(1, 9, 11), t(2, 11, 13))


# ---------------------------------------------------------------------------
# find_conflicts_for_task
# ---------------------------------------------------------------------------

class TestFindConflictsForTask:
    def test_no_conflicts(self):
        candidate = t(1, 9, 11)
        existing = [t(2, 11, 13), t(3, 13, 15)]
        assert find_conflicts_for_task(candidate, existing) == []

    def test_one_conflict(self):
        candidate = t(1, 9, 12)
        existing = [t(2, 11, 13), t(3, 14, 16)]
        result = find_conflicts_for_task(candidate, existing)
        assert len(result) == 1
        assert result[0].id == 2

    def test_multiple_conflicts(self):
        candidate = t(1, 9, 17)
        existing = [t(2, 10, 11), t(3, 12, 14), t(4, 16, 18)]
        result = find_conflicts_for_task(candidate, existing)
        assert {r.id for r in result} == {2, 3, 4}

    def test_skips_same_task(self):
        candidate = t(1, 9, 11)
        existing = [t(1, 9, 11), t(2, 10, 12)]  # id=1 is same task
        result = find_conflicts_for_task(candidate, existing)
        assert len(result) == 1
        assert result[0].id == 2


# ---------------------------------------------------------------------------
# find_day_conflicts
# ---------------------------------------------------------------------------

class TestFindDayConflicts:
    def test_no_conflicts(self):
        tasks = [t(1, 9, 11), t(2, 11, 13), t(3, 14, 16)]
        result = find_day_conflicts(tasks, date(2026, 4, 1))
        assert result == []

    def test_two_tasks_overlap(self):
        tasks = [t(1, 9, 12), t(2, 11, 14)]
        result = find_day_conflicts(tasks, date(2026, 4, 1))
        ids = {r.id for r in result}
        assert ids == {1, 2}

    def test_three_way_conflict(self):
        tasks = [t(1, 9, 13), t(2, 10, 14), t(3, 11, 15)]
        result = find_day_conflicts(tasks, date(2026, 4, 1))
        assert {r.id for r in result} == {1, 2, 3}

    def test_only_tasks_on_target_date_considered(self):
        """Tâche d'un autre jour ne doit pas générer de conflit."""
        task_today = FakeTask(
            id=1,
            start_at=datetime(2026, 4, 1, 9, 0),
            end_at=datetime(2026, 4, 1, 11, 0),
        )
        task_tomorrow = FakeTask(
            id=2,
            start_at=datetime(2026, 4, 2, 9, 0),
            end_at=datetime(2026, 4, 2, 11, 0),
        )
        result = find_day_conflicts([task_today, task_tomorrow], date(2026, 4, 1))
        assert result == []
