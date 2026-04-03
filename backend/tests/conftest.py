"""
Fixtures partagées pour tous les tests.

Stratégie DB :
- SQLite :memory: avec StaticPool (toutes les sessions partagent la même connexion).
- Les modules `app.database.engine` et `app.database.SessionLocal` sont patchés au niveau
  module AVANT que le lifespan FastAPI ne les utilise.
- Les tables sont créées/détruites autour de chaque test via la fixture `db`.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as _db_module
from app.database import Base, get_db
from app.main import app
from app import crud
from app.models import UserRole
from app.security import get_current_user, require_admin, require_assigned_role, require_manager

_SQLITE_URL = "sqlite:///:memory:"

_engine = create_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Session = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

# Patch avant tout démarrage de l'app (lifespan + get_db)
_db_module.engine = _engine
_db_module.SessionLocal = _Session


# ---------------------------------------------------------------------------
# Fixtures DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


# ---------------------------------------------------------------------------
# Fixtures utilisateurs
# ---------------------------------------------------------------------------

@pytest.fixture()
def manager_user(db):
    return crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_manager_1",
        name="Manager Test",
        telegram_username="manager_test",
        default_role=UserRole.manager,
    )


@pytest.fixture()
def employee_user(db):
    return crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_employee_1",
        name="Employee Test",
        telegram_username="employee_test",
        default_role=UserRole.employee,
    )


@pytest.fixture()
def employee_user2(db):
    return crud.upsert_telegram_user(
        db,
        telegram_user_id="tg_employee_2",
        name="Employee Test 2",
        telegram_username="employee_test2",
        default_role=UserRole.employee,
    )


# ---------------------------------------------------------------------------
# Factories de TestClient
# ---------------------------------------------------------------------------

def _make_client(db, current_user=None, is_admin=False):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if current_user is not None:
        _user = current_user  # capture locale

        app.dependency_overrides[get_current_user] = lambda: _user
        app.dependency_overrides[require_assigned_role] = lambda: _user
        if _user.role == UserRole.manager:
            app.dependency_overrides[require_manager] = lambda: _user

    if is_admin:
        app.dependency_overrides[require_admin] = lambda: {
            "sub": "admin",
            "role": "admin",
            "kind": "admin",
        }

    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def manager_client(db, manager_user):
    client = _make_client(db, current_user=manager_user)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def employee_client(db, employee_user):
    client = _make_client(db, current_user=employee_user)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client(db):
    client = _make_client(db, is_admin=True)
    yield client
    app.dependency_overrides.clear()
