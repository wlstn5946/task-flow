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
EMPTY = {"top3": [], "later": [], "cheer": "오늘은 비어 있어요."}


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


def status_error(cls, status):
    return cls("error", response=httpx2.Response(status, request=REQUEST), body=None)


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


def reply(top3=(), later=(), cheer="힘내요."):
    return json.dumps(
        {"top3": [{"id": i, "reason": f"이유 {i}"} for i in top3], "later": list(later), "cheer": cheer},
        ensure_ascii=False,
    )


def briefing(client):
    return client.post("/tasks/briefing")


def sent_tasks(fake):
    """모델에 보낸 <tasks> JSON 을 목록으로 읽는다."""
    content = fake.calls[0]["messages"][0]["content"]
    return json.loads(content.split("<tasks>")[1].split("</tasks>")[0])


@pytest.fixture
def three(client):
    return [add(client, f"할 일 {i}") for i in range(1, 4)]


# --- 정상 ---


def test_returns_top3_later_and_cheer(client, monkeypatch, three):
    a, b, c = three
    install_fake(monkeypatch, reply([b, a], [c], "오늘도 화이팅!"))
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == {
        "top3": [{"id": b, "reason": f"이유 {b}"}, {"id": a, "reason": f"이유 {a}"}],
        "later": [c],
        "cheer": "오늘도 화이팅!",
    }


@pytest.mark.parametrize(
    "wrap",
    [
        lambda s: f"  {s}  ",
        lambda s: f"```json\n{s}\n```",
        lambda s: f"```\n{s}\n```",
    ],
)
def test_reads_plain_and_fenced_json(client, monkeypatch, three, wrap):
    install_fake(monkeypatch, wrap(reply(three[:1], three[1:])))
    res = briefing(client)
    assert res.status_code == 200
    assert [p["id"] for p in res.json()["top3"]] == three[:1]
    assert res.json()["later"] == three[1:]


def test_empty_top3_and_later_are_allowed(client, monkeypatch, three):
    install_fake(monkeypatch, reply())
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == {"top3": [], "later": [], "cheer": "힘내요."}


# --- 보낸 내용 ---


def test_call_uses_model_thinking_off_prompt_and_limits(client, monkeypatch, three):
    fake = install_fake(monkeypatch, reply(three[:1]))
    assert briefing(client).status_code == 200
    (call,) = fake.calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert call["system"] == ai.BRIEFING_SYSTEM_PROMPT
    assert call["max_tokens"] == 1500
    assert call["messages"][0]["role"] == "user"
    (kwargs,) = fake.client_kwargs
    assert kwargs["api_key"] == FAKE_KEY
    assert kwargs["timeout"] == ai.BRIEFING_TIMEOUT_SECONDS == 30.0


def test_sends_only_my_unfinished_tasks_without_description(client, other, monkeypatch):
    mine = add(client, "내 일", description="비밀 설명 문장")
    progress = add(client, "진행 중", status="IN_PROGRESS")
    add(client, "끝낸 일", status="DONE")
    add(other, "남의 일")
    fake = install_fake(monkeypatch, reply([mine]))
    assert briefing(client).status_code == 200
    sent = sent_tasks(fake)
    assert [t["id"] for t in sent] == [mine, progress]
    assert all(set(t) == {"id", "title", "priority", "due_date", "overdue"} for t in sent)
    content = fake.calls[0]["messages"][0]["content"]
    assert "비밀 설명 문장" not in content
    assert "남의 일" not in content
    assert "끝낸 일" not in content
    assert "IN_PROGRESS" not in content
    assert content.endswith("<today>2026-10-20</today>")


def test_overdue_and_today_values(client, monkeypatch):
    late = add(client, "지난 일", due_date="2026-10-19")
    same = add(client, "오늘 일", due_date="2026-10-20")
    later = add(client, "나중 일", due_date="2026-10-21")
    none = add(client, "기한 없음")
    fake = install_fake(monkeypatch, reply([late]))
    assert briefing(client).status_code == 200
    by_id = {t["id"]: t for t in sent_tasks(fake)}
    assert by_id[late]["overdue"] is True
    # 당일 마감은 기한 초과가 아니다.
    assert by_id[same]["overdue"] is False
    assert by_id[later]["overdue"] is False
    assert by_id[none] == {
        "id": none,
        "title": "기한 없음",
        "priority": "NORMAL",
        "due_date": None,
        "overdue": False,
    }
    assert by_id[late]["due_date"] == "2026-10-19"


def test_sent_order_follows_list_order(client, monkeypatch):
    low = add(client, "낮음", priority="LOW")
    normal = add(client, "보통")
    high = add(client, "높음", priority="HIGH")
    soon = add(client, "곧", due_date="2026-10-25")
    late = add(client, "초과", priority="LOW", due_date="2026-10-01")
    fake = install_fake(monkeypatch, reply([late]))
    assert briefing(client).status_code == 200
    expected = [t["id"] for t in client.get("/tasks").json()]
    assert [t["id"] for t in sent_tasks(fake)] == expected
    assert expected == [late, high, soon, normal, low]


# --- 걸러내기 ---


def test_unknown_ids_are_dropped_from_top3_and_later(client, monkeypatch, three):
    a, b, c = three
    install_fake(monkeypatch, reply([9999, a], [8888, b, c]))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == [a]
    assert res["later"] == [b, c]


def test_other_users_task_id_is_dropped(client, other, monkeypatch, three):
    foreign = add(other, "남의 일")
    install_fake(monkeypatch, reply([foreign, three[0]], [foreign]))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == [three[0]]
    assert res["later"] == []


def test_done_task_id_is_dropped(client, monkeypatch, three):
    done = add(client, "끝낸 일", status="DONE")
    install_fake(monkeypatch, reply([done, three[0]], [done]))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == [three[0]]
    assert res["later"] == []


def test_top3_keeps_first_three_only(client, monkeypatch):
    ids = [add(client, f"일 {i}") for i in range(5)]
    install_fake(monkeypatch, reply(ids, []))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == ids[:3]
    # 넘친 항목은 later 로 옮기지 않는다.
    assert res["later"] == []


def test_duplicate_ids_are_removed(client, monkeypatch, three):
    a, b, c = three
    install_fake(monkeypatch, reply([a, a, b, a], [c, c]))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == [a, b]
    assert res["later"] == [c]


def test_unknown_ids_do_not_use_up_top3_slots(client, monkeypatch):
    ids = [add(client, f"일 {i}") for i in range(3)]
    install_fake(monkeypatch, reply([7001, 7002, 7003, *ids], []))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == ids


def test_later_drops_ids_already_in_top3(client, monkeypatch, three):
    a, b, c = three
    install_fake(monkeypatch, reply([a], [a, b, c]))
    res = briefing(client).json()
    assert [p["id"] for p in res["top3"]] == [a]
    assert res["later"] == [b, c]


def test_all_fake_ids_gives_filtered_result_not_502(client, monkeypatch, three):
    install_fake(monkeypatch, reply([9001, 9002], [9003], "응원"))
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == {"top3": [], "later": [], "cheer": "응원"}


def test_unknown_keys_are_ignored(client, monkeypatch, three):
    text = json.dumps(
        {"top3": [{"id": three[0], "reason": "x", "extra": 1}], "later": [], "cheer": "c", "more": 2}
    )
    install_fake(monkeypatch, text)
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == {"top3": [{"id": three[0], "reason": "x"}], "later": [], "cheer": "c"}


# --- 0개: 모델을 부르지 않는다 ---


def test_no_tasks_returns_empty_briefing_without_call(client, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


def test_all_done_returns_empty_briefing_without_call(client, monkeypatch):
    add(client, "끝 1", status="DONE")
    add(client, "끝 2", status="DONE")
    fake = install_fake(monkeypatch, reply())
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


def test_only_others_tasks_returns_empty_briefing(client, other, monkeypatch):
    add(other, "남의 일")
    fake = install_fake(monkeypatch, reply())
    assert briefing(client).json() == EMPTY
    assert fake.calls == []


@pytest.mark.parametrize("value", [None, "", "   "])
def test_no_tasks_is_200_even_without_key(client, monkeypatch, value):
    fake = install_fake(monkeypatch, reply())
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    res = briefing(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


# --- 502: 구조가 틀린 답 ---


def top(*picks):
    return json.dumps({"top3": list(picks), "later": [], "cheer": "c"})


@pytest.mark.parametrize(
    "text",
    [
        "알겠습니다. 브리핑입니다.",
        "[]",
        "{}",
        "",
        '```json\n{"top3": [',
        json.dumps({"later": [], "cheer": "c"}),
        json.dumps({"top3": [], "cheer": "c"}),
        json.dumps({"top3": [], "later": []}),
        json.dumps({"top3": "x", "later": [], "cheer": "c"}),
        json.dumps({"top3": {}, "later": [], "cheer": "c"}),
        json.dumps({"top3": None, "later": [], "cheer": "c"}),
        json.dumps({"top3": [], "later": "1", "cheer": "c"}),
        json.dumps({"top3": [], "later": None, "cheer": "c"}),
        json.dumps({"top3": [], "later": ["abc"], "cheer": "c"}),
        json.dumps({"top3": [], "later": [[1]], "cheer": "c"}),
        json.dumps({"top3": [], "later": [], "cheer": 5}),
        json.dumps({"top3": [], "later": [], "cheer": None}),
        top({"id": 1}),
        top({"reason": "x"}),
        top({"id": "abc", "reason": "x"}),
        top({"id": None, "reason": "x"}),
        top({"id": 1, "reason": 5}),
        top("문자열 항목"),
        top(None),
        top(1),
    ],
)
def test_bad_shape_is_502(client, monkeypatch, three, text):
    install_fake(monkeypatch, text)
    before = snapshot()
    res = briefing(client)
    assert res.status_code == 502
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def test_truncated_answer_is_502(client, monkeypatch, three):
    # 잘린 답은 JSON 이 우연히 닫혀 있어도 거절한다.
    install_fake(monkeypatch, reply(three[:1]), stop_reason="max_tokens")
    assert briefing(client).status_code == 502


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="thinking")]])
def test_empty_or_non_text_content_is_502(client, monkeypatch, three, content):
    install_fake(monkeypatch, content=content)
    assert briefing(client).status_code == 502


def test_other_api_error_is_502(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.InternalServerError, 500))
    assert briefing(client).status_code == 502


# --- 503: 꺼짐 · 한도 · 바쁨 ---


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_is_503_and_no_call(client, monkeypatch, three, value):
    fake = install_fake(monkeypatch, reply(three[:1]))
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    before = snapshot()
    res = briefing(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert fake.calls == []
    assert snapshot() == before


def test_rejected_key_is_503_off(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.AuthenticationError, 401))
    res = briefing(client)
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
    res = briefing(client)
    assert res.status_code == 503
    assert res.json() == {"detail": ai.AI_BUSY.detail}
    assert snapshot() == before


# --- 로그인 ---


def test_requires_login(anonymous, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    assert briefing(anonymous).status_code == 401
    assert fake.calls == []


# --- 저장소 · 로그 ---


def test_briefing_never_changes_tasks(client, monkeypatch, three):
    before = snapshot()
    install_fake(monkeypatch, reply(three[:2], three[2:]))
    assert briefing(client).status_code == 200
    assert snapshot() == before
    assert len(client.get("/tasks").json()) == 3


def ai_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.ai"]


def test_missing_key_is_logged(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, reply())
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert briefing(client).status_code == 503
    assert any("ANTHROPIC_API_KEY" in m for m in ai_logs(caplog))


def test_api_error_logs_kind_and_status_only(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, error=status_error(anthropic.RateLimitError, 429))
    briefing(client)
    logs = ai_logs(caplog)
    assert any("RateLimitError" in m and "상태=429" in m for m in logs)
    # 키 · 요청 본문 · 할 일 제목 · SDK 메시지는 로그에 남기지 않는다.
    assert not any(
        FAKE_KEY in m or "할 일" in m or "error" in m.lower() for m in logs
    )


# --- DB 의 규칙 밖 마감일 ---


def set_raw_due_date(task_id, value):
    """API 를 거치지 않고 DB 에 마감일을 직접 쓴다. CHECK 가 통과시키는 규칙 밖 글을 만들기 위해서이다."""
    conn = sqlite3.connect(db_path())
    try:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (value, task_id))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("bad", ["다음주", "10/20", "2026-02-30", "2026-10-21T09:00:00", ""])
def test_due_date_outside_the_rules_is_sent_as_none(client, monkeypatch, bad):
    task_id = add(client, "표본")
    set_raw_due_date(task_id, bad)
    fake = install_fake(monkeypatch, reply(top3=[task_id]))
    assert briefing(client).status_code == 200
    (sent,) = sent_tasks(fake)
    # 규칙 밖 글은 모델에 가지 않고, 마감일이 없으니 기한 초과도 아니다.
    assert sent["due_date"] is None
    assert sent["overdue"] is False
    content = fake.calls[0]["messages"][0]["content"]
    assert bad == "" or bad not in content


def test_valid_due_date_is_sent_unchanged(client, monkeypatch):
    late = add(client, "지난 일", due_date="2026-10-19")
    soon = add(client, "다음 일", due_date="2026-10-21")
    fake = install_fake(monkeypatch, reply(top3=[late]))
    assert briefing(client).status_code == 200
    sent = {t["id"]: t for t in sent_tasks(fake)}
    assert (sent[late]["due_date"], sent[late]["overdue"]) == ("2026-10-19", True)
    assert (sent[soon]["due_date"], sent[soon]["overdue"]) == ("2026-10-21", False)
