"""테스트용 PostgreSQL 도우미.

테스트는 TEST_DATABASE_URL 로만 돌고, 호스트가 내 PC(localhost)가 아니면 멈춘다.
테스트마다 세 표를 비우므로 Supabase 같은 진짜 DB 에는 절대 연결하지 않는다.
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.db import BACKEND_DIR

load_dotenv(BACKEND_DIR / ".env")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def test_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.fail("TEST_DATABASE_URL 이 없다. backend/.env 에 내 PC 의 PostgreSQL 주소를 넣는다.")
    if conninfo_to_dict(url).get("host") not in LOCAL_HOSTS:
        # 주소와 비밀번호는 출력하지 않는다.
        pytest.fail("TEST_DATABASE_URL 의 호스트가 localhost 가 아니다. 테스트는 내 PC 에서만 돈다.")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(test_url(), row_factory=dict_row, autocommit=True)


def use_test_db(monkeypatch) -> None:
    """앱이 테스트 DB 를 보게 하고 세 표를 비운다. id 는 1 부터 다시 센다."""
    url = test_url()
    monkeypatch.setenv("DATABASE_URL", url)
    with connect() as conn:
        conn.execute("TRUNCATE users, sessions, tasks RESTART IDENTITY CASCADE")


def set_raw_due_date(task_id, value) -> None:
    """API 를 거치지 않고 DB 에 마감일을 직접 쓴다.

    PostgreSQL 에는 CHECK 를 끄는 PRAGMA 가 없어 제약을 지우고 쓴 뒤 NOT VALID 로 다시 단다.
    이미 들어간 행은 검사하지 않고 새 행은 계속 검사한다. 행은 다음 테스트의 TRUNCATE 로 사라진다.
    """
    with connect() as conn, conn.transaction():
        conn.execute("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_due_date_check")
        conn.execute("UPDATE tasks SET due_date = %s WHERE id = %s", (value, task_id))
        conn.execute(
            "ALTER TABLE tasks ADD CONSTRAINT tasks_due_date_check"
            " CHECK (due_date IS NULL OR to_char(due_date::date, 'YYYY-MM-DD') = due_date)"
            " NOT VALID"
        )
