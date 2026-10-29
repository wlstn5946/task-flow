import sqlite3
from datetime import UTC, date, datetime
from enum import StrEnum

from fastapi import APIRouter, HTTPException

from app import ai
from app.deps import Conn, CurrentUser, Today
from app.models import (
    GenerateRequest,
    GeneratedTasks,
    Status,
    SuggestRequest,
    Suggestion,
    Task,
    TaskCreate,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# 남의 Task 는 없는 Task 와 같은 404 로 보인다. (D-020)
NOT_FOUND = HTTPException(status_code=404, detail="Task 를 찾을 수 없습니다.")

# 기한 초과 → 우선순위(HIGH 먼저) → 가까운 마감일(없으면 맨 뒤) → 만든 순서(ID). (R-012, BR-4)
# 기한 초과의 기준(BR-3)은 _is_overdue 와 같아야 한다. 내 Task 만 고르는 조건은 호출하는 쪽의 WHERE 이다. (R-009)
LIST_ORDER = """
    ORDER BY
        (due_date IS NOT NULL AND due_date < :today AND status != 'DONE') DESC,
        CASE priority WHEN 'HIGH' THEN 0 WHEN 'NORMAL' THEN 1 ELSE 2 END,
        due_date IS NULL,
        due_date,
        id
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _is_overdue(row: sqlite3.Row, today: date) -> bool:
    """마감일이 오늘보다 이전이고 완료가 아니면 기한 초과이다. 당일은 아니다. 저장하지 않고 계산한다. (BR-3)"""
    due_date = row["due_date"]
    return (
        due_date is not None
        and due_date < today.isoformat()
        and row["status"] != Status.DONE
    )


def _to_task(row: sqlite3.Row, today: date) -> Task:
    return Task(**row, is_overdue=_is_overdue(row, today))


@router.get("", response_model=list[Task])
def list_tasks(conn: Conn, user: CurrentUser, today: Today) -> list[Task]:
    rows = conn.execute(
        f"SELECT * FROM tasks WHERE owner_id = :owner_id {LIST_ORDER}",
        {"owner_id": user.id, "today": today.isoformat()},
    ).fetchall()
    return [_to_task(row, today) for row in rows]


@router.post("/suggest", response_model=Suggestion)
def suggest_task(body: SuggestRequest, user: CurrentUser, today: Today) -> Suggestion:
    # 제안만 돌려주고 저장소는 건드리지 않는다. 로그인 확인은 CurrentUser 가 먼저 한다.
    return ai.suggest(body.title, body.description, today)


@router.post("/generate", response_model=GeneratedTasks)
def generate_tasks(
    body: GenerateRequest, user: CurrentUser, today: Today
) -> GeneratedTasks:
    # 목표 하나를 할 일 3~5개로 나눈 초안만 돌려준다. 저장하지 않으므로 저장소를 건드리지 않는다.
    return ai.generate(body.title, today)


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, conn: Conn, user: CurrentUser, today: Today) -> Task:
    # 주인은 요청에서 받지 않고 로그인한 사용자로 정한다.
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO tasks"
            " (title, description, status, priority, due_date, created_at, updated_at, owner_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.title,
                body.description,
                body.status.value,
                body.priority.value,
                body.due_date,
                now,
                now,
                user.id,
            ),
        )
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _to_task(row, today)


@router.patch("/{task_id}", response_model=Task)
def update_task(
    task_id: int, body: TaskUpdate, conn: Conn, user: CurrentUser, today: Today
) -> Task:
    # 보낸 항목만 바꾼다. 컬럼 이름은 모델 필드에서만 오므로 SQL 에 안전하다.
    # null 은 모델이 due_date 에만 허용하므로 여기서는 "마감일 지우기"가 된다.
    changes = {
        name: value.value if isinstance(value, StrEnum) else value
        for name, value in body.model_dump(exclude_unset=True).items()
    }
    assignments = ", ".join(f"{name} = ?" for name in changes)
    with conn:
        cur = conn.execute(
            f"UPDATE tasks SET {assignments}, updated_at = ? WHERE id = ? AND owner_id = ?",
            (*changes.values(), _now(), task_id, user.id),
        )
    if cur.rowcount == 0:
        raise NOT_FOUND
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_task(row, today)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, conn: Conn, user: CurrentUser) -> None:
    with conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, user.id)
        )
    if cur.rowcount == 0:
        raise NOT_FOUND
