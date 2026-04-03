from datetime import date

from app import models


def tasks_overlap(task_a: models.Task, task_b: models.Task) -> bool:
    return task_a.start_at < task_b.end_at and task_b.start_at < task_a.end_at


def find_conflicts_for_task(candidate_task: models.Task, existing_tasks: list[models.Task]) -> list[models.Task]:
    return [task for task in existing_tasks if task.id != candidate_task.id and tasks_overlap(candidate_task, task)]


def find_day_conflicts(tasks: list[models.Task], target_date: date) -> list[models.Task]:
    day_tasks = [t for t in tasks if t.start_at.date() <= target_date <= t.end_at.date()]
    conflicts: dict[int, models.Task] = {}
    for idx, task_a in enumerate(day_tasks):
        for task_b in day_tasks[idx + 1 :]:
            if tasks_overlap(task_a, task_b):
                conflicts[task_a.id] = task_a
                conflicts[task_b.id] = task_b
    return list(conflicts.values())
