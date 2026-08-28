from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, get_current_auth, require_csrf
from app.models import (
    Account,
    AccountRealm,
    AccountStatus,
    MemberRole,
    MemberStatus,
    Organization,
    OrganizationMember,
    OwnershipDomain,
    State,
    StudentSetting,
    ownership_domain_for_type,
)
from app.presenters import organization_summary
from app.schemas import (
    LoginRequest,
    MessageResponse,
    OrganizationRegisterRequest,
    SessionUserResponse,
    StudentRegisterRequest,
)
from app.security import (
    clear_auth_cookies,
    create_session,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.utils import slugify

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _unique_organization_slug(
    db: Session,
    domain: OwnershipDomain,
    display_name: str,
) -> str:
    base = slugify(display_name)
    candidate = base
    suffix = 1
    while db.scalar(
        select(Organization.id).where(
            Organization.domain == domain,
            Organization.slug == candidate,
        )
    ):
        suffix += 1
        candidate = f"{base[:110]}-{suffix}"
    return candidate


def _session_user(db: Session, account: Account) -> SessionUserResponse:
    if account.realm == AccountRealm.STUDENT:
        setting = db.get(StudentSetting, account.id)
        return SessionUserResponse(
            id=account.id,
            login_identifier=account.login_identifier,
            realm=account.realm,
            display_alias=setting.display_alias if setting else None,
            preferred_language=setting.preferred_language if setting else "en",
        )

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
            OrganizationMember.domain == account.domain,
            OrganizationMember.account_id == account.id,
            OrganizationMember.status == MemberStatus.ACTIVE,
        )
    ).one_or_none()
    organization = organization_summary(row[1], row[0]) if row else None
    return SessionUserResponse(
        id=account.id,
        login_identifier=account.login_identifier,
        realm=account.realm,
        organization=organization,
    )


def _login(
    payload: LoginRequest,
    expected_realm: AccountRealm,
    request: Request,
    response: Response,
    db: Session,
) -> SessionUserResponse:
    email = str(payload.email).lower()
    query = select(Account).where(
        Account.login_identifier == email,
        Account.realm == expected_realm,
    )
    if expected_realm == AccountRealm.STUDENT:
        query = query.where(Account.domain == OwnershipDomain.STUDENT)
    else:
        query = query.where(Account.domain != OwnershipDomain.STUDENT)

    accounts = db.scalars(query).all()
    account = accounts[0] if len(accounts) == 1 else None
    if (
        not account
        or account.status != AccountStatus.ACTIVE
        or not verify_password(account.password_hash, payload.password)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")

    account.last_login_at = datetime.now(UTC)
    _, raw_token = create_session(db, account, request.headers.get("user-agent"))
    db.commit()
    set_auth_cookies(response, raw_token)
    return _session_user(db, account)


@router.post(
    "/student/register",
    response_model=SessionUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_student(
    payload: StudentRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionUserResponse:
    email = str(payload.email).lower()
    if db.scalar(select(Account.id).where(Account.login_identifier == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already uses this email")

    account = Account(
        domain=OwnershipDomain.STUDENT,
        login_identifier=email,
        password_hash=hash_password(payload.password),
        realm=AccountRealm.STUDENT,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    db.flush()
    db.add(
        StudentSetting(
            account_id=account.id,
            account_domain=OwnershipDomain.STUDENT,
            display_alias=payload.display_alias,
            preferred_language=payload.preferred_language,
        )
    )
    _, raw_token = create_session(db, account, request.headers.get("user-agent"))
    db.commit()
    set_auth_cookies(response, raw_token)
    return _session_user(db, account)


@router.post(
    "/organization/register",
    response_model=SessionUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_organization(
    payload: OrganizationRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionUserResponse:
    email = str(payload.email).lower()
    if db.scalar(select(Account.id).where(Account.login_identifier == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already uses this email")

    domain = ownership_domain_for_type(payload.organization_type)
    if (
        domain == OwnershipDomain.STATE_GOVERNMENT
        and not db.get(State, payload.jurisdiction_state_code)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "State or Union Territory code is invalid")

    account = Account(
        domain=domain,
        login_identifier=email,
        password_hash=hash_password(payload.password),
        realm=AccountRealm.ORGANIZATION_MEMBER,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    db.flush()

    organization = Organization(
        domain=domain,
        slug=_unique_organization_slug(db, domain, payload.display_name),
        legal_name=payload.legal_name,
        display_name=payload.display_name,
        type=payload.organization_type,
        jurisdiction_state_code=payload.jurisdiction_state_code,
        is_synthetic=False,
    )
    db.add(organization)
    db.flush()
    db.add(
        OrganizationMember(
            domain=domain,
            organization_id=organization.id,
            account_id=account.id,
            role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
        )
    )
    _, raw_token = create_session(db, account, request.headers.get("user-agent"))
    db.commit()
    set_auth_cookies(response, raw_token)
    return _session_user(db, account)


@router.post("/student/login", response_model=SessionUserResponse)
def student_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionUserResponse:
    return _login(payload, AccountRealm.STUDENT, request, response, db)


@router.post("/organization/login", response_model=SessionUserResponse)
def organization_login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionUserResponse:
    return _login(payload, AccountRealm.ORGANIZATION_MEMBER, request, response, db)


@router.get("/me", response_model=SessionUserResponse)
def current_user(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> SessionUserResponse:
    return _session_user(db, auth.account)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    auth: AuthContext = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> MessageResponse:
    auth.session.revoked_at = datetime.now(UTC)
    db.commit()
    clear_auth_cookies(response)
    return MessageResponse(message="Signed out")
