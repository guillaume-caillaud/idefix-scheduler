from datetime import datetime

from app import crud
from app.database import Base, SessionLocal, engine
from app.models import UserRole


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        manager = crud.upsert_telegram_user(
            db,
            telegram_user_id="900001",
            name="Manager Demo",
            telegram_username="manager_demo",
            default_role=UserRole.manager,
        )
        employee_1 = crud.upsert_telegram_user(
            db,
            telegram_user_id="900002",
            name="Alice",
            telegram_username="alice",
            default_role=UserRole.employee,
        )
        employee_2 = crud.upsert_telegram_user(
            db,
            telegram_user_id="900003",
            name="Bob",
            telegram_username="bob",
            default_role=UserRole.employee,
        )

        task_1 = crud.create_task(
            db,
            title="Support clients",
            description="Permanence hotline",
            start_at=datetime(2026, 4, 1, 9, 0, 0),
            end_at=datetime(2026, 4, 1, 11, 0, 0),
            required_people=2,
            created_by=manager.id,
            team_id=None,
        )
        task_2 = crud.create_task(
            db,
            title="Inventaire",
            description="Contrôle stock zone A",
            start_at=datetime(2026, 4, 1, 10, 30, 0),
            end_at=datetime(2026, 4, 1, 12, 0, 0),
            required_people=1,
            created_by=manager.id,
            team_id=None,
        )
        task_3 = crud.create_task(
            db,
            title="Préparation commandes",
            description="Batch matin",
            start_at=datetime(2026, 4, 2, 9, 0, 0),
            end_at=datetime(2026, 4, 2, 11, 30, 0),
            required_people=1,
            created_by=manager.id,
            team_id=None,
        )

        crud.create_assignment(db, task_1.id, employee_1.id)
        crud.create_assignment(db, task_1.id, manager.id)
        crud.create_assignment(db, task_2.id, employee_1.id)
        crud.create_assignment(db, task_3.id, employee_2.id)

        print("Database initialized with demo data")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
