import sqlite3
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_conn
from app.models import Task, TaskCreate, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@router.get("", response_model=list[Task])
def list_tasks(conn: Conn) -> list[Task]:
    # 먼저 만든 Task 가 위에 온다. (Q-04)
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at, id").fetchall()
    return [Task(**row) for row in rows]


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, conn: Conn) -> Task:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, status, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (body.title, body.description, body.status.value, now, now),
        )
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return Task(**row)


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, body: TaskUpdate, conn: Conn) -> Task:
    with conn:
        cur = conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (body.status.value, _now(), task_id),
        )
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task 를 찾을 수 없습니다.")
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return Task(**row)
