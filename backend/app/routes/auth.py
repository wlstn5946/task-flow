import sqlite3
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response

from app.deps import Conn, CurrentUser
from app.models import Login, Registration, User
from app.security import (
    DUMMY_HASH,
    SESSION_COOKIE,
    SESSION_LIFETIME,
    hash_password,
    new_session_token,
    now_iso,
    session_key,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=User, status_code=201)
def register(body: Registration, conn: Conn) -> User:
    # 가입해도 로그인된 상태가 되지 않는다. 따로 login 한다. (D-016)
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (body.username, hash_password(body.password)),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="이미 쓰는 아이디입니다.") from None
    return User(id=cur.lastrowid, username=body.username)


@router.post("/login", response_model=User)
def login(
    body: Login,
    conn: Conn,
    response: Response,
    old_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (body.username.strip().lower(),),
    ).fetchone()
    # 아이디가 없는 경우와 비밀번호가 틀린 경우를 같은 응답으로 준다.
    ok = verify_password(row["password_hash"] if row else DUMMY_HASH, body.password)
    if row is None or not ok:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 맞지 않습니다.")

    token = new_session_token()
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_iso(),))
        if old_session:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_key(old_session),))
        conn.execute(
            "INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)",
            (session_key(token), row["id"], now_iso(SESSION_LIFETIME)),
        )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
    )
    return User(id=row["id"], username=row["username"])


@router.post("/logout", status_code=204)
def logout(
    _: CurrentUser,
    conn: Conn,
    response: Response,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    with conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_key(session or ""),))
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return user
