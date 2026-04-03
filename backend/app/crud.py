from datetime import date, datetime, time, timedelta
from collections import defaultdict

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app import models


def upsert_telegram_user(
    db: Session,
    telegram_user_id: str,
    name: str,
    telegram_username: str | None,
    default_role: models.UserRole = models.UserRole.pending,
):
    existing = get_user_by_telegram_user_id(db, telegram_user_id)
    if existing:
        existing.name = name
        existing.telegram_username = telegram_username
        db.commit()
        db.refresh(existing)
        return existing

    user = models.User(
        name=name,
        role=default_role,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int):
    return db.get(models.User, user_id)


def set_user_role(db: Session, user_id: int, role: models.UserRole):
    user = get_user(db, user_id)
    if not user:
        return None
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def update_user_name(db: Session, user_id: int, name: str):
    user = get_user(db, user_id)
    if not user:
        return None
    user.name = name
    db.commit()
    db.refresh(user)
    return user


def get_user_by_telegram_user_id(db: Session, telegram_user_id: str):
    stmt = select(models.User).where(models.User.telegram_user_id == telegram_user_id)
    return db.execute(stmt).scalars().first()


def create_task(
    db: Session,
    title: str,
    description: str | None,
    start_at: datetime,
    end_at: datetime,
    required_people: int,
    created_by: int,
    team_id: int | None,
):
    task = models.Task(
        title=title,
        description=description,
        start_at=start_at,
        end_at=end_at,
        required_people=required_people,
        created_by=created_by,
        team_id=team_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    task_id: int,
    title: str | None,
    description: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
    required_people: int | None,
    team_id: int | None,
    team_id_provided: bool,
):
    task = db.get(models.Task, task_id)
    if not task:
        return None

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if start_at is not None:
        task.start_at = start_at
    if end_at is not None:
        task.end_at = end_at
    if required_people is not None:
        task.required_people = required_people
    if team_id_provided:
        task.team_id = team_id

    if task.end_at <= task.start_at:
        raise ValueError("end_at must be after start_at")

    db.commit()
    db.refresh(task)
    return task


def list_tasks_for_day(db: Session, target_date: date):
    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)
    stmt = (
        select(models.Task)
        .where(and_(models.Task.start_at < day_end, models.Task.end_at > day_start))
        .order_by(models.Task.start_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_tasks_for_day_for_team(db: Session, target_date: date, team_id: int):
    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)
    stmt = (
        select(models.Task)
        .outerjoin(models.TaskAssignment, models.TaskAssignment.task_id == models.Task.id)
        .outerjoin(models.TeamMember, models.TeamMember.user_id == models.TaskAssignment.assignee_id)
        .where(
            and_(
                models.Task.start_at < day_end,
                models.Task.end_at > day_start,
                or_(
                    models.Task.team_id == team_id,
                    models.TeamMember.team_id == team_id,
                ),
            )
        )
        .distinct()
        .order_by(models.Task.start_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_assignment_count_by_task(db: Session, task_ids: list[int]) -> dict[int, int]:
    if not task_ids:
        return {}
    stmt = (
        select(models.TaskAssignment.task_id, func.count(models.TaskAssignment.id))
        .where(models.TaskAssignment.task_id.in_(task_ids))
        .group_by(models.TaskAssignment.task_id)
    )
    rows = db.execute(stmt).all()
    return {task_id: count for task_id, count in rows}


def get_assignees_by_task(db: Session, task_ids: list[int]) -> dict[int, list[models.User]]:
    if not task_ids:
        return {}

    stmt = (
        select(models.TaskAssignment.task_id, models.User)
        .join(models.User, models.User.id == models.TaskAssignment.assignee_id)
        .where(models.TaskAssignment.task_id.in_(task_ids))
        .order_by(models.TaskAssignment.task_id.asc(), models.User.name.asc())
    )
    rows = db.execute(stmt).all()
    grouped: dict[int, list[models.User]] = defaultdict(list)
    for task_id, user in rows:
        grouped[task_id].append(user)
    return dict(grouped)


def create_assignment(db: Session, task_id: int, assignee_id: int):
    assignment = models.TaskAssignment(task_id=task_id, assignee_id=assignee_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_user_tasks_for_day(db: Session, user_id: int, target_date: date):
    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)
    stmt = (
        select(models.Task)
        .join(models.TaskAssignment, models.TaskAssignment.task_id == models.Task.id)
        .where(
            and_(
                models.TaskAssignment.assignee_id == user_id,
                models.Task.start_at < day_end,
                models.Task.end_at > day_start,
            )
        )
        .order_by(models.Task.start_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_unfilled_tasks_for_day(db: Session, target_date: date):
    tasks = list_tasks_for_day(db, target_date)
    counts = get_assignment_count_by_task(db, [t.id for t in tasks])
    return [task for task in tasks if counts.get(task.id, 0) < task.required_people]


def list_unfilled_tasks_for_day_for_team(db: Session, target_date: date, team_id: int):
    tasks = list_tasks_for_day_for_team(db, target_date, team_id)
    counts = get_assignment_count_by_task(db, [t.id for t in tasks])
    return [task for task in tasks if counts.get(task.id, 0) < task.required_people]


def list_users(db: Session, role: models.UserRole | None = None):
    stmt = select(models.User)
    if role is not None:
        stmt = stmt.where(models.User.role == role)
    stmt = stmt.order_by(models.User.id.asc())
    return list(db.execute(stmt).scalars().all())


def create_team(db: Session, name: str, created_by: int | None):
    team = models.Team(name=name, created_by=created_by)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_team(db: Session, team_id: int):
    return db.get(models.Team, team_id)


def list_teams(db: Session):
    stmt = select(models.Team).order_by(models.Team.name.asc())
    return list(db.execute(stmt).scalars().all())


def list_teams_managed_by(db: Session, manager_user_id: int):
    stmt = (
        select(models.Team)
        .where(models.Team.created_by == manager_user_id)
        .order_by(models.Team.name.asc())
    )
    return list(db.execute(stmt).scalars().all())


def is_team_managed_by(db: Session, team_id: int, manager_user_id: int) -> bool:
    stmt = select(models.Team.id).where(
        and_(models.Team.id == team_id, models.Team.created_by == manager_user_id)
    )
    return db.execute(stmt).first() is not None


def list_teams_for_user(db: Session, user_id: int):
    stmt = (
        select(models.Team)
        .join(models.TeamMember, models.TeamMember.team_id == models.Team.id)
        .where(models.TeamMember.user_id == user_id)
        .order_by(models.Team.name.asc())
    )
    return list(db.execute(stmt).scalars().all())


def add_users_to_team(db: Session, team_id: int, user_ids: list[int]):
    for user_id in user_ids:
        exists_stmt = select(models.TeamMember).where(
            and_(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user_id)
        )
        exists = db.execute(exists_stmt).scalars().first()
        if not exists:
            db.add(models.TeamMember(team_id=team_id, user_id=user_id))
    db.commit()


def remove_user_from_team(db: Session, team_id: int, user_id: int) -> bool:
    stmt = select(models.TeamMember).where(
        and_(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user_id)
    )
    membership = db.execute(stmt).scalars().first()
    if not membership:
        return False
    db.delete(membership)
    db.commit()
    return True


def is_user_in_team(db: Session, user_id: int, team_id: int) -> bool:
    stmt = select(models.TeamMember.id).where(
        and_(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user_id)
    )
    return db.execute(stmt).first() is not None


def get_team_members(db: Session, team_id: int):
    stmt = (
        select(models.User)
        .join(models.TeamMember, models.TeamMember.user_id == models.User.id)
        .where(models.TeamMember.team_id == team_id)
        .order_by(models.User.name.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_assignment(db: Session, assignment_id: int):
    return db.get(models.TaskAssignment, assignment_id)


def delete_assignment(db: Session, assignment_id: int) -> bool:
    assignment = db.get(models.TaskAssignment, assignment_id)
    if not assignment:
        return False
    db.delete(assignment)
    db.commit()
    return True


def get_setting(db: Session, key: str) -> str | None:
    stmt = select(models.Setting).where(models.Setting.key == key)
    setting = db.execute(stmt).scalars().first()
    return setting.value if setting else None


def set_setting(db: Session, key: str, value: str) -> models.Setting:
    stmt = select(models.Setting).where(models.Setting.key == key)
    existing = db.execute(stmt).scalars().first()
    if existing:
        existing.value = value
        db.commit()
        db.refresh(existing)
        return existing

    setting = models.Setting(key=key, value=value)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting
