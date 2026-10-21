from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator

TITLE_MAX_LENGTH = 20


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
    """보낸 항목만 바꾼다. 설명을 비우려면 빈 문자열을 보낸다."""

    title: str | None = None
    description: str | None = None
    status: Status | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("제목은 비워 둘 수 없습니다.")
        return validate_title(value)

    @model_validator(mode="after")
    def _check_fields(self) -> "TaskUpdate":
        if not self.model_fields_set:
            raise ValueError("바꿀 항목이 없습니다.")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} 에는 null 을 보낼 수 없습니다.")
        return self


class Task(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    created_at: str
    updated_at: str
