from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database import get_db
from app.models import (
    Account,
    AccountRealm,
    AccountStatus,
    AuthSession,
    MemberStatus,
    Organization,
    OrganizationMember,
)
from app.security import CSRF_COOKIE_NAME, csrf_token_for_session, hash_session_token

settings = get_settings()


@dataclass(slots=True)
class AuthContext:
    account: Account
    session: AuthSession
    raw_token: str


@dataclass(slots=True)
class OrganizationContext:
    auth: AuthContext
    organization: Organization
    membership: OrganizationMember


def get_current_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    token_hash = hash_session_token(raw_token)
    row = db.execute(
        select(AuthSession, Account)
        .join(
            Account,
            and_(
                Account.domain == AuthSession.domain,
                Account.id == AuthSession.account_id,
            ),
        )
        .where(AuthSession.token_hash == token_hash)
    ).one_or_none()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid")

    auth_session, account = row
    now = datetime.now(UTC)
    if auth_session.revoked_at or auth_session.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has expired")
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not active")

    return AuthContext(account=account, session=auth_session, raw_token=raw_token)


def require_csrf(
    request: Request,
    auth: AuthContext = Depends(get_current_auth),
) -> AuthContext:
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    expected = csrf_token_for_session(auth.raw_token)
    if not header_token or not cookie_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token is required")
    if not hmac.compare_digest(header_token, cookie_token) or not hmac.compare_digest(
        header_token, expected
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token is invalid")
    return auth


def require_student(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
    if auth.account.realm != AccountRealm.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student account required")
    return auth


def require_student_write(auth: AuthContext = Depends(require_csrf)) -> AuthContext:
    if auth.account.realm != AccountRealm.STUDENT:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student account required")
    return auth


def _organization_context(auth: AuthContext, db: Session) -> OrganizationContext:
    if auth.account.realm != AccountRealm.ORGANIZATION_MEMBER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organization account required")

    row = db.execute(
        select(OrganizationMember, Organization)
        .join(
            Organization,
            and_(
                Organization.domain == OrganizationMember.domain,
                Organization.id == OrganizationMember.organization_id,
            ),
        )
        .where(
            OrganizationMember.domain == auth.account.domain,
            OrganizationMember.account_id == auth.account.id,
            OrganizationMember.status == MemberStatus.ACTIVE,
        )
    ).one_or_none()
    if not row:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "One active organization membership is required",
        )
    membership, organization = row
    return OrganizationContext(
        auth=auth,
        organization=organization,
        membership=membership,
    )


def require_organization(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> OrganizationContext:
    return _organization_context(auth, db)


def require_organization_write(
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> OrganizationContext:
    return _organization_context(auth, db)
