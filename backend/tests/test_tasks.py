import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "test.db"))
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


def test_tasks_persist_across_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "persist.db"))
    with TestClient(app) as c:
        create(c, title="남아야 함", status="DONE")
    with TestClient(app) as c:
        tasks = c.get("/tasks").json()
    assert [(t["title"], t["status"]) for t in tasks] == [("남아야 함", "DONE")]
