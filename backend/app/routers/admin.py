from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings/default-day")
def get_default_day(db: Session = Depends(get_db)):
    """Get the default date for planning views (yyyy-MM-dd format)"""
    value = crud.get_setting(db, "default_day")
    if value is None:
        return {"day": None}
    return {"day": value}


@router.post("/settings/default-day")
def set_default_day(
    payload: schemas.SettingIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Set the default date for planning views (yyyy-MM-dd format)"""
    result = crud.set_setting(db, "default_day", payload.value)
    return {"day": result.value}


@router.get("/settings/app-name")
def get_app_name(db: Session = Depends(get_db)):
    """Get the application name for display in navbar and title"""
    value = crud.get_setting(db, "app_name")
    if value is None:
        return {"app_name": "Team Scheduler"}
    return {"app_name": value}


@router.post("/settings/app-name")
def set_app_name(
    payload: schemas.SettingIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Set the application name"""
    result = crud.set_setting(db, "app_name", payload.value)
    return {"app_name": result.value}


@router.get("/settings/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    value = crud.get_setting(db, key)
    if value is None:
        raise HTTPException(status_code=404, detail="setting not found")
    return {"key": key, "value": value}


@router.post("/settings/{key}")
def set_setting(
    key: str,
    payload: schemas.SettingIn,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    result = crud.set_setting(db, key, payload.value)
    return {"key": result.key, "value": result.value}
