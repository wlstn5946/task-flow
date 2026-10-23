from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from app.deps import Conn, CurrentUser
from app.models import Status, Task, TaskCreate, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

# 남의 Task 는 없는 Task 와 같은 404 로 보인다. (D-020)
NOT_FOUND = HTTPException(status_code=404, detail="Task 를 찾을 수 없습니다.")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@router.get("", response_model=list[Task])
def list_tasks(conn: Conn, user: CurrentUser) -> list[Task]:
    # 먼저 만든 Task 가 위에 온다. (Q-04) 내 Task 만 돌려준다. (R-009)
    rows = conn.execute(
        "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at, id", (user.id,)
    ).fetchall()
    return [Task(**row) for row in rows]


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, conn: Conn, user: CurrentUser) -> Task:
    # 주인은 요청에서 받지 않고 로그인한 사용자로 정한다.
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (body.title, body.description, body.status.value, now, now, user.id),
        )
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Task(**row)


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, body: TaskUpdate, conn: Conn, user: CurrentUser) -> Task:
    # 보낸 항목만 바꾼다. 컬럼 이름은 모델 필드에서만 오므로 SQL 에 안전하다.
    changes = {
        name: value.value if isinstance(value, Status) else value
        for name in body.model_fields_set
        if (value := getattr(body, name)) is not None
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
    return Task(**row)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, conn: Conn, user: CurrentUser) -> None:
    with conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, user.id)
        )
    if cur.rowcount == 0:
        raise NOT_FOUND
