"""backend/.env 의 DATABASE_URL 로 연결해 schema.sql 을 한 번 실행한다.

실행: uv run --with "psycopg[binary]" python backend/supabase/apply_schema.py
접속 주소와 비밀번호는 출력하지 않는다. 표마다 주인과 RLS 켜짐만 한 줄씩 출력한다.
"""

import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE.parent / ".env"
TABLES = ["users", "sessions", "tasks"]


def database_url() -> str:
    # python-dotenv 없이 KEY=VALUE 줄만 읽는다.
    if not ENV_FILE.exists():
        sys.exit("멈춤: backend/.env 가 없다.")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "DATABASE_URL":
            url = value.strip().strip('"').strip("'")
            if url:
                return url
    sys.exit("멈춤: backend/.env 에 DATABASE_URL 이 없다.")


def main() -> None:
    schema = (HERE / "schema.sql").read_text(encoding="utf-8")
    # with 블록이 끝날 때 커밋한다. 중간에 실패하면 아무것도 남지 않는다.
    with psycopg.connect(database_url()) as conn:
        conn.execute(schema)
        rows = conn.execute(
            "select tablename, tableowner, rowsecurity from pg_tables"
            " where schemaname = 'public' and tablename = any(%s) order by tablename",
            (TABLES,),
        ).fetchall()
    for name, owner, rls in rows:
        print(f"{name}: 주인={owner} RLS={'켜짐' if rls else '꺼짐'}")


if __name__ == "__main__":
    main()
