import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from dotenv import load_dotenv

from app.db import BACKEND_DIR

load_dotenv(BACKEND_DIR / ".env")

SESSION_COOKIE = "session"
SESSION_LIFETIME = timedelta(hours=1)  # 로그인한 때부터 1시간. (D-017, Q-21 은 이 해석으로 둔다)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# 없는 아이디로 로그인해도 해시 비교 시간이 같도록 쓰는 값이다.
DUMMY_HASH = hash_password("dummy-password-for-timing")


def now_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(UTC) + delta).isoformat(timespec="milliseconds")


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def session_key(token: str) -> str:
    """쿠키의 값은 그대로 저장하지 않는다. 비밀값으로 서명한 해시를 sessions 표의 키로 쓴다."""
    secret = os.environ.get("SESSION_SECRET", "")
    if not secret:
        raise RuntimeError("SESSION_SECRET 이 없다. backend/.env 에 값을 넣는다.")
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
