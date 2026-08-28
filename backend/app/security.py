import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Account, AuthSession

password_hasher = PasswordHasher()
settings = get_settings()
CSRF_COOKIE_NAME = "scholarsaathi_csrf"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, supplied_password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, supplied_password)
    except (VerificationError, InvalidHashError):
        return False


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def csrf_token_for_session(raw_token: str) -> str:
    secret = settings.app_secret_key.get_secret_value().encode("utf-8")
    return hmac.new(secret, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session(
    db: Session,
    account: Account,
    user_agent: str | None,
) -> tuple[AuthSession, str]:
    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
    auth_session = AuthSession(
        domain=account.domain,
        account_id=account.id,
        token_hash=hash_session_token(raw_token),
        expires_at=expires_at,
        user_agent=(user_agent or "")[:512] or None,
    )
    db.add(auth_session)
    return auth_session, raw_token


def set_auth_cookies(response: Response, raw_token: str) -> None:
    max_age = settings.session_ttl_hours * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token_for_session(raw_token),
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
