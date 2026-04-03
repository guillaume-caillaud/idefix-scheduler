from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import User, UserRole
from app.security import require_manager, require_manager_or_admin, require_user_or_admin

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=schemas.TaskOut)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    manager: User = Depends(require_manager),
):
    team_id = _resolve_team_id_for_manager_create(db, manager, payload.team_id)

    task = crud.create_task(
        db,
        title=payload.title,
        description=payload.description,
        start_at=payload.start_at,
        end_at=payload.end_at,
        required_people=payload.required_people,
        created_by=manager.id,
        team_id=team_id,
    )
    return enrich_task(task, 0, [])


@router.patch("/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    team_id = _resolve_team_id_for_update(db, auth_ctx, payload)

    try:
        task = crud.update_task(
            db,
            task_id=task_id,
            title=payload.title,
            description=payload.description,
            start_at=payload.start_at,
            end_at=payload.end_at,
            required_people=payload.required_people,
            team_id=team_id,
            team_id_provided="team_id" in payload.model_fields_set,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    assigned = crud.get_assignment_count_by_task(db, [task.id]).get(task.id, 0)
    assignees = crud.get_assignees_by_task(db, [task.id]).get(task.id, [])
    return enrich_task(task, assigned, assignees)


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
    date_value: date,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_user_or_admin),
):
    actor_kind, actor = auth_ctx
    if team_id is not None:
        if actor_kind == "user":
            _assert_team_access(db, actor, team_id)
        tasks = crud.list_tasks_for_day_for_team(db, date_value, team_id)
    else:
        tasks = crud.list_tasks_for_day(db, date_value)

    counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
    assignees_by_task = crud.get_assignees_by_task(db, [t.id for t in tasks])
    return [
        enrich_task(task, counts.get(task.id, 0), assignees_by_task.get(task.id, []))
        for task in tasks
    ]


@router.get("/unfilled", response_model=schemas.UnfilledTasksResponse)
def unfilled_tasks(
    date_value: date,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_user_or_admin),
):
    actor_kind, actor = auth_ctx
    if team_id is not None:
        if actor_kind == "user":
            _assert_team_access(db, actor, team_id)
        tasks = crud.list_unfilled_tasks_for_day_for_team(db, date_value, team_id)
    else:
        tasks = crud.list_unfilled_tasks_for_day(db, date_value)

    counts = crud.get_assignment_count_by_task(db, [t.id for t in tasks])
    assignees_by_task = crud.get_assignees_by_task(db, [t.id for t in tasks])
    enriched = [
        enrich_task(task, counts.get(task.id, 0), assignees_by_task.get(task.id, []))
        for task in tasks
    ]
    return schemas.UnfilledTasksResponse(date=date_value, tasks=enriched)


def enrich_task(task, assigned_people: int, assignees: list[User]) -> schemas.TaskOut:
    missing_people = max(task.required_people - assigned_people, 0)
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
    )


def _assert_team_access(db: Session, user: User, team_id: int) -> None:
    team = crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")

    if user.role == UserRole.manager and not crud.is_team_managed_by(db, team_id, user.id):
        raise HTTPException(status_code=403, detail="team access denied")

    if user.role == UserRole.employee and not crud.is_user_in_team(db, user.id, team_id):
        raise HTTPException(status_code=403, detail="team access denied")


def _resolve_team_id_for_manager_create(
    db: Session,
    manager: User,
    requested_team_id: int | None,
) -> int | None:
    if requested_team_id is not None:
        if not crud.is_team_managed_by(db, requested_team_id, manager.id):
            raise HTTPException(status_code=403, detail="manager can only create tasks for managed teams")
        return requested_team_id

    managed_teams = crud.list_teams_managed_by(db, manager.id)
    if len(managed_teams) == 0:
        raise HTTPException(status_code=400, detail="manager must create a team before creating tasks")
    if len(managed_teams) > 1:
        raise HTTPException(status_code=400, detail="manager must specify team_id when managing multiple teams")
    return managed_teams[0].id


def _resolve_team_id_for_update(
    db: Session,
    auth_ctx: tuple[str, User | dict],
    payload: schemas.TaskUpdate,
) -> int | None:
    if "team_id" not in payload.model_fields_set:
        return None

    requested_team_id = payload.team_id
    actor_kind, actor = auth_ctx
    if actor_kind == "admin":
        return requested_team_id

    manager = actor
    if requested_team_id is None:
        raise HTTPException(status_code=403, detail="manager cannot remove task team association")

    if not crud.is_team_managed_by(db, requested_team_id, manager.id):
        raise HTTPException(status_code=403, detail="manager can only assign managed teams")

    return requested_team_id
