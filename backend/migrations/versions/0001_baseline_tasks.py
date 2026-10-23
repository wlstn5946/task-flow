"""v0.1.0 의 tasks 표

이미 v0.1.0 으로 만들어진 DB 에서는 아무것도 바꾸지 않는다. (IF NOT EXISTS)

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK (status IN ('TODO', 'IN_PROGRESS', 'DONE')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    raise NotImplementedError("기준선 이전으로는 되돌리지 않는다. 0단계의 DB 복사본을 쓴다.")
