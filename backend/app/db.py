import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

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


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
