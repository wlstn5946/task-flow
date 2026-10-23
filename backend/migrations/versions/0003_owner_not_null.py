"""기존 Task 에 주인을 채우고 owner_id 를 NOT NULL 로 바꾼다

DATA-MIGRATION-PLAN 3~5단계. 주인은 처음 가입한 사용자(users.id 가 가장 작은 사용자)이다. (D-019)
주인이 없는 Task 가 있는데 사용자가 한 명도 없으면 멈춘다. 이때 DB 는 바뀌지 않는다.
처음 가입한 사용자가 생긴 뒤 `alembic upgrade head` 를 다시 실행한다.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    before = conn.exec_driver_sql("SELECT count(*) FROM tasks").scalar_one()
    orphans = conn.exec_driver_sql(
        "SELECT count(*) FROM tasks WHERE owner_id IS NULL"
    ).scalar_one()

    # 3단계: 주인 채우기
    if orphans:
        first_user = conn.exec_driver_sql("SELECT min(id) FROM users").scalar_one()
        if first_user is None:
            raise RuntimeError(
                f"멈춤: 주인이 없는 Task 가 {orphans}개 있는데 가입한 사용자가 없다. "
                "처음 가입한 사용자가 생긴 뒤 다시 실행한다."
            )
        conn.exec_driver_sql(
            "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (first_user,)
        )

    # 4단계: 빈 값 확인
    left = conn.exec_driver_sql(
        "SELECT count(*) FROM tasks WHERE owner_id IS NULL"
    ).scalar_one()
    if left:
        raise RuntimeError(f"멈춤: owner_id 가 비어 있는 Task 가 {left}개 남았다.")

    # 5단계: NOT NULL. SQLite 는 열 제약을 바꿀 수 없어 새 표를 만들어 옮긴다.
    seq = conn.exec_driver_sql(
        "SELECT seq FROM sqlite_sequence WHERE name = 'tasks'"
    ).scalar_one_or_none()
    op.execute(
        """
        CREATE TABLE tasks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK (status IN ('TODO', 'IN_PROGRESS', 'DONE')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            owner_id INTEGER NOT NULL REFERENCES users(id)
        )
        """
    )
    op.execute(
        "INSERT INTO tasks_new (id, title, description, status, created_at, updated_at, owner_id)"
        " SELECT id, title, description, status, created_at, updated_at, owner_id FROM tasks"
    )
    if seq is not None:
        # 지운 Task 의 id 를 다시 쓰지 않도록 자동 증가 값을 이어 간다.
        op.execute(f"UPDATE sqlite_sequence SET seq = {int(seq)} WHERE name = 'tasks_new'")
    op.execute("DROP TABLE tasks")
    op.execute("ALTER TABLE tasks_new RENAME TO tasks")
    op.execute("CREATE INDEX idx_tasks_owner_id ON tasks(owner_id)")

    after = conn.exec_driver_sql("SELECT count(*) FROM tasks").scalar_one()
    if after != before:
        raise RuntimeError(f"멈춤: Task 개수가 {before}개에서 {after}개로 달라졌다.")


def downgrade() -> None:
    raise NotImplementedError("되돌리지 않는다. 0단계의 DB 복사본을 쓴다.")
