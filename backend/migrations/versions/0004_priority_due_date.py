"""tasks 에 priority 와 due_date 열을 더한다

이슈 #20. 표를 다시 만들지 않고 열만 더하므로 id, 자동 증가 값, owner_id, 인덱스는 그대로이다.
기존 Task 는 priority 가 NORMAL 이고 due_date 는 비어 있다. (R-006, R-010)
기한 초과는 서버가 목록을 줄 때 계산하므로 열로 저장하지 않는다. (BR-3)

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'NORMAL'"
        " CHECK (priority IN ('LOW', 'NORMAL', 'HIGH'))"
    )
    # 날짜만 YYYY-MM-DD 글자로 저장한다. 글자 순서가 날짜 순서와 같아 정렬에 그대로 쓴다.
    op.execute(
        "ALTER TABLE tasks ADD COLUMN due_date TEXT"
        " CHECK (due_date IS NULL OR date(due_date) = due_date)"
    )


def downgrade() -> None:
    raise NotImplementedError("되돌리지 않는다. 적용 전 DB 복사본을 쓴다.")
