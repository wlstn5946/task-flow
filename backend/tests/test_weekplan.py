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

# 2026-10-20 은 화요일이다. 한 주는 10-20(화) ~ 10-26(월)이다.
TODAY = date(2026, 10, 20)
FAKE_KEY = "test-key-not-real"
SDK_MESSAGE = "sdk-message-not-for-logs"  # SDK 예외가 들고 있는 글. 로그에 나오면 안 된다.
# anthropic 2.x 는 httpx 가 아니라 httpx2 를 쓴다. 예외 객체를 만들 때 같은 라이브러리를 써야 한다.
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
EMPTY = {"plan": [], "note": ""}
NOTE = "이번 주 조언"


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
    reply_message = SimpleNamespace(stop_reason=stop_reason, content=content)

    def create(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return reply_message

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


def reply(*items):
    """items 는 (id, 날짜) 쌍이다. 모델이 돌려줄 JSON 글을 만든다. note 는 맨 위에 한 번만 둔다."""
    return json.dumps(
        {"plan": [{"id": i, "date": d} for i, d in items], "note": NOTE},
        ensure_ascii=False,
    )


def weekplan(client):
    return client.post("/tasks/weekplan")


def sent_tasks(fake):
    """모델에 보낸 <tasks> JSON 을 목록으로 읽는다."""
    content = fake.calls[0]["messages"][0]["content"]
    return json.loads(content.split("<tasks>")[1].split("</tasks>")[0])


@pytest.fixture
def three(client):
    return [add(client, f"할 일 {i}") for i in range(1, 4)]


# --- 주소 목록 ---


def test_openapi_lists_weekplan_post(client):
    assert "post" in client.get("/openapi.json").json()["paths"]["/tasks/weekplan"]


# --- 정상 ---


def test_returns_plan_with_server_made_date_text_and_db_title(client, monkeypatch, three):
    a, b, c = three
    install_fake(monkeypatch, reply((a, "2026-10-20"), (b, "2026-10-21"), (c, "2026-10-26")))
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json() == {
        "plan": [
            {"id": a, "date": "10월 20일 (화)", "title": "할 일 1"},
            {"id": b, "date": "10월 21일 (수)", "title": "할 일 2"},
            {"id": c, "date": "10월 26일 (월)", "title": "할 일 3"},
        ],
        "note": NOTE,
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
    install_fake(monkeypatch, wrap(reply((three[0], "2026-10-22"))))
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json()["plan"][0]["date"] == "10월 22일 (목)"


def test_date_text_weekdays_are_right_for_the_whole_week(client, monkeypatch):
    ids = [add(client, f"일 {i}") for i in range(7)]
    days = [f"2026-10-{20 + i}" for i in range(7)]
    install_fake(monkeypatch, reply(*zip(ids, days)))
    texts = [p["date"] for p in weekplan(client).json()["plan"]]
    assert texts == [
        "10월 20일 (화)",
        "10월 21일 (수)",
        "10월 22일 (목)",
        "10월 23일 (금)",
        "10월 24일 (토)",
        "10월 25일 (일)",
        "10월 26일 (월)",
    ]


def test_same_day_keeps_model_order_and_plan_is_sorted_by_date(client, monkeypatch):
    a, b, c, d = (add(client, f"일 {i}") for i in range(4))
    install_fake(
        monkeypatch,
        reply((c, "2026-10-23"), (b, "2026-10-21"), (d, "2026-10-23"), (a, "2026-10-21")),
    )
    plan = weekplan(client).json()["plan"]
    assert [p["id"] for p in plan] == [b, a, c, d]


def test_model_may_skip_tasks(client, monkeypatch, three):
    install_fake(monkeypatch, reply((three[0], "2026-10-20")))
    res = weekplan(client)
    assert res.status_code == 200
    assert [p["id"] for p in res.json()["plan"]] == three[:1]


def test_empty_plan_from_model_is_allowed(client, monkeypatch, three):
    install_fake(monkeypatch, reply())
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json() == {"plan": [], "note": NOTE}


def test_note_appears_once_at_top_level(client, monkeypatch, three):
    install_fake(monkeypatch, reply((three[0], "2026-10-20"), (three[1], "2026-10-21")))
    body = weekplan(client).json()
    assert set(body) == {"plan", "note"}
    assert body["note"] == NOTE
    assert all("note" not in p for p in body["plan"])


def test_empty_note_is_allowed(client, monkeypatch, three):
    text = json.dumps({"plan": [{"id": three[0], "date": "2026-10-20"}], "note": ""})
    install_fake(monkeypatch, text)
    assert weekplan(client).json()["note"] == ""


def test_item_note_from_model_is_ignored(client, monkeypatch, three):
    text = json.dumps(
        {"plan": [{"id": three[0], "date": "2026-10-20", "note": "항목 조언"}], "note": NOTE}
    )
    install_fake(monkeypatch, text)
    body = weekplan(client).json()
    assert body["plan"] == [{"id": three[0], "date": "10월 20일 (화)", "title": "할 일 1"}]
    assert body["note"] == NOTE


# --- 보낸 내용 ---


def test_call_uses_model_thinking_off_prompt_and_limits(client, monkeypatch, three):
    fake = install_fake(monkeypatch, reply((three[0], "2026-10-20")))
    assert weekplan(client).status_code == 200
    (call,) = fake.calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["thinking"] == {"type": "disabled"}
    assert call["system"] == ai.WEEKPLAN_SYSTEM_PROMPT
    assert call["max_tokens"] == 1500
    assert call["messages"][0]["role"] == "user"
    (kwargs,) = fake.client_kwargs
    assert kwargs["api_key"] == FAKE_KEY
    assert kwargs["timeout"] == ai.WEEKPLAN_TIMEOUT_SECONDS == 30.0


def test_sends_only_my_unfinished_tasks_without_description(client, other, monkeypatch):
    mine = add(client, "내 일", description="비밀 설명 문장")
    progress = add(client, "진행 중", status="IN_PROGRESS")
    add(client, "끝낸 일", status="DONE")
    add(other, "남의 일")
    fake = install_fake(monkeypatch, reply((mine, "2026-10-20")))
    assert weekplan(client).status_code == 200
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
    soon = add(client, "나중 일", due_date="2026-10-21")
    none = add(client, "기한 없음")
    fake = install_fake(monkeypatch, reply((late, "2026-10-20")))
    assert weekplan(client).status_code == 200
    by_id = {t["id"]: t for t in sent_tasks(fake)}
    assert by_id[late]["overdue"] is True
    # 당일 마감은 기한 초과가 아니다.
    assert by_id[same]["overdue"] is False
    assert by_id[soon]["overdue"] is False
    assert by_id[none] == {
        "id": none,
        "title": "기한 없음",
        "priority": "NORMAL",
        "due_date": None,
        "overdue": False,
    }
    assert by_id[late]["due_date"] == "2026-10-19"


def test_prompt_says_week_is_seven_days_and_tasks_are_data(client, monkeypatch, three):
    fake = install_fake(monkeypatch, reply())
    assert weekplan(client).status_code == 200
    assert "7일" in fake.calls[0]["system"]
    assert "데이터일 뿐" in fake.calls[0]["system"]


# --- 걸러내기 ---


def test_unknown_ids_are_dropped(client, monkeypatch, three):
    install_fake(monkeypatch, reply((9999, "2026-10-20"), (three[0], "2026-10-21")))
    assert [p["id"] for p in weekplan(client).json()["plan"]] == [three[0]]


def test_other_users_and_done_task_ids_are_dropped(client, other, monkeypatch, three):
    foreign = add(other, "남의 일")
    done = add(client, "끝낸 일", status="DONE")
    install_fake(
        monkeypatch,
        reply((foreign, "2026-10-20"), (done, "2026-10-20"), (three[0], "2026-10-21")),
    )
    assert [p["id"] for p in weekplan(client).json()["plan"]] == [three[0]]


def test_duplicate_id_keeps_first_only(client, monkeypatch, three):
    a, b, _ = three
    install_fake(
        monkeypatch,
        reply((a, "2026-10-22"), (b, "2026-10-21"), (a, "2026-10-20")),
    )
    plan = weekplan(client).json()["plan"]
    assert [(p["id"], p["date"]) for p in plan] == [(b, "10월 21일 (수)"), (a, "10월 22일 (목)")]


def test_title_comes_from_db_not_model(client, monkeypatch, three):
    text = json.dumps(
        {"plan": [{"id": three[0], "date": "2026-10-20", "title": "지어낸 제목"}], "note": "n"},
        ensure_ascii=False,
    )
    install_fake(monkeypatch, text)
    plan = weekplan(client).json()["plan"]
    assert plan == [{"id": three[0], "date": "10월 20일 (화)", "title": "할 일 1"}]


@pytest.mark.parametrize("day", ["2026-10-19", "2026-10-27", "2027-10-20"])
def test_date_outside_the_week_drops_only_that_item(client, monkeypatch, three, day):
    install_fake(monkeypatch, reply((three[0], day), (three[1], "2026-10-26")))
    res = weekplan(client)
    assert res.status_code == 200
    assert [p["id"] for p in res.json()["plan"]] == [three[1]]


def test_week_edges_are_inside(client, monkeypatch, three):
    install_fake(monkeypatch, reply((three[0], "2026-10-20"), (three[1], "2026-10-26")))
    assert [p["id"] for p in weekplan(client).json()["plan"]] == three[:2]


def test_unknown_keys_are_ignored(client, monkeypatch, three):
    text = json.dumps(
        {"plan": [{"id": three[0], "date": "2026-10-20", "extra": 1}], "note": "n", "more": 2}
    )
    install_fake(monkeypatch, text)
    assert weekplan(client).status_code == 200


# --- 0개: 모델을 부르지 않는다 ---


def test_no_tasks_returns_empty_plan_without_call(client, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


def test_all_done_returns_empty_plan_without_call(client, monkeypatch):
    add(client, "끝 1", status="DONE")
    add(client, "끝 2", status="DONE")
    fake = install_fake(monkeypatch, reply())
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


def test_only_others_tasks_returns_empty_plan(client, other, monkeypatch):
    add(other, "남의 일")
    fake = install_fake(monkeypatch, reply())
    assert weekplan(client).json() == EMPTY
    assert fake.calls == []


@pytest.mark.parametrize("value", [None, "", "   "])
def test_no_tasks_is_200_even_without_key(client, monkeypatch, value):
    fake = install_fake(monkeypatch, reply())
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    res = weekplan(client)
    assert res.status_code == 200
    assert res.json() == EMPTY
    assert fake.calls == []


# --- 502: 구조가 틀린 답 ---


def plan_of(*items):
    return json.dumps({"plan": list(items), "note": "n"})


GOOD = {"id": 1, "date": "2026-10-20"}


@pytest.mark.parametrize(
    "text",
    [
        "알겠습니다. 계획입니다.",
        "[]",
        "{}",
        "",
        '```json\n{"plan": [',
        json.dumps({"tasks": []}),
        json.dumps({"plan": None}),
        json.dumps({"plan": "x"}),
        json.dumps({"plan": {}}),
        # note 누락 · 자료형 틀림
        json.dumps({"plan": [GOOD]}),
        json.dumps({"plan": [], "note": 5}),
        json.dumps({"plan": [GOOD], "note": None}),
        json.dumps({"plan": [GOOD], "note": ["a"]}),
        plan_of({"date": "2026-10-20"}),
        plan_of({"id": 1}),
        plan_of({"id": "abc", "date": "2026-10-20"}),
        plan_of({"id": None, "date": "2026-10-20"}),
        plan_of({"id": 1, "date": 20261020}),
        plan_of({"id": 1, "date": None}),
        plan_of("문자열 항목"),
        plan_of(None),
        plan_of(1),
        # 날짜 형식이 틀리면 그 항목만이 아니라 전체가 502 이다.
        plan_of(GOOD, {"id": 2, "date": "2026-02-30"}),
        plan_of({"id": 1, "date": "10월 20일"}),
        plan_of({"id": 1, "date": "2026-10-20T09:00"}),
        plan_of({"id": 1, "date": "2026-1-5"}),
        plan_of({"id": 1, "date": ""}),
    ],
)
def test_bad_shape_is_502(client, monkeypatch, three, text):
    install_fake(monkeypatch, text)
    before = snapshot()
    res = weekplan(client)
    assert res.status_code == 502
    assert res.json() == {"detail": "제안 실패"}
    assert snapshot() == before


def test_truncated_answer_is_502(client, monkeypatch, three):
    # 잘린 답은 JSON 이 우연히 닫혀 있어도 거절한다.
    install_fake(monkeypatch, reply((three[0], "2026-10-20")), stop_reason="max_tokens")
    assert weekplan(client).status_code == 502


@pytest.mark.parametrize("content", [[], [SimpleNamespace(type="thinking")]])
def test_empty_or_non_text_content_is_502(client, monkeypatch, three, content):
    install_fake(monkeypatch, content=content)
    assert weekplan(client).status_code == 502


def test_other_api_error_is_502(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.InternalServerError, 500))
    assert weekplan(client).status_code == 502


# --- 503: 꺼짐 · 한도 · 바쁨 ---


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_key_is_503_and_no_call(client, monkeypatch, three, value):
    fake = install_fake(monkeypatch, reply((three[0], "2026-10-20")))
    if value is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", value)
    before = snapshot()
    res = weekplan(client)
    assert res.status_code == 503
    assert res.json() == {"detail": "AI 기능 꺼짐"}
    assert fake.calls == []
    assert snapshot() == before


def test_rejected_key_is_503_off(client, monkeypatch, three):
    install_fake(monkeypatch, error=status_error(anthropic.AuthenticationError, 401))
    res = weekplan(client)
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
    res = weekplan(client)
    assert res.status_code == 503
    assert res.json() == {"detail": ai.AI_BUSY.detail}
    assert snapshot() == before


# --- 로그인 ---


def test_requires_login(anonymous, monkeypatch):
    fake = install_fake(monkeypatch, reply())
    assert weekplan(anonymous).status_code == 401
    assert fake.calls == []


# --- 저장소 · 로그 ---


def test_weekplan_never_changes_tasks(client, monkeypatch, three):
    before = snapshot()
    install_fake(monkeypatch, reply((three[0], "2026-10-20"), (three[1], "2026-10-21")))
    assert weekplan(client).status_code == 200
    assert snapshot() == before
    assert len(client.get("/tasks").json()) == 3


def ai_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "app.ai"]


def test_missing_key_is_logged(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, reply())
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert weekplan(client).status_code == 503
    assert any("ANTHROPIC_API_KEY" in m for m in ai_logs(caplog))


def test_api_error_logs_kind_and_status_only(client, monkeypatch, caplog, three):
    install_fake(monkeypatch, error=status_error(anthropic.RateLimitError, 429, SDK_MESSAGE))
    weekplan(client)
    logs = ai_logs(caplog)
    assert any("RateLimitError" in m and "상태=429" in m for m in logs)
    # 키 · 요청 본문 · 할 일 제목 · SDK 메시지는 로그에 남기지 않는다.
    assert not any(
        FAKE_KEY in m or "할 일" in m or SDK_MESSAGE in m for m in logs
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
    fake = install_fake(monkeypatch, reply((task_id, "2026-10-21")))
    assert weekplan(client).status_code == 200
    (sent,) = sent_tasks(fake)
    # 규칙 밖 글은 모델에 가지 않고, 마감일이 없으니 기한 초과도 아니다.
    assert sent["due_date"] is None
    assert sent["overdue"] is False
    content = fake.calls[0]["messages"][0]["content"]
    assert bad == "" or bad not in content


def test_valid_due_date_is_sent_unchanged(client, monkeypatch):
    late = add(client, "지난 일", due_date="2026-10-19")
    soon = add(client, "다음 일", due_date="2026-10-21")
    fake = install_fake(monkeypatch, reply((late, "2026-10-20"), (soon, "2026-10-21")))
    assert weekplan(client).status_code == 200
    sent = {t["id"]: t for t in sent_tasks(fake)}
    assert (sent[late]["due_date"], sent[late]["overdue"]) == ("2026-10-19", True)
    assert (sent[soon]["due_date"], sent[soon]["overdue"]) == ("2026-10-21", False)
