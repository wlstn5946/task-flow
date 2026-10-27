import sqlite3
from datetime import date
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from app.db import get_conn
from app.models import User
from app.security import SESSION_COOKIE, now_iso, session_key

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def current_user(
    conn: Conn,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User:
    """로그인한 사용자를 돌려준다. 로그인 안 됨 · 만료는 401. (D-020)"""
    unauthorized = HTTPException(status_code=401, detail="로그인이 필요합니다.")
    if not session:
        raise unauthorized
    row = conn.execute(
        "SELECT users.id, users.username, sessions.expires_at FROM sessions"
        " JOIN users ON users.id = sessions.user_id WHERE sessions.id = ?",
        (session_key(session),),
    ).fetchone()
    if row is None or row["expires_at"] <= now_iso():
        raise unauthorized
    return User(id=row["id"], username=row["username"])


CurrentUser = Annotated[User, Depends(current_user)]


def get_today() -> date:
    """기한 초과를 판단하는 '오늘'. 서버 PC 의 로컬 날짜이다. 테스트에서는 바꿔 끼운다."""
    return date.today()


Today = Annotated[date, Depends(get_today)]
