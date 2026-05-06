from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import Task, User, UserRole
from app.security import require_assigned_role
from app.services.conflicts import find_conflicts_for_task, find_day_conflicts

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("", response_model=schemas.AssignmentOut)
def assign_user(
    payload: schemas.AssignmentCreate,
    db: Session = Depends(get_db),
    requester: User = Depends(require_assigned_role),
):
    assignee = crud.get_user(db, payload.assignee_id)
    if not assignee or assignee.role not in (UserRole.employee, UserRole.manager):
        raise HTTPException(status_code=400, detail="assignee must be employee or manager")

    if requester.role != UserRole.manager and requester.id != payload.assignee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only managers can assign another user",
        )

    task = db.get(Task, payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    current_count = crud.get_assignment_count_by_task(db, [task.id]).get(task.id, 0)
    if current_count >= task.required_people and requester.role != UserRole.manager:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="task is already fully staffed",
        )

    try:
        assignment = crud.create_assignment(db, payload.task_id, payload.assignee_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="user already assigned to this task")

    user_tasks = crud.get_user_tasks_for_day(db, payload.assignee_id, task.start_at.date())
    overlaps = find_conflicts_for_task(task, user_tasks)
    return schemas.AssignmentOut(
        id=assignment.id,
        task_id=assignment.task_id,
        assignee_id=assignment.assignee_id,
        conflicts=[
            schemas.ConflictItem(
                task_id=t.id,
                title=t.title,
                start_at=t.start_at,
                end_at=t.end_at,
            )
            for t in overlaps
        ],
    )


@router.get("/me/schedule", response_model=schemas.DayScheduleResponse)
def my_schedule(
    date_value: date,
    db: Session = Depends(get_db),
    user: User = Depends(require_assigned_role),
):
    tasks = crud.get_user_tasks_for_day(db, user.id, date_value)
    counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
    assignees_by_task = crud.get_assignees_by_task(db, [t.id for t in tasks])
    teams_by_id = _get_teams_by_id(db, tasks)
    my_assignment_ids = crud.get_assignment_id_for_user_by_tasks(db, user.id, [t.id for t in tasks])
    return schemas.DayScheduleResponse(
        user_id=user.id,
        date=date_value,
        tasks=[
            _enrich_task(task, counts.get(task.id, 0), assignees_by_task.get(task.id, []), teams_by_id, my_assignment_ids.get(task.id))
            for task in tasks
        ],
    )


@router.get("/me/conflicts", response_model=schemas.ConflictResponse)
def my_conflicts(
    date_value: date,
    db: Session = Depends(get_db),
    user: User = Depends(require_assigned_role),
):
    tasks = crud.get_user_tasks_for_day(db, user.id, date_value)
    conflicts = find_day_conflicts(tasks, date_value)
    return schemas.ConflictResponse(
        user_id=user.id,
        date=date_value,
        conflicts=[
            schemas.ConflictItem(task_id=t.id, title=t.title, start_at=t.start_at, end_at=t.end_at)
            for t in conflicts
        ],
    )


@router.get("/telegram/{telegram_user_id}/schedule", response_model=schemas.DayScheduleResponse)
def telegram_schedule(telegram_user_id: str, date_value: date, db: Session = Depends(get_db)):
    user = crud.get_user_by_telegram_user_id(db, telegram_user_id)
    if not user or user.role == UserRole.pending:
        raise HTTPException(status_code=404, detail="user not found")
    tasks = crud.get_user_tasks_for_day(db, user.id, date_value)
    counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
    assignees_by_task = crud.get_assignees_by_task(db, [t.id for t in tasks])
    teams_by_id = _get_teams_by_id(db, tasks)
    return schemas.DayScheduleResponse(
        user_id=user.id,
        date=date_value,
        tasks=[
            _enrich_task(task, counts.get(task.id, 0), assignees_by_task.get(task.id, []), teams_by_id)
            for task in tasks
        ],
    )


@router.get("/{assignment_id}", response_model=schemas.AssignmentInfo)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_assigned_role),
):
    assignment = crud.get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="assignment not found")
    return assignment


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    requester: User = Depends(require_assigned_role),
):
    assignment = crud.get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="assignment not found")
    if requester.role != UserRole.manager and requester.id != assignment.assignee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="cannot remove another user's assignment",
        )
    crud.delete_assignment(db, assignment_id)


def _get_teams_by_id(db: Session, tasks) -> dict:
    team_ids = {t.team_id for t in tasks if t.team_id is not None}
    if not team_ids:
        return {}
    return {team.id: team for team in [crud.get_team(db, tid) for tid in team_ids] if team}


def _enrich_task(task: Task, assigned_people: int, assignees: list[User], teams_by_id: dict | None = None, my_assignment_id: int | None = None) -> schemas.TaskOut:
    missing_people = max(task.required_people - assigned_people, 0)
    team_name = None
    if task.team_id and teams_by_id:
        team = teams_by_id.get(task.team_id)
        team_name = team.name if team else None
    return schemas.TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        start_at=task.start_at,
        end_at=task.end_at,
        required_people=task.required_people,
        created_by=task.created_by,
        team_id=task.team_id,
        assigned_people=assigned_people,
        missing_people=missing_people,
        is_fully_staffed=missing_people == 0,
        assigned_users=[
            schemas.TaskAssigneeOut(id=user.id, name=user.name, role=user.role)
            for user in assignees
        ],
        team_name=team_name,
        my_assignment_id=my_assignment_id,
    )
