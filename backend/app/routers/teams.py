from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import User, UserRole
from app.security import require_assigned_role, require_manager_or_admin, require_user_or_admin

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    actor_kind, actor = auth_ctx
    if actor_kind == "admin":
        return crud.list_teams(db)
    return crud.list_teams_managed_by(db, actor.id)


@router.get("/me", response_model=list[schemas.TeamOut])
def list_my_teams(
    db: Session = Depends(get_db),
    user: User = Depends(require_assigned_role),
):
    return crud.list_teams_for_user(db, user.id)


@router.post("", response_model=schemas.TeamOut)
def create_team(
    payload: schemas.TeamCreate,
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    _, actor = auth_ctx
    created_by = actor.id if isinstance(actor, User) else None
    try:
        return crud.create_team(db, payload.name.strip(), created_by)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="team name already exists")


@router.get("/{team_id}", response_model=schemas.TeamDetailOut)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    auth_ctx: tuple[str, User | dict] = Depends(require_user_or_admin),
):
    team = crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")

    actor_kind, actor = auth_ctx
    if actor_kind == "user" and actor.role == UserRole.employee and not crud.is_user_in_team(db, actor.id, team_id):
        raise HTTPException(status_code=403, detail="team access denied")

    members = crud.get_team_members(db, team_id)
    return _team_detail(team, members)


@router.post("/{team_id}/members", response_model=schemas.TeamDetailOut)
def add_team_members(
    team_id: int,
    payload: schemas.TeamMembersUpdate,
    db: Session = Depends(get_db),
    _: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    team = crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")

    users = [crud.get_user(db, user_id) for user_id in payload.user_ids]
    if any(user is None for user in users):
        raise HTTPException(status_code=404, detail="one or more users not found")

    invalid_roles = [user.id for user in users if user and user.role != UserRole.employee]
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="only employees can be added to teams",
        )

    crud.add_users_to_team(db, team_id, payload.user_ids)
    members = crud.get_team_members(db, team_id)
    return _team_detail(team, members)


@router.delete("/{team_id}/members/{user_id}", response_model=schemas.TeamDetailOut)
def remove_team_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    team = crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")

    removed = crud.remove_user_from_team(db, team_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="team member not found")

    members = crud.get_team_members(db, team_id)
    return _team_detail(team, members)


@router.patch("/{team_id}/manager", response_model=schemas.TeamDetailOut)
def set_team_manager(
    team_id: int,
    payload: schemas.TeamSetManager,
    db: Session = Depends(get_db),
    _: tuple[str, User | dict] = Depends(require_manager_or_admin),
):
    """Admin/Manager can assign a manager to a team."""
    team = crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")

    if payload.manager_id is not None:
        manager = crud.get_user(db, payload.manager_id)
        if not manager:
            raise HTTPException(status_code=404, detail="manager not found")
        if manager.role != UserRole.manager:
            raise HTTPException(status_code=400, detail="user must have manager role")
    
    team.manager_id = payload.manager_id
    db.commit()
    db.refresh(team)
    
    members = crud.get_team_members(db, team_id)
    return _team_detail(team, members)


def _team_detail(team, members: list[User]) -> schemas.TeamDetailOut:
    manager = None
    if team.manager_id:
        manager_user = [m for m in members if m.id == team.manager_id]
        if not manager_user and team.manager_id:
            # Manager might not be in members list, fetch separately
            from app.database import get_db
            try:
                db = next(get_db())
                manager_user_obj = crud.get_user(db, team.manager_id)
                if manager_user_obj:
                    manager = schemas.TeamMemberOut(
                        id=manager_user_obj.id,
                        name=manager_user_obj.name,
                        role=manager_user_obj.role
                    )
            except:
                pass
        elif manager_user:
            m = manager_user[0]
            manager = schemas.TeamMemberOut(id=m.id, name=m.name, role=m.role)
    
    return schemas.TeamDetailOut(
        id=team.id,
        name=team.name,
        created_by=team.created_by,
        manager_id=team.manager_id,
        manager=manager,
        members=[schemas.TeamMemberOut(id=m.id, name=m.name, role=m.role) for m in members],
    )
