import pytest
from fastapi.testclient import TestClient

from app.db import migrate
from app.main import app


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


def test_list_keeps_oldest_first(client):
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
