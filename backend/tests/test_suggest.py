import sqlite3
from datetime import date
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from app import ai
from app.db import db_path, migrate
from app.deps import get_today
from app.main import app

TODAY = date(2026, 10, 20)
FAKE_KEY = "test-key-not-real"
# anthropic 2.x 는 httpx 가 아니라 httpx2 를 쓴다. 예외 객체를 만들 때 같은 라이브러리를 써야 한다.
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

GOOD = '{"priority": "HIGH", "due_date": "2026-10-21", "reason": "내일까지라 급합니다."}'
NO_DATE = '{"priority": "NORMAL", "due_date": null, "reason": "단서가 없습니다."}'


@pytest.fixture(autouse=True)
def fixed_today():
    app.dependency_overrides[get_today] = lambda: TODAY
    yield
    app.dependency_overrides.pop(get_today, None)


@pytest.fixture(autouse=True)
def fake_key(monkeypatch):
    # 진짜 키가 아니다. 어떤 테스트도 실제 API 를 부르지 않는다.
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_KEY)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKFLOW_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    migrate()


@pytest.fixture
def client(db):
    creds = {"username": "alice", "password": "password1"}
    with TestClient(app) as c:
        assert c.post("/auth/register", json=creds).status_code == 201
        assert c.post("/auth/login", json=creds).status_code == 200
        yield c


@pytest.fixture
def anonymous(db):
    with TestClient(app) as c:
        yield c


def install_fake(monkeypatch, text=None, *, stop_reason="end_turn", content=None, error=None):
    """anthropic.Anthropic 을 가짜로 바꾸고, 가짜가 받은 호출 인자를 돌려준다."""
    calls = []
    if content is None:
        content = [SimpleNamespace(text=text)]
    reply = SimpleNamespace(stop_reason=stop_reason, content=content)

    def create(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return reply

    fake = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(ai.anthropic, "Anthropic", lambda **kwargs: fake)
    return calls


def status_error(cls, status):
    return cls("error", response=httpx2.Response(status, request=REQUEST), body=None)


def snapshot():
    conn = sqlite3.connect(db_path())
    try:
        return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()


def suggest(client, **overrides):
    body = {"title": "보고서 마무리", "description": "내일까지", **overrides}
    return client.post("/tasks/suggest", json=body)


# --- 정상 ---


@pytest.mark.parametrize(
    "text",
    [
        GOOD,
        f"```json\n{GOOD}\n```",
        f"  \n```json\n{GOOD}\n```\n  ",
        f"```\n{GOOD}\n```",
        f"  {GOOD}  ",
    ],
)
def test_reads_plain_and_fenced_json(client, monkeypatch, text):
    install_fake(monkeypatch, text)
    res = suggest(client)
    assert res.status_code == 200
    assert res.json() == {
        "priority": "HIGH",
        "due_date": "2026-10-21",
        "reason": "내일까지라 급합니다.",
    }


def test_null_due_date_is_allowed(client, monkeypatch):
    install_fake(monkeypatch, NO_DATE)
    res = suggest(client)
    assert res.status_code == 200
    assert res.json()["due_date"] is None
    assert res.json()["priority"] == "NORMAL"


def test_past_due_date_is_not_rejected(client, monkeypatch):
    install_fake(
        monkeypatch, '{"priority": "LOW", "due_date": "2020-01-01", "reason": "지난 날짜"}'
    )
    assert suggest(client).status_code == 200


# --- 호출 내용 ---


def test_call_uses_model_thinking_off_prompt_and_template(client, monkeypatch):
    calls = install_fake(monkeypatch, GOOD)
    assert suggest(client, title="보고서", description="내일까지").status_code == 200
    (call,) = calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert call["system"] == ai.SYSTEM_PROMPT
    assert call["messages"] == [
        {
            "role": "user",
            "content": (
                "<task>\n<title>보고서</title>\n"
                "<description>내일까지</description>\n"
                "<today>2026-10-20</today>\n</task>"
            ),
        }
    ]


def test_empty_description_becomes_none_marker(client, monkeypatch):
    calls = install_fake(monkeypatch, GOOD)
    body = {"title": "보고서"}
    assert client.post("/tasks/suggest", json=body).status_code == 200
    assert "<description>(없음)</description>" in calls[0]["messages"][0]["content"]


def test_key_is_read_from_environment_only(client, monkeypatch):
    seen = {}
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                stop_reason="end_turn", content=[SimpleNamespace(text=GOOD)]
            )
        )
    )

    def factory(**kwargs):
        seen.update(kwargs)
        return fake

    monkeypatch.setattr(ai.anthropic, "Anthropic", factory)
    assert suggest(client).status_code == 200
    assert seen["api_key"] == FAKE_KEY


# --- 502: 제안 실패 ---


@pytest.mark.parametrize(
    "text",
    [
        '{"priority": "URGENT", "due_date": null, "reason": "x"}',
        '{"priority": "high", "due_date": null, "reason": "x"}',
        '{"priority": "HIGH", "due_date": "20261020", "reason": "x"}',
        '{"priority": "HIGH", "due_date": "2026-02-30", "reason": "x"}',
        '{"priority": "HIGH", "due_date": "2026-10-21T09:00:00", "reason": "x"}',
        '{"priority": "HIGH", "due_date": 20261021, "reason": "x"}',
        '{"priority": "HIGH", "due_date": null}',
        '{"due_date": null, "reason": "x"}',
        '{"priority": "HIGH", "due_date": null, "reason": 3}',
        "알겠습니다. 우선순위는 높음입니다.",
        "[]",
        "",
        '```json\n{"priority": "HIGH"',
    ],
)
def test_bad_answer_is_502(client, monkeypatch, text):
    install_fake(monkeypatch, text)
    before = snapshot()
    res = suggest(client)
    assert res.status_code == 502
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def test_truncated_answer_is_502(client, monkeypatch):
    # 잘린 답은 JSON 이 우연히 닫혀 있어도 거절한다.
    install_fake(monkeypatch, GOOD, stop_reason="max_tokens")
    assert suggest(client).status_code == 502


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="thinking")]])
def test_empty_or_non_text_content_is_502(client, monkeypatch, content):
    install_fake(monkeypatch, content=content)
    assert suggest(client).status_code == 502


def test_other_api_error_is_502(client, monkeypatch):
    install_fake(monkeypatch, error=status_error(anthropic.InternalServerError, 500))
    assert suggest(client).status_code == 502


# --- 503: 꺼짐 · 한도 · 바쁨 ---


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_is_503_and_no_call(client, monkeypatch, value):
    calls = install_fake(monkeypatch, GOOD)
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    before = snapshot()
    res = suggest(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert calls == []
    assert snapshot() == before


def test_rejected_key_is_503_off(client, monkeypatch):
    install_fake(monkeypatch, error=status_error(anthropic.AuthenticationError, 401))
    res = suggest(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert FAKE_KEY not in res.text


@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.RateLimitError, 429),
        status_error(anthropic.APIStatusError, 529),
        status_error(anthropic.APIStatusError, 503),
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.APITimeoutError(request=REQUEST),
    ],
)
def test_limit_or_busy_is_503_with_message(client, monkeypatch, error):
    install_fake(monkeypatch, error=error)
    before = snapshot()
    res = suggest(client)
    assert res.status_code == 503
    assert res.json() == {"detail": ai.AI_BUSY.detail}
    assert snapshot() == before


# --- 로그인 · 입력 ---


def test_requires_login(anonymous, monkeypatch):
    calls = install_fake(monkeypatch, GOOD)
    assert suggest(anonymous).status_code == 401
    assert calls == []


def test_login_is_checked_before_input(anonymous, monkeypatch):
    install_fake(monkeypatch, GOOD)
    assert anonymous.post("/tasks/suggest", json={"title": ""}).status_code == 401


@pytest.mark.parametrize("title", ["", "   ", "가" * 21])
def test_bad_title_is_422_and_no_call(client, monkeypatch, title):
    calls = install_fake(monkeypatch, GOOD)
    assert suggest(client, title=title).status_code == 422
    assert calls == []


def test_missing_title_is_422(client, monkeypatch):
    install_fake(monkeypatch, GOOD)
    assert client.post("/tasks/suggest", json={"description": "x"}).status_code == 422


# --- 저장소 ---


def test_suggest_never_changes_tasks(client, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "기존", "description": "", "status": "TODO"}
    )
    assert created.status_code == 201
    before = snapshot()
    install_fake(monkeypatch, GOOD)
    assert suggest(client).status_code == 200
    assert snapshot() == before
    assert len(client.get("/tasks").json()) == 1


# --- 원인 로그 (503 이 왜 났는지 서버 로그로 구분한다) ---


def ai_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.ai"]


def test_missing_key_is_logged(client, monkeypatch, caplog):
    install_fake(monkeypatch, GOOD)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert suggest(client).status_code == 503
    assert any("ANTHROPIC_API_KEY" in m for m in ai_logs(caplog))


@pytest.mark.parametrize(
    ("error", "kind", "status"),
    [
        (status_error(anthropic.AuthenticationError, 401), "AuthenticationError", "401"),
        (status_error(anthropic.RateLimitError, 429), "RateLimitError", "429"),
        (anthropic.APIConnectionError(request=REQUEST), "APIConnectionError", "None"),
        (status_error(anthropic.InternalServerError, 500), "InternalServerError", "500"),
    ],
)
def test_api_error_logs_kind_and_status_only(client, monkeypatch, caplog, error, kind, status):
    install_fake(monkeypatch, error=error)
    suggest(client)
    logs = ai_logs(caplog)
    assert any(kind in m and f"상태={status}" in m for m in logs)
    # 키 · 요청 본문 · SDK 메시지는 로그에 남기지 않는다.
    assert not any(FAKE_KEY in m or "보고서 마무리" in m or "error" in m.lower() for m in logs)
