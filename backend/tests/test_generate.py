import json
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
GOAL = "블로그 개설"


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


def item(i=1, **overrides):
    return {
        "title": f"할 일 {i}",
        "description": "설명",
        "priority": "NORMAL",
        "due_date": None,
        **overrides,
    }


def items(n=4):
    return [item(i) for i in range(1, n + 1)]


def answer(tasks):
    return json.dumps({"tasks": tasks}, ensure_ascii=False)


def install_fake(monkeypatch, text=None, *, stop_reason="end_turn", content=None, error=None):
    """anthropic.Anthropic 을 가짜로 바꾸고, 호출 인자와 클라이언트 생성 인자를 돌려준다."""
    calls = []
    client_kwargs = []
    if content is None:
        content = [SimpleNamespace(text=text)]
    reply = SimpleNamespace(stop_reason=stop_reason, content=content)

    def create(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return reply

    fake = SimpleNamespace(messages=SimpleNamespace(create=create))

    def factory(**kwargs):
        client_kwargs.append(kwargs)
        return fake

    monkeypatch.setattr(ai.anthropic, "Anthropic", factory)
    return SimpleNamespace(calls=calls, client_kwargs=client_kwargs)


def status_error(cls, status):
    return cls("error", response=httpx2.Response(status, request=REQUEST), body=None)


def snapshot():
    conn = sqlite3.connect(db_path())
    try:
        return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()


def generate(client, **overrides):
    return client.post("/tasks/generate", json={"title": GOAL, **overrides})


# --- 정상 ---


@pytest.mark.parametrize("n", [3, 4, 5])
def test_three_to_five_tasks_are_returned(client, monkeypatch, n):
    install_fake(monkeypatch, answer(items(n)))
    res = generate(client)
    assert res.status_code == 200
    assert res.json() == {"tasks": items(n)}


@pytest.mark.parametrize(
    "wrap",
    [
        lambda s: s,
        lambda s: f"  {s}  ",
        lambda s: f"```json\n{s}\n```",
        lambda s: f"  \n```json\n{s}\n```\n  ",
        lambda s: f"```\n{s}\n```",
    ],
)
def test_reads_plain_and_fenced_json(client, monkeypatch, wrap):
    install_fake(monkeypatch, wrap(answer(items(3))))
    res = generate(client)
    assert res.status_code == 200
    assert res.json() == {"tasks": items(3)}


def test_allows_null_date_past_date_and_empty_description(client, monkeypatch):
    tasks = [
        item(1, due_date=None, description=""),
        item(2, due_date="2020-01-01", priority="LOW"),
        item(3, due_date="2026-10-21", priority="HIGH"),
    ]
    install_fake(monkeypatch, answer(tasks))
    res = generate(client)
    assert res.status_code == 200
    assert res.json() == {"tasks": tasks}


def test_title_is_trimmed_and_unknown_keys_are_ignored(client, monkeypatch):
    tasks = [item(1, title="  자리  ", reason="모르는 키"), item(2), item(3)]
    install_fake(monkeypatch, answer(tasks))
    res = generate(client)
    assert res.status_code == 200
    first = res.json()["tasks"][0]
    assert first["title"] == "자리"
    assert "reason" not in first


# --- 호출 내용 ---


def test_call_uses_model_thinking_off_prompt_and_template(client, monkeypatch):
    fake = install_fake(monkeypatch, answer(items(3)))
    assert generate(client, title="블로그 개설").status_code == 200
    (call,) = fake.calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert call["system"] == ai.GENERATE_SYSTEM_PROMPT
    assert call["max_tokens"] == 1500
    assert call["messages"] == [
        {
            "role": "user",
            "content": (
                "<request>\n<title>블로그 개설</title>\n"
                "<today>2026-10-20</today>\n</request>"
            ),
        }
    ]


def test_key_comes_from_environment_and_timeout_is_longer(client, monkeypatch):
    fake = install_fake(monkeypatch, answer(items(3)))
    assert generate(client).status_code == 200
    (kwargs,) = fake.client_kwargs
    assert kwargs["api_key"] == FAKE_KEY
    assert kwargs["timeout"] == ai.GENERATE_TIMEOUT_SECONDS == 30.0


def test_suggest_defaults_are_unchanged(client, monkeypatch):
    # generate 를 위해 call_model 에 인자를 더했지만 suggest 의 호출 값은 그대로여야 한다.
    fake = install_fake(
        monkeypatch, '{"priority": "HIGH", "due_date": null, "reason": "x"}'
    )
    res = client.post("/tasks/suggest", json={"title": "보고서", "description": ""})
    assert res.status_code == 200
    (call,) = fake.calls
    assert call["system"] == ai.SYSTEM_PROMPT
    assert call["max_tokens"] == 300
    assert fake.client_kwargs[0]["timeout"] == 20.0


# --- 502: 전체 실패 ---


@pytest.mark.parametrize(
    "text",
    [
        answer(items(2)),
        answer(items(6)),
        answer([]),
        json.dumps({"tasks": {"a": 1}}),
        json.dumps({"tasks": "할 일"}),
        json.dumps({"tasks": None}),
        json.dumps({"items": items(3)}, ensure_ascii=False),
        json.dumps(items(3), ensure_ascii=False),
        "{}",
        "알겠습니다. 할 일을 나누었습니다.",
        "[]",
        "",
        '```json\n{"tasks": [',
    ],
)
def test_bad_shape_is_502(client, monkeypatch, text):
    install_fake(monkeypatch, text)
    before = snapshot()
    res = generate(client)
    assert res.status_code == 502
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def without(key):
    """한 키가 빠진 항목."""
    broken = item(3)
    del broken[key]
    return broken


@pytest.mark.parametrize(
    "bad",
    [
        item(3, title=""),
        item(3, title="   "),
        item(3, title="가" * 21),
        item(3, title=5),
        item(3, title=None),
        item(3, priority="URGENT"),
        item(3, priority="high"),
        item(3, priority=None),
        item(3, due_date="20261020"),
        item(3, due_date="2026-02-30"),
        item(3, due_date="2026-10-21T09:00:00"),
        item(3, due_date=20261021),
        item(3, due_date=""),
        item(3, description=None),
        item(3, description=5),
        without("title"),
        without("description"),
        without("priority"),
        without("due_date"),
        "문자열 항목",
        None,
    ],
)
@pytest.mark.parametrize("n", [3, 5])
def test_one_bad_item_fails_the_whole_answer(client, monkeypatch, n, bad):
    tasks = [item(i) for i in range(1, n)] + [bad]
    install_fake(monkeypatch, answer(tasks))
    before = snapshot()
    res = generate(client)
    assert res.status_code == 502
    # 맞는 항목만 걸러서 돌려주지 않는다.
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def test_truncated_answer_is_502(client, monkeypatch):
    # 잘린 답은 JSON 이 우연히 닫혀 있어도 거절한다.
    install_fake(monkeypatch, answer(items(3)), stop_reason="max_tokens")
    assert generate(client).status_code == 502


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="thinking")]])
def test_empty_or_non_text_content_is_502(client, monkeypatch, content):
    install_fake(monkeypatch, content=content)
    assert generate(client).status_code == 502


def test_other_api_error_is_502(client, monkeypatch):
    install_fake(monkeypatch, error=status_error(anthropic.InternalServerError, 500))
    assert generate(client).status_code == 502


# --- 503: 꺼짐 · 한도 · 바쁨 ---


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_is_503_and_no_call(client, monkeypatch, value):
    fake = install_fake(monkeypatch, answer(items(3)))
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    before = snapshot()
    res = generate(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert fake.calls == []
    assert snapshot() == before


def test_rejected_key_is_503_off(client, monkeypatch):
    install_fake(monkeypatch, error=status_error(anthropic.AuthenticationError, 401))
    res = generate(client)
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
    res = generate(client)
    assert res.status_code == 503
    assert res.json() == {"detail": ai.AI_BUSY.detail}
    assert snapshot() == before


# --- 로그인 · 입력 ---


def test_requires_login(anonymous, monkeypatch):
    fake = install_fake(monkeypatch, answer(items(3)))
    assert generate(anonymous).status_code == 401
    assert fake.calls == []


def test_login_is_checked_before_input(anonymous, monkeypatch):
    install_fake(monkeypatch, answer(items(3)))
    assert anonymous.post("/tasks/generate", json={"title": ""}).status_code == 401


@pytest.mark.parametrize("title", ["", "   ", "가" * 21])
def test_bad_title_is_422_and_no_call(client, monkeypatch, title):
    fake = install_fake(monkeypatch, answer(items(3)))
    assert generate(client, title=title).status_code == 422
    assert fake.calls == []


def test_missing_title_is_422(client, monkeypatch):
    install_fake(monkeypatch, answer(items(3)))
    assert client.post("/tasks/generate", json={}).status_code == 422


def test_description_in_request_is_ignored(client, monkeypatch):
    fake = install_fake(monkeypatch, answer(items(3)))
    assert generate(client, description="무시되는 설명").status_code == 200
    assert "무시되는 설명" not in fake.calls[0]["messages"][0]["content"]


# --- 저장소 · 로그 ---


def test_generate_never_changes_tasks(client, monkeypatch):
    created = client.post(
        "/tasks", json={"title": "기존", "description": "", "status": "TODO"}
    )
    assert created.status_code == 201
    before = snapshot()
    install_fake(monkeypatch, answer(items(5)))
    assert generate(client).status_code == 200
    assert snapshot() == before
    assert len(client.get("/tasks").json()) == 1


def ai_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.ai"]


def test_missing_key_is_logged(client, monkeypatch, caplog):
    install_fake(monkeypatch, answer(items(3)))
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert generate(client).status_code == 503
    assert any("ANTHROPIC_API_KEY" in m for m in ai_logs(caplog))


def test_api_error_logs_kind_and_status_only(client, monkeypatch, caplog):
    install_fake(monkeypatch, error=status_error(anthropic.RateLimitError, 429))
    generate(client)
    logs = ai_logs(caplog)
    assert any("RateLimitError" in m and "상태=429" in m for m in logs)
    # 키 · 요청 본문 · SDK 메시지는 로그에 남기지 않는다.
    assert not any(FAKE_KEY in m or GOAL in m or "error" in m.lower() for m in logs)
