import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import db_path, migrate
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    migrate()
    with TestClient(app) as c:
        yield c


def register(client, username="alice", password="password1"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username="alice", password="password1"):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_register_returns_only_id_and_username(client):
    res = register(client)
    assert res.status_code == 201
    assert set(res.json()) == {"id", "username"}


def test_register_does_not_log_in(client):
    register(client)
    assert client.get("/auth/me").status_code == 401


def test_register_duplicate_username_is_409(client):
    register(client)
    assert register(client).status_code == 409
    assert register(client, username="ALICE").status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"username": "ab", "password": "password1"},
        {"username": "a" * 21, "password": "password1"},
        {"username": "한글아이디", "password": "password1"},
        {"username": "alice", "password": "short"},
        {"username": "alice"},
    ],
)
def test_register_invalid_input_is_422(client, body):
    assert client.post("/auth/register", json=body).status_code == 422


def test_password_is_stored_as_argon2_hash(client):
    register(client)
    with sqlite3.connect(db_path()) as conn:
        (stored,) = conn.execute("SELECT password_hash FROM users").fetchone()
    assert stored.startswith("$argon2")
    assert "password1" not in stored


def test_login_sets_http_only_cookie_and_me_works(client):
    register(client)
    res = login(client)
    assert res.status_code == 200
    assert set(res.json()) == {"id", "username"}
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=3600" in cookie
    assert client.get("/auth/me").json()["username"] == "alice"


def test_login_failures_look_the_same(client):
    register(client)
    wrong_password = login(client, password="wrong-password")
    unknown_user = login(client, username="nobody")
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert client.get("/auth/me").status_code == 401


def test_session_value_is_not_stored_as_is(client):
    register(client)
    login(client)
    token = client.cookies["session"]
    with sqlite3.connect(db_path()) as conn:
        (stored,) = conn.execute("SELECT id FROM sessions").fetchone()
    assert stored != token


def test_logout_ends_session(client):
    register(client)
    login(client)
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401
    with sqlite3.connect(db_path()) as conn:
        assert conn.execute("SELECT count(*) FROM sessions").fetchone() == (0,)


def test_logout_requires_login(client):
    assert client.post("/auth/logout").status_code == 401


def test_expired_session_is_401(client):
    register(client)
    login(client)
    with sqlite3.connect(db_path()) as conn:
        conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00.000+00:00'")
    assert client.get("/auth/me").status_code == 401


def test_forged_cookie_is_401(client):
    client.cookies.set("session", "forged")
    assert client.get("/auth/me").status_code == 401
