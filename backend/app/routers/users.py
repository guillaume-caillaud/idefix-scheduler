from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import User, UserRole
from app.security import require_admin, require_manager

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    role: Optional[UserRole] = None,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return crud.list_users(db, role=role)


@router.get("/assignable", response_model=list[schemas.UserOut])
def list_assignable_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_manager),
):
    """Utilisateurs pouvant être affectés — visibles par les managers."""
    users = crud.list_users(db)
    return [u for u in users if u.role in (UserRole.employee, UserRole.manager)]


@router.get("/by-telegram/{telegram_user_id}", response_model=schemas.UserOut)
def get_user_by_telegram_id(telegram_user_id: str, db: Session = Depends(get_db)):
    user = crud.get_user_by_telegram_user_id(db, telegram_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user.role == UserRole.pending:
        raise HTTPException(status_code=403, detail="user role not approved yet")
    return user
