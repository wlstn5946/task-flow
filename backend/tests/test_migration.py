import sqlite3

import pytest

from app.db import db_path, migrate


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "migration.db"))


def query(sql, params=()):
    with sqlite3.connect(db_path()) as conn:
        return conn.execute(sql, params).fetchall()


def run(sql, params=()):
    conn = sqlite3.connect(db_path())
    with conn:
        conn.execute(sql, params)
    conn.close()


def add_tasks(count):
    for i in range(count):
        run(
            "INSERT INTO tasks (title, description, status, created_at, updated_at)"
            " VALUES (?, ?, 'TODO', 't', 't')",
            (f"카드{i}", f"설명{i}"),
        )


def tables():
    return {r[0] for r in query("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_baseline_keeps_existing_v010_database():
    # v0.1.0 으로 만들어진 DB 를 흉내 낸다: tasks 표와 Task 만 있고 alembic 기록이 없다.
    migrate("0001")
    add_tasks(2)
    run("DROP TABLE alembic_version")
    before = query("SELECT * FROM tasks ORDER BY id")

    migrate("0001")

    assert query("SELECT * FROM tasks ORDER BY id") == before


def test_step_1_2_adds_tables_and_empty_owner_without_changing_tasks():
    migrate("0001")
    add_tasks(3)
    before = query("SELECT id, title, description, status, created_at, updated_at FROM tasks")

    migrate("0002")

    assert {"users", "sessions"} <= tables()
    assert query("SELECT count(*) FROM users") == [(0,)]
    assert query("SELECT count(*) FROM sessions") == [(0,)]
    assert query(
        "SELECT id, title, description, status, created_at, updated_at FROM tasks"
    ) == before
    assert query("SELECT count(*) FROM tasks WHERE owner_id IS NULL") == [(3,)]


def test_existing_tasks_go_to_first_registered_user():
    migrate("0002")
    add_tasks(3)
    run("INSERT INTO users (username, password_hash) VALUES ('first', 'h1')")
    run("INSERT INTO users (username, password_hash) VALUES ('second', 'h2')")

    migrate("head")

    assert query("SELECT count(*) FROM tasks") == [(3,)]
    assert query("SELECT DISTINCT owner_id FROM tasks") == [(1,)]
    assert query("SELECT title, description FROM tasks ORDER BY id") == [
        ("카드0", "설명0"),
        ("카드1", "설명1"),
        ("카드2", "설명2"),
    ]


def test_owner_id_is_not_null_after_step_5():
    migrate("head")
    run("INSERT INTO users (username, password_hash) VALUES ('u', 'h')")
    with pytest.raises(sqlite3.IntegrityError):
        run(
            "INSERT INTO tasks (title, description, status, created_at, updated_at)"
            " VALUES ('x', '', 'TODO', 't', 't')"
        )


def test_stops_and_changes_nothing_when_tasks_have_no_owner_and_no_user():
    migrate("0002")
    add_tasks(2)
    before = query("SELECT * FROM tasks ORDER BY id")

    with pytest.raises(RuntimeError, match="멈춤"):
        migrate("head")

    assert query("SELECT * FROM tasks ORDER BY id") == before
    assert query("SELECT version_num FROM alembic_version") == [("0002",)]

    # 처음 가입한 사용자가 생긴 뒤에는 이어서 끝난다.
    run("INSERT INTO users (username, password_hash) VALUES ('first', 'h')")
    migrate("head")
    assert query("SELECT count(*) FROM tasks WHERE owner_id = 1") == [(2,)]


def test_no_tasks_needs_no_user():
    migrate("head")
    assert query("SELECT count(*) FROM tasks") == [(0,)]
    assert query("SELECT version_num FROM alembic_version") == [("0004",)]


def test_deleted_task_ids_are_not_reused():
    migrate("0002")
    add_tasks(3)
    run("DELETE FROM tasks WHERE id = 3")
    run("INSERT INTO users (username, password_hash) VALUES ('first', 'h')")

    migrate("head")
    run(
        "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
        " VALUES ('new', '', 'TODO', 't', 't', 1)"
    )

    assert query("SELECT max(id) FROM tasks") == [(4,)]


def test_step_0004_gives_existing_tasks_normal_and_no_due_date():
    migrate("0003")
    run("INSERT INTO users (username, password_hash) VALUES ('a', 'h')")
    run("INSERT INTO users (username, password_hash) VALUES ('b', 'h')")
    for owner in (1, 1, 2):
        run(
            "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
            " VALUES ('t', 'd', 'DONE', 'c', 'u', ?)",
            (owner,),
        )
    before = query(
        "SELECT id, title, description, status, created_at, updated_at, owner_id"
        " FROM tasks ORDER BY id"
    )

    migrate("head")

    assert query(
        "SELECT id, title, description, status, created_at, updated_at, owner_id"
        " FROM tasks ORDER BY id"
    ) == before
    assert query("SELECT DISTINCT priority, due_date FROM tasks") == [("NORMAL", None)]
    assert query("SELECT owner_id, count(*) FROM tasks GROUP BY owner_id") == [(1, 2), (2, 1)]
    assert query("SELECT version_num FROM alembic_version") == [("0004",)]


def test_step_0004_keeps_index_and_id_sequence():
    migrate("0003")
    run("INSERT INTO users (username, password_hash) VALUES ('a', 'h')")
    for _ in range(3):
        run(
            "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
            " VALUES ('t', '', 'TODO', 'c', 'u', 1)"
        )
    run("DELETE FROM tasks WHERE id = 3")

    migrate("head")
    run(
        "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
        " VALUES ('new', '', 'TODO', 'c', 'u', 1)"
    )

    assert query("SELECT max(id) FROM tasks") == [(4,)]
    assert query(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_tasks_owner_id'"
    ) == [("idx_tasks_owner_id",)]


def test_new_columns_reject_values_outside_the_rules():
    migrate("head")
    run("INSERT INTO users (username, password_hash) VALUES ('u', 'h')")
    insert = (
        "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id,"
        " priority, due_date) VALUES ('t', '', 'TODO', 'c', 'u', 1, ?, ?)"
    )
    run(insert, ("HIGH", "2020-01-01"))  # 지난 날짜도 쓸 수 있다.
    run(insert, ("LOW", None))
    for priority, due_date in (("URGENT", None), (None, None), ("NORMAL", "2026-02-30"), ("NORMAL", "10/20")):
        with pytest.raises(sqlite3.IntegrityError):
            run(insert, (priority, due_date))
    assert query("SELECT count(*) FROM tasks") == [(2,)]
