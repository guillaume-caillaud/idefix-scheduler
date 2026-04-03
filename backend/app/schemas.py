from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models import UserRole


class TelegramLoginRequest(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    auth_date: int
    hash: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AssignRoleRequest(BaseModel):
    role: UserRole


class UserProfileUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str):
        clean = value.strip()
        if not clean:
            raise ValueError("name cannot be empty")
        if len(clean) > 120:
            raise ValueError("name too long")
        return clean


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: UserRole
    telegram_user_id: str
    telegram_username: Optional[str] = None


class TeamCreate(BaseModel):
    name: str
    manager_id: Optional[int] = None


class TeamMembersUpdate(BaseModel):
    user_ids: List[int]


class TeamSetManager(BaseModel):
    manager_id: Optional[int] = None


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_by: Optional[int] = None
    manager_id: Optional[int] = None


class TeamMemberOut(BaseModel):
    id: int
    name: str
    role: UserRole


class TeamDetailOut(TeamOut):
    members: List[TeamMemberOut] = []
    manager: Optional[TeamMemberOut] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    required_people: int = 1
    team_id: Optional[int] = None

    @field_validator("end_at")
    @classmethod
    def end_must_be_after_start(cls, value: datetime, info):
        start_at = info.data.get("start_at")
        if start_at and value <= start_at:
            raise ValueError("end_at must be after start_at")
        return value

    @field_validator("required_people")
    @classmethod
    def required_people_min_one(cls, value: int):
        if value < 1:
            raise ValueError("required_people must be >= 1")
        return value


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    required_people: Optional[int] = None
    team_id: Optional[int] = None

    @field_validator("required_people")
    @classmethod
    def required_people_min_one(cls, value: Optional[int]):
        if value is not None and value < 1:
            raise ValueError("required_people must be >= 1")
        return value


class TaskAssigneeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: UserRole


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    required_people: int
    created_by: int
    team_id: Optional[int] = None
    assigned_people: int = 0
    missing_people: int = 0
    is_fully_staffed: bool = False
    assigned_users: List[TaskAssigneeOut] = []


class AssignmentCreate(BaseModel):
    task_id: int
    assignee_id: int


class AssignmentInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    assignee_id: int


class ConflictItem(BaseModel):
    task_id: int
    title: str
    start_at: datetime
    end_at: datetime


class AssignmentOut(BaseModel):
    id: int
    task_id: int
    assignee_id: int
    conflicts: List[ConflictItem]


class DayScheduleResponse(BaseModel):
    user_id: int
    date: date
    tasks: List[TaskOut]


class ConflictResponse(BaseModel):
    user_id: int
    date: date
    conflicts: List[ConflictItem]


class UnfilledTasksResponse(BaseModel):
    date: date
    tasks: List[TaskOut]


class AlertRequest(BaseModel):
    message: str
    user_ids: Optional[List[int]] = None  # None = diffusion à tous les employés


class SettingIn(BaseModel):
    value: str


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str
