import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "taskflow.db"


def db_path() -> Path:
    return Path(os.environ.get("TASKFLOW_DB", DEFAULT_DB_PATH))


def migrate(target: str = "head") -> None:
    """스키마는 Alembic 이전(migrations/)이 유일한 출처이다. 앱은 시작할 때 스키마를 바꾸지 않는다."""
    from alembic import command
    from alembic.config import Config

    db_path().parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(config, target)


# 표는 supabase/schema.sql 이 만든다. 앱은 열이 있는지만 확인한다.
REQUIRED_COLUMNS = {
    "users": {"id", "username", "password_hash"},
    "sessions": {"id", "user_id", "expires_at"},
    "tasks": {
        "id",
        "title",
        "description",
        "status",
        "created_at",
        "updated_at",
        "owner_id",
        "priority",
        "due_date",
    },
}


def database_url() -> str:
    # backend/.env 는 app.security 가 불러온다.
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL 이 없다. backend/.env 에 값을 넣는다.")
    return url


def _connect() -> psycopg.Connection:
    # prepare_threshold=None: 트랜잭션 풀러(6543)는 prepared statement 를 못 쓴다.
    return psycopg.connect(
        database_url(), row_factory=dict_row, autocommit=True, prepare_threshold=None
    )


def init_db() -> None:
    """표를 만들지 않고 열이 다 있는지만 확인한다. 모자라면 멈춘다."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns"
            " WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (list(REQUIRED_COLUMNS),),
        ).fetchall()
    found = {(row["table_name"], row["column_name"]) for row in rows}
    missing = sorted(
        f"{table}.{column}"
        for table, columns in REQUIRED_COLUMNS.items()
        for column in columns
        if (table, column) not in found
    )
    if missing:
        raise RuntimeError(
            f"멈춤: 없는 열 {', '.join(missing)}. backend/supabase/schema.sql 을 먼저 적용한다."
        )


def get_conn() -> Iterator[psycopg.Connection]:
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()
