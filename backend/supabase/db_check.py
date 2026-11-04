"""backend/.env 의 DATABASE_URL 로 연결해 접속 상태를 읽기만 한다.

실행: uv run --with "psycopg[binary]" python backend/supabase/db_check.py
접속 주소와 비밀번호는 출력하지 않는다. DB 에 쓰는 명령은 없다.
"""

import statistics
import time

import psycopg

from apply_schema import TABLES, database_url

PORT_NAMES = {6543: "트랜잭션 풀러", 5432: "직접 연결"}


def port_label(port: int) -> str:
    name = PORT_NAMES.get(port)
    return f"{port}({name})" if name else str(port)


def server_label(version: int) -> str:
    # server_version 은 170004 처럼 온다. 10 이상은 앞자리가 주 버전, 끝 두 자리가 부 버전이다.
    return f"PostgreSQL {version // 10000}.{version % 100}"


def main() -> None:
    url = database_url()
    start = time.perf_counter()
    conn = psycopg.connect(url)
    connect_ms = (time.perf_counter() - start) * 1000
    try:
        # 트랜잭션을 시작하기 전에 읽기 전용으로 바꾼다. 쓰기 문장은 DB 가 거절한다.
        conn.read_only = True

        role = conn.execute("select current_user").fetchone()[0]

        query_ms = []
        for _ in range(5):
            start = time.perf_counter()
            conn.execute("select 1").fetchone()
            query_ms.append((time.perf_counter() - start) * 1000)

        rows = conn.execute(
            "select tablename, tableowner, rowsecurity from pg_tables"
            " where schemaname = 'public' and tablename = any(%s)",
            (TABLES,),
        ).fetchall()
        info = conn.info
        host, port, version = info.host, info.port, info.server_version
    finally:
        conn.rollback()
        conn.close()

    found = {name: (owner, rls) for name, owner, rls in rows}
    tables = []
    for name in sorted(TABLES):
        if name in found:
            owner, rls = found[name]
            tables.append(f"{name}: 주인={owner} RLS={'켜짐' if rls else '꺼짐'}")
        else:
            tables.append(f"{name}: 없음")

    print(f"① 호스트={host} 포트={port_label(port)} 서버={server_label(version)} 역할={role}")
    print(f"② 연결={connect_ms:.1f}ms 쿼리 5번 가운데 값={statistics.median(query_ms):.1f}ms")
    print("③ " + " · ".join(tables))


if __name__ == "__main__":
    main()
