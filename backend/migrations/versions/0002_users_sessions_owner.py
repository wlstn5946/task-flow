"""users, sessions 표와 tasks.owner_id (null 허용)

DATA-MIGRATION-PLAN 1~2단계. 기존 Task 의 내용은 바뀌지 않고 owner_id 는 모두 비어 있다.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    # id 는 숫자 자동 증가가 아니다. 쿠키로 받은 값을 찾는 키이다. (DATA-MIGRATION-PLAN 3-2)
    op.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL
        )
        """
    )
    op.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
    op.execute("CREATE INDEX idx_tasks_owner_id ON tasks(owner_id)")


def downgrade() -> None:
    raise NotImplementedError("되돌리지 않는다. 0단계의 DB 복사본을 쓴다.")
