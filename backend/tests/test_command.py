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
SDK_MESSAGE = "sdk-message-not-for-logs"  # SDK 예외가 들고 있는 글. 로그에 나오면 안 된다.
# anthropic 2.x 는 httpx 가 아니라 httpx2 를 쓴다. 예외 객체를 만들 때 같은 라이브러리를 써야 한다.
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


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
def other(db):
    # 다른 사람의 할 일을 만들기 위한 두 번째 로그인.
    creds = {"username": "bobby", "password": "password1"}
    with TestClient(app) as c:
        assert c.post("/auth/register", json=creds).status_code == 201
        assert c.post("/auth/login", json=creds).status_code == 200
        yield c


@pytest.fixture
def anonymous(db):
    with TestClient(app) as c:
        yield c


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


def status_error(cls, status, message="error"):
    return cls(message, response=httpx2.Response(status, request=REQUEST), body=None)


def snapshot():
    conn = sqlite3.connect(db_path())
    try:
        return conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()


def add(c, title, status="TODO", priority="NORMAL", due_date=None, description=""):
    res = c.post(
        "/tasks",
        json={
            "title": title,
            "description": description,
            "status": status,
            "priority": priority,
            "due_date": due_date,
        },
    )
    assert res.status_code == 201
    return res.json()["id"]


def act(kind, id=None, title=None, priority=None, due_date=None):
    return {"kind": kind, "id": id, "title": title, "priority": priority, "due_date": due_date}


def reply(actions=(), ask=None):
    return json.dumps({"actions": list(actions), "ask": ask}, ensure_ascii=False)


def command(client, text="견적서 끝냈어"):
    return client.post("/tasks/command", json={"text": text})


def sent_tasks(fake):
    """모델에 보낸 <tasks> JSON 을 목록으로 읽는다."""
    content = fake.calls[0]["messages"][0]["content"]
    return json.loads(content.split("<tasks>")[1].split("</tasks>")[0])


@pytest.fixture
def three(client):
    return [add(client, f"할 일 {i}") for i in range(1, 4)]


# --- 정상 ---


def test_returns_add_due_and_done_actions(client, monkeypatch, three):
    a, b, c = three
    install_fake(
        monkeypatch,
        reply(
            [
                act("add", title="보고서 쓰기", priority="HIGH", due_date="2026-10-21"),
                act("due", b, due_date="2026-10-25"),
                act("done", c),
            ]
        ),
    )
    res = command(client)
    assert res.status_code == 200
    assert res.json() == {
        "actions": [
            act("add", title="보고서 쓰기", priority="HIGH", due_date="2026-10-21"),
            act("due", b, due_date="2026-10-25"),
            act("done", c),
        ],
        "ask": None,
    }


def test_add_without_priority_is_normal_and_ignores_id(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("add", id=three[0], title="새 일")]))
    res = command(client)
    assert res.json()["actions"] == [act("add", title="새 일", priority="NORMAL")]


def test_due_and_done_clear_unused_fields(client, monkeypatch, three):
    a, b, _ = three
    install_fake(
        monkeypatch,
        reply(
            [
                act("due", a, title="딴 제목", priority="HIGH", due_date="2026-10-22"),
                act("done", b, title="딴 제목", priority="HIGH"),
            ]
        ),
    )
    assert command(client).json()["actions"] == [
        act("due", a, due_date="2026-10-22"),
        act("done", b),
    ]


def test_past_due_date_is_allowed(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("due", three[0], due_date="2026-10-01")]))
    assert command(client).json()["actions"] == [act("due", three[0], due_date="2026-10-01")]


def test_ask_is_null_when_actions_remain_even_if_model_sent_one(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("done", three[0])], ask="이건 무시됨"))
    assert command(client).json()["ask"] is None


@pytest.mark.parametrize(
    "wrap",
    [
        lambda s: f"  {s}  ",
        lambda s: f"```json\n{s}\n```",
        lambda s: f"```\n{s}\n```",
    ],
)
def test_reads_plain_and_fenced_json(client, monkeypatch, three, wrap):
    install_fake(monkeypatch, wrap(reply([act("done", three[0])])))
    res = command(client)
    assert res.status_code == 200
    assert res.json()["actions"] == [act("done", three[0])]


def test_missing_optional_keys_are_read_as_null(client, monkeypatch, three):
    install_fake(
        monkeypatch,
        json.dumps({"actions": [{"kind": "done", "id": three[0]}]}),
    )
    assert command(client).json() == {"actions": [act("done", three[0])], "ask": None}


# --- 입력 ---


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_blank_text_is_422_with_reason_and_no_call(client, monkeypatch, text):
    fake = install_fake(monkeypatch, reply())
    res = command(client, text)
    assert res.status_code == 422
    assert "명령은 비워 둘 수 없습니다." in res.text
    assert fake.calls == []


def test_text_over_200_is_422_with_reason_and_no_call(client, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    res = command(client, "가" * 201)
    assert res.status_code == 422
    assert "명령은 200글자까지입니다." in res.text
    assert fake.calls == []


def test_text_of_200_is_accepted_and_trimmed(client, monkeypatch):
    fake = install_fake(monkeypatch, reply([act("add", title="새 일")]))
    assert command(client, "  " + "가" * 200 + "  ").status_code == 200
    content = fake.calls[0]["messages"][0]["content"]
    assert content.startswith("<text>" + "가" * 200 + "</text>")


@pytest.mark.parametrize("body", [{}, {"text": None}, {"text": 5}, {"other": "x"}])
def test_missing_or_wrong_type_text_is_422(client, monkeypatch, body):
    fake = install_fake(monkeypatch, reply())
    assert client.post("/tasks/command", json=body).status_code == 422
    assert fake.calls == []


# --- 보낸 내용 ---


def test_call_uses_model_thinking_off_prompt_and_limits(client, monkeypatch, three):
    fake = install_fake(monkeypatch, reply([act("done", three[0])]))
    assert command(client).status_code == 200
    (call,) = fake.calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert call["system"] == ai.COMMAND_SYSTEM_PROMPT
    assert call["max_tokens"] == 1500
    assert call["messages"][0]["role"] == "user"
    (kwargs,) = fake.client_kwargs
    assert kwargs["api_key"] == FAKE_KEY
    assert kwargs["timeout"] == ai.COMMAND_TIMEOUT_SECONDS == 30.0


def test_sends_only_my_unfinished_tasks_without_description(client, other, monkeypatch):
    mine = add(client, "내 일", description="비밀 설명 문장")
    progress = add(client, "진행 중", status="IN_PROGRESS")
    add(client, "끝낸 일", status="DONE")
    add(other, "남의 일")
    fake = install_fake(monkeypatch, reply([act("done", mine)]))
    assert command(client, "내 일 끝냈어").status_code == 200
    sent = sent_tasks(fake)
    assert [t["id"] for t in sent] == [mine, progress]
    assert all(set(t) == {"id", "title", "priority", "due_date", "overdue"} for t in sent)
    content = fake.calls[0]["messages"][0]["content"]
    assert "비밀 설명 문장" not in content
    assert "남의 일" not in content
    assert "끝낸 일" not in content
    assert "IN_PROGRESS" not in content
    assert content.startswith("<text>내 일 끝냈어</text>")
    assert content.endswith("<today>2026-10-20</today>")


def test_calls_model_even_with_no_tasks(client, monkeypatch):
    fake = install_fake(monkeypatch, reply([act("add", title="첫 할 일")]))
    res = command(client, "첫 할 일 추가")
    assert res.status_code == 200
    assert len(fake.calls) == 1
    assert sent_tasks(fake) == []
    assert res.json()["actions"] == [act("add", title="첫 할 일", priority="NORMAL")]


# --- 걸러내기 ---


def test_drops_ids_not_sent_including_other_users_and_done(client, other, monkeypatch):
    mine = add(client, "내 일")
    done = add(client, "끝낸 일", status="DONE")
    theirs = add(other, "남의 일")
    install_fake(
        monkeypatch,
        reply(
            [
                act("done", theirs),
                act("due", theirs, due_date="2026-10-25"),
                act("done", done),
                act("done", 9999),
                act("done", mine),
            ]
        ),
    )
    assert command(client).json()["actions"] == [act("done", mine)]


def test_drops_due_and_done_without_id(client, monkeypatch, three):
    install_fake(
        monkeypatch,
        reply([act("due", None, due_date="2026-10-25"), act("done", None), act("done", three[0])]),
    )
    assert command(client).json()["actions"] == [act("done", three[0])]


@pytest.mark.parametrize(
    "bad", ["2026-02-30", "2026-10-25T09:00", "10월 25일", "2026/10/25", "내일", ""]
)
def test_drops_actions_with_bad_dates(client, monkeypatch, three, bad):
    install_fake(
        monkeypatch,
        reply(
            [
                act("add", title="날짜 틀림", due_date=bad),
                act("due", three[0], due_date=bad),
                act("done", three[1], due_date=bad),
                act("done", three[2]),
            ]
        ),
    )
    # 규칙 밖 날짜가 붙은 action 은 통째로 버린다. done 도 날짜 칸이 규칙 밖이면 버린다.
    assert command(client).json()["actions"] == [act("done", three[2])]


def test_due_without_date_is_dropped(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("due", three[0]), act("done", three[1])]))
    assert command(client).json()["actions"] == [act("done", three[1])]


@pytest.mark.parametrize("title", [None, "", "   ", "가" * 21])
def test_drops_add_with_bad_title(client, monkeypatch, three, title):
    install_fake(monkeypatch, reply([act("add", title=title), act("done", three[0])]))
    assert command(client).json()["actions"] == [act("done", three[0])]


def test_add_title_of_20_is_kept_and_trimmed(client, monkeypatch):
    install_fake(monkeypatch, reply([act("add", title="  " + "가" * 20 + "  ")]))
    assert command(client).json()["actions"][0]["title"] == "가" * 20


@pytest.mark.parametrize("priority", ["URGENT", "high", "낮음"])
def test_drops_add_with_bad_priority(client, monkeypatch, three, priority):
    install_fake(
        monkeypatch,
        reply([act("add", title="새 일", priority=priority), act("done", three[0])]),
    )
    assert command(client).json()["actions"] == [act("done", three[0])]


@pytest.mark.parametrize("kind", ["delete", "DONE", "", "update"])
def test_drops_unknown_kind(client, monkeypatch, three, kind):
    install_fake(monkeypatch, reply([act(kind, three[0]), act("done", three[1])]))
    assert command(client).json()["actions"] == [act("done", three[1])]


def test_drops_duplicate_done_and_due_but_keeps_adds(client, monkeypatch, three):
    a, b, _ = three
    install_fake(
        monkeypatch,
        reply(
            [
                act("done", a),
                act("done", a),
                act("due", b, due_date="2026-10-25"),
                act("due", b, due_date="2026-10-26"),
                act("add", title="같은 제목"),
                act("add", title="같은 제목"),
            ]
        ),
    )
    assert command(client).json()["actions"] == [
        act("done", a),
        act("due", b, due_date="2026-10-25"),
        act("add", title="같은 제목", priority="NORMAL"),
        act("add", title="같은 제목", priority="NORMAL"),
    ]


# --- ask ---


def test_empty_actions_returns_model_ask(client, monkeypatch, three):
    install_fake(monkeypatch, reply([], ask="어느 할 일인가요?"))
    assert command(client).json() == {"actions": [], "ask": "어느 할 일인가요?"}


@pytest.mark.parametrize("ask", [None, "", "   "])
def test_empty_actions_without_ask_uses_fallback(client, monkeypatch, three, ask):
    install_fake(monkeypatch, reply([], ask=ask))
    assert command(client).json() == {"actions": [], "ask": ai.COMMAND_FALLBACK_ASK}


def test_all_actions_dropped_becomes_ask(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("done", 9999)], ask="모델이 준 문장"))
    assert command(client).json() == {"actions": [], "ask": "모델이 준 문장"}


def test_all_actions_dropped_without_ask_uses_fallback(client, monkeypatch, three):
    install_fake(monkeypatch, reply([act("done", 9999)]))
    assert command(client).json() == {"actions": [], "ask": ai.COMMAND_FALLBACK_ASK}


# --- 502: 형식 위반 ---


def wrap_actions(*items):
    return json.dumps({"actions": list(items), "ask": None})


@pytest.mark.parametrize(
    "text",
    [
        "그냥 문장입니다",
        "",
        '```json\n{"actions": [',
        json.dumps({"ask": None}),
        json.dumps({"actions": "x", "ask": None}),
        json.dumps({"actions": {}, "ask": None}),
        json.dumps({"actions": None, "ask": None}),
        json.dumps({"actions": [], "ask": 5}),
        json.dumps({"actions": [], "ask": ["a"]}),
        wrap_actions({"id": 1}),
        wrap_actions({"kind": None}),
        wrap_actions({"kind": "done", "id": "abc"}),
        wrap_actions({"kind": "add", "title": 5}),
        wrap_actions({"kind": "add", "priority": 5}),
        wrap_actions({"kind": "due", "due_date": 5}),
        wrap_actions("문자열 항목"),
        wrap_actions(None),
        wrap_actions(1),
    ],
)
def test_bad_shape_is_502(client, monkeypatch, three, text):
    install_fake(monkeypatch, text)
    before = snapshot()
    res = command(client)
    assert res.status_code == 502
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def test_truncated_answer_is_502(client, monkeypatch, three):
    # 잘린 답은 JSON 이 우연히 닫혀 있어도 거절한다.
    install_fake(monkeypatch, reply([act("done", three[0])]), stop_reason="max_tokens")
    assert command(client).status_code == 502


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="thinking")]])
def test_empty_or_non_text_content_is_502(client, monkeypatch, three, content):
    install_fake(monkeypatch, content=content)
    assert command(client).status_code == 502


def test_other_api_error_is_502(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.InternalServerError, 500))
    assert command(client).status_code == 502


# --- 503: 꺼짐 · 한도 · 바쁨 ---


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_is_503_and_no_call(client, monkeypatch, three, value):
    fake = install_fake(monkeypatch, reply())
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    before = snapshot()
    res = command(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert fake.calls == []
    assert snapshot() == before


def test_rejected_key_is_503_off(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.AuthenticationError, 401))
    res = command(client)
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
def test_limit_or_busy_is_503_with_message(client, monkeypatch, three, error):
    install_fake(monkeypatch, error=error)
    before = snapshot()
    res = command(client)
    assert res.status_code == 503
    assert res.json() == {"detail": ai.AI_BUSY.detail}
    assert snapshot() == before


# --- 로그인 ---


def test_requires_login(anonymous, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    assert command(anonymous).status_code == 401
    assert fake.calls == []


# --- 저장소 · 로그 ---


def test_command_never_changes_tasks(client, monkeypatch, three):
    before = snapshot()
    install_fake(
        monkeypatch,
        reply(
            [
                act("add", title="새 일"),
                act("due", three[0], due_date="2026-10-25"),
                act("done", three[1]),
            ]
        ),
    )
    assert command(client).status_code == 200
    assert snapshot() == before
    assert len(client.get("/tasks").json()) == 3


def ai_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.ai"]


def test_missing_key_is_logged(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, reply())
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert command(client).status_code == 503
    assert any("ANTHROPIC_API_KEY" in m for m in ai_logs(caplog))


def test_api_error_logs_kind_and_status_only(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, error=status_error(anthropic.RateLimitError, 429, SDK_MESSAGE))
    command(client, "비밀 명령 문장")
    logs = ai_logs(caplog)
    assert any("RateLimitError" in m and "상태=429" in m for m in logs)
    # 키 · 요청 본문 · 명령 문장 · 할 일 제목 · SDK 메시지는 로그에 남기지 않는다.
    assert not any(
        FAKE_KEY in m or "비밀 명령 문장" in m or "할 일" in m or SDK_MESSAGE in m
        for m in logs
    )
