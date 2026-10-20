from enum import StrEnum

from pydantic import BaseModel, field_validator

TITLE_MAX_LENGTH = 30


class Status(StrEnum):
    """상태 세 값의 정의는 여기 한 곳에만 둔다. (D-007)"""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


def validate_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise ValueError("제목은 비워 둘 수 없습니다.")
    if len(title) > TITLE_MAX_LENGTH:
        raise ValueError(f"제목은 {TITLE_MAX_LENGTH}글자까지입니다.")
    return title


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: Status

    _check_title = field_validator("title")(validate_title)


class TaskUpdate(BaseModel):
    """상태 변경. 제목·설명 수정은 이후 이슈에서 이 모델을 넓힌다."""

    status: Status


class Task(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    created_at: str
    updated_at: str
