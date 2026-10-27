import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator

TITLE_MAX_LENGTH = 20


class Status(StrEnum):
    """상태 세 값의 정의는 여기 한 곳에만 둔다. (D-007)"""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class Priority(StrEnum):
    """우선순위 세 값의 정의는 여기 한 곳에만 둔다. 저장소의 CHECK 와 같은 값이다. (R-010)"""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


DUE_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def validate_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise ValueError("제목은 비워 둘 수 없습니다.")
    if len(title) > TITLE_MAX_LENGTH:
        raise ValueError(f"제목은 {TITLE_MAX_LENGTH}글자까지입니다.")
    return title


def validate_due_date(value: str | None) -> str | None:
    """YYYY-MM-DD 날짜만 받는다. 없는 날짜(02-30)와 시각이 붙은 값은 거절한다. 지난 날짜는 괜찮다. (BR-2)"""
    if value is None:
        return None
    if not DUE_DATE_PATTERN.fullmatch(value):
        raise ValueError("마감일은 YYYY-MM-DD 형식입니다.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("존재하지 않는 날짜입니다.") from None
    return value


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: Status
    priority: Priority = Priority.NORMAL
    due_date: str | None = None

    _check_title = field_validator("title")(validate_title)
    _check_due_date = field_validator("due_date")(validate_due_date)


# 수정에서 null 을 보내 지울 수 있는 항목. 나머지는 null 이면 거절한다. (10-3)
NULLABLE_ON_UPDATE = {"due_date"}


class TaskUpdate(BaseModel):
    """보낸 항목만 바꾼다. 설명을 비우려면 빈 문자열을, 마감일을 지우려면 null 을 보낸다."""

    title: str | None = None
    description: str | None = None
    status: Status | None = None
    priority: Priority | None = None
    due_date: str | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("제목은 비워 둘 수 없습니다.")
        return validate_title(value)

    _check_due_date = field_validator("due_date")(validate_due_date)

    @model_validator(mode="after")
    def _check_fields(self) -> "TaskUpdate":
        if not self.model_fields_set:
            raise ValueError("바꿀 항목이 없습니다.")
        for name in self.model_fields_set - NULLABLE_ON_UPDATE:
            if getattr(self, name) is None:
                raise ValueError(f"{name} 에는 null 을 보낼 수 없습니다.")
        return self


USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,20}")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


class Registration(BaseModel):
    """가입 입력. 규칙은 임시 기본값이다. (Q-19)"""

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        username = value.strip().lower()
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("아이디는 영문 · 숫자 · _ 로 3~20글자입니다.")
        return username

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if not PASSWORD_MIN_LENGTH <= len(value) <= PASSWORD_MAX_LENGTH:
            raise ValueError(
                f"비밀번호는 {PASSWORD_MIN_LENGTH}~{PASSWORD_MAX_LENGTH}글자입니다."
            )
        return value


class Login(BaseModel):
    """로그인 입력. 형식은 점검하지 않는다. 맞지 않으면 그냥 로그인 실패(401)이다."""

    username: str
    password: str


class User(BaseModel):
    """사용자 응답. id, username 만 담는다. (D-021)"""

    id: int
    username: str


class Task(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    priority: Priority
    due_date: str | None
    is_overdue: bool
    created_at: str
    updated_at: str
