import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import db_path, migrate
from app.deps import get_today
from app.main import app

TODAY = date(2026, 10, 20)


def days(offset):
    """오늘(2026-10-20)에서 offset 일 떨어진 날짜 글자."""
    return (TODAY + timedelta(days=offset)).isoformat()


@pytest.fixture(autouse=True)
def fixed_today():
    # 기한 초과 판단의 '오늘'을 고정한다. (BUSINESS-RULES.md 판정표의 예시와 같다.)
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


def sign_up_and_log_in(client, username):
    creds = {"username": username, "password": "password1"}
    assert client.post("/auth/register", json=creds).status_code == 201
    assert client.post("/auth/login", json=creds).status_code == 200


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    migrate()


@pytest.fixture
def client(db):
    """alice 로 로그인한 클라이언트."""
    with TestClient(app) as c:
        sign_up_and_log_in(c, "alice")
        yield c


@pytest.fixture
def bob(client):
    """bob 으로 로그인한 별도 클라이언트. 쿠키가 alice 와 섞이지 않는다."""
    with TestClient(app) as c:
        sign_up_and_log_in(c, "bob")
        yield c


@pytest.fixture
def anonymous(client):
    with TestClient(app) as c:
        yield c


def create(client, **overrides):
    body = {"title": "책 읽기", "description": "", "status": "TODO", **overrides}
    return client.post("/tasks", json=body)


def test_list_is_empty_at_first(client):
    res = client.get("/tasks")
    assert res.status_code == 200
    assert res.json() == []


def test_create_returns_task_in_chosen_status(client):
    res = create(client, title="운동", description="30분", status="IN_PROGRESS")
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "운동"
    assert body["description"] == "30분"
    assert body["status"] == "IN_PROGRESS"
    assert body["id"] > 0
    assert body["created_at"] == body["updated_at"]


def test_description_can_be_omitted(client):
    res = client.post("/tasks", json={"title": "제목만", "status": "TODO"})
    assert res.status_code == 201
    assert res.json()["description"] == ""


def test_title_is_trimmed(client):
    assert create(client, title="  공백  ").json()["title"] == "공백"


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_empty_or_blank_title_is_rejected_and_nothing_saved(client, title):
    assert create(client, title=title).status_code == 422
    assert client.get("/tasks").json() == []


def test_title_missing_is_rejected(client):
    res = client.post("/tasks", json={"status": "TODO"})
    assert res.status_code == 422


def test_title_20_chars_ok_21_rejected(client):
    assert create(client, title="가" * 20).status_code == 201
    assert create(client, title="가" * 21).status_code == 422
    assert len(client.get("/tasks").json()) == 1


@pytest.mark.parametrize("status", ["todo", "DOING", "", "완료"])
def test_invalid_status_is_rejected(client, status):
    assert create(client, status=status).status_code == 422
    assert client.get("/tasks").json() == []


def test_status_is_required(client):
    res = client.post("/tasks", json={"title": "x"})
    assert res.status_code == 422


def test_list_keeps_oldest_first_when_priority_and_due_date_match(client):
    # 우선순위와 마감일이 모두 같으면 만든 순서(ID)가 남는다. (BR-4)
    for title in ["첫째", "둘째", "셋째"]:
        create(client, title=title)
    assert [t["title"] for t in client.get("/tasks").json()] == ["첫째", "둘째", "셋째"]


def test_tasks_persist_across_app_restart(db):
    with TestClient(app) as c:
        sign_up_and_log_in(c, "alice")
        create(c, title="남아야 함", status="DONE")
    with TestClient(app) as c:
        c.post("/auth/login", json={"username": "alice", "password": "password1"})
        tasks = c.get("/tasks").json()
    assert [(t["title"], t["status"]) for t in tasks] == [("남아야 함", "DONE")]


# --- 로그인과 소유 (R-008, R-009, D-020) ---


def test_every_task_request_needs_login(anonymous):
    assert anonymous.get("/tasks").status_code == 401
    assert create(anonymous).status_code == 401
    assert anonymous.patch("/tasks/1", json={"status": "DONE"}).status_code == 401
    assert anonymous.delete("/tasks/1").status_code == 401


def test_login_is_checked_before_input_rules(anonymous):
    assert anonymous.post("/tasks", json={"title": ""}).status_code == 401


def test_task_response_has_no_owner(client):
    assert "owner_id" not in create(client).json()


def test_list_shows_only_my_tasks(client, bob):
    create(client, title="alice 의 것")
    create(bob, title="bob 의 것")
    assert [t["title"] for t in client.get("/tasks").json()] == ["alice 의 것"]
    assert [t["title"] for t in bob.get("/tasks").json()] == ["bob 의 것"]


def test_owner_in_request_is_ignored(client, bob):
    res = create(client, owner_id=2)
    assert res.status_code == 201
    assert bob.get("/tasks").json() == []
    assert len(client.get("/tasks").json()) == 1


def test_patch_other_users_task_is_404_and_unchanged(client, bob):
    task = create(client, title="alice 의 것").json()
    res = bob.patch(f"/tasks/{task['id']}", json={"title": "가로채기"})
    assert res.status_code == 404
    assert client.get("/tasks").json()[0]["title"] == "alice 의 것"


def test_delete_other_users_task_is_404_and_nothing_deleted(client, bob):
    task = create(client).json()
    assert bob.delete(f"/tasks/{task['id']}").status_code == 404
    assert len(client.get("/tasks").json()) == 1


def test_other_users_task_looks_like_missing_task(client, bob):
    task = create(client).json()
    other = bob.patch(f"/tasks/{task['id']}", json={"status": "DONE"})
    missing = bob.patch("/tasks/9999", json={"status": "DONE"})
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()


def test_own_task_can_be_changed_and_deleted(client):
    task = create(client).json()
    res = client.patch(f"/tasks/{task['id']}", json={"status": "DONE"})
    assert res.status_code == 200
    assert res.json()["status"] == "DONE"
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get("/tasks").json() == []


def test_logged_out_user_cannot_see_tasks(client):
    create(client)
    client.post("/auth/logout")
    assert client.get("/tasks").status_code == 401


# --- 우선순위와 마감일 (R-007, R-010, 이슈 #20) ---


def titles(client):
    return [t["title"] for t in client.get("/tasks").json()]


def test_new_task_defaults_to_normal_priority_without_due_date(client):
    body = create(client).json()
    assert body["priority"] == "NORMAL"
    assert body["due_date"] is None
    assert body["is_overdue"] is False


def test_create_with_priority_and_due_date_including_past_date(client):
    body = create(client, priority="HIGH", due_date=days(-30)).json()
    assert body["priority"] == "HIGH"
    assert body["due_date"] == days(-30)
    assert client.get("/tasks").json()[0]["due_date"] == days(-30)


@pytest.mark.parametrize("priority", ["urgent", "high", "", None, 1])
def test_invalid_priority_is_rejected_and_nothing_saved(client, priority):
    assert create(client, priority=priority).status_code == 422
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize(
    "due_date", ["2026-02-30", "10/20", "20261020", "2026-10-20T10:00:00", "", 20261020]
)
def test_invalid_due_date_is_rejected_and_nothing_saved(client, due_date):
    assert create(client, due_date=due_date).status_code == 422
    assert client.get("/tasks").json() == []


def test_patch_only_title_keeps_priority_and_due_date(client):
    task = create(client, priority="HIGH", due_date=days(3)).json()
    res = client.patch(f"/tasks/{task['id']}", json={"title": "바뀜"})
    assert res.status_code == 200
    assert (res.json()["priority"], res.json()["due_date"]) == ("HIGH", days(3))


def test_patch_priority_and_due_date_only(client):
    task = create(client).json()
    res = client.patch(
        f"/tasks/{task['id']}", json={"priority": "LOW", "due_date": days(5)}
    )
    assert res.status_code == 200
    body = res.json()
    assert (body["priority"], body["due_date"], body["title"]) == ("LOW", days(5), "책 읽기")


def test_patch_due_date_null_clears_it_but_priority_stays(client):
    task = create(client, priority="HIGH", due_date=days(3)).json()
    res = client.patch(f"/tasks/{task['id']}", json={"due_date": None})
    assert res.status_code == 200
    assert (res.json()["priority"], res.json()["due_date"]) == ("HIGH", None)
    assert client.get("/tasks").json()[0]["due_date"] is None


def test_patch_priority_null_is_rejected_and_unchanged(client):
    task = create(client, priority="HIGH").json()
    res = client.patch(f"/tasks/{task['id']}", json={"priority": None})
    assert res.status_code == 422
    assert client.get("/tasks").json()[0]["priority"] == "HIGH"


@pytest.mark.parametrize("body", [{"priority": "URGENT"}, {"due_date": "2026-13-01"}])
def test_patch_invalid_values_are_rejected_and_unchanged(client, body):
    task = create(client, priority="HIGH", due_date=days(3)).json()
    assert client.patch(f"/tasks/{task['id']}", json=body).status_code == 422
    saved = client.get("/tasks").json()[0]
    assert (saved["priority"], saved["due_date"]) == ("HIGH", days(3))


def test_patch_title_and_description_null_are_still_rejected(client):
    task = create(client).json()
    assert client.patch(f"/tasks/{task['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/tasks/{task['id']}", json={"description": None}).status_code == 422
    assert client.get("/tasks").json()[0]["title"] == "책 읽기"


def test_patch_with_only_unknown_field_changes_nothing(client):
    task = create(client).json()
    assert client.patch(f"/tasks/{task['id']}", json={"color": "red"}).status_code == 422


def test_patch_new_fields_updates_updated_at(client, monkeypatch):
    task = create(client).json()
    monkeypatch.setattr("app.routes.tasks._now", lambda: "9999-01-01T00:00:00.000+00:00")
    res = client.patch(f"/tasks/{task['id']}", json={"priority": "HIGH"})
    assert res.json()["updated_at"] == "9999-01-01T00:00:00.000+00:00"
    assert res.json()["created_at"] == task["created_at"]


def test_legacy_row_without_new_values_lists_as_normal_without_due_date(client):
    # 마이그레이션 전에 있던 행은 새 열이 기본값이다. 목록 전체가 오류가 되면 안 된다.
    conn = sqlite3.connect(db_path())
    with conn:
        conn.execute(
            "INSERT INTO tasks (title, description, status, created_at, updated_at, owner_id)"
            " VALUES ('옛 카드', '', 'TODO', 't', 't', 1)"
        )
    conn.close()
    task = client.get("/tasks").json()[0]
    assert (task["priority"], task["due_date"], task["is_overdue"]) == ("NORMAL", None, False)


# 기한 초과 판정표: 오늘이 10-20 일 때 어제 × TODO · IN_PROGRESS 만 기한 초과이다. (BR-3)
@pytest.mark.parametrize("status", ["TODO", "IN_PROGRESS", "DONE"])
@pytest.mark.parametrize(
    "offset, overdue_when_not_done",
    [(-1, True), (0, False), (1, False), (None, False)],
    ids=["yesterday", "today", "tomorrow", "no-due-date"],
)
def test_overdue_table(client, status, offset, overdue_when_not_done):
    due_date = None if offset is None else days(offset)
    created = create(client, status=status, due_date=due_date).json()
    listed = client.get("/tasks").json()[0]
    expected = overdue_when_not_done and status != "DONE"
    assert created["is_overdue"] is expected
    assert listed["is_overdue"] is expected


def test_changing_status_keeps_fields_and_recomputes_overdue(client):
    task = create(client, priority="HIGH", due_date=days(-1)).json()
    assert task["is_overdue"] is True
    done = client.patch(f"/tasks/{task['id']}", json={"status": "DONE"}).json()
    assert (done["priority"], done["due_date"], done["is_overdue"]) == ("HIGH", days(-1), False)
    back = client.patch(f"/tasks/{task['id']}", json={"status": "TODO"}).json()
    assert back["is_overdue"] is True


def test_list_sorted_overdue_then_priority_then_due_date_then_id(client):
    create(client, title="a 보통 마감없음")
    create(client, title="b 낮음 기한초과", priority="LOW", due_date=days(-1))
    create(client, title="c 높음 마감없음", priority="HIGH")
    create(client, title="d 높음 내일", priority="HIGH", due_date=days(1))
    create(client, title="e 높음 모레", priority="HIGH", due_date=days(2))
    create(client, title="f 보통 내일", due_date=days(1))
    create(client, title="g 높음 어제 완료", priority="HIGH", due_date=days(-1), status="DONE")
    create(client, title="h 높음 기한초과", priority="HIGH", due_date=days(-3))
    create(client, title="i 보통 내일(f와 같음)", due_date=days(1))
    assert titles(client) == [
        "h 높음 기한초과",
        "b 낮음 기한초과",
        "g 높음 어제 완료",
        "d 높음 내일",
        "e 높음 모레",
        "c 높음 마감없음",
        "f 보통 내일",
        "i 보통 내일(f와 같음)",
        "a 보통 마감없음",
    ]


def test_sorted_list_never_shows_other_users_tasks(client, bob):
    create(client, title="alice 기한초과", priority="HIGH", due_date=days(-1))
    create(bob, title="bob 기한초과", priority="HIGH", due_date=days(-2))
    create(bob, title="bob 보통")
    assert titles(client) == ["alice 기한초과"]
    assert titles(bob) == ["bob 기한초과", "bob 보통"]
