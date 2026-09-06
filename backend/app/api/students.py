from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuthContext, require_student, require_student_write
from app.models import OwnershipDomain, State, StudentSetting
from app.schemas import (
    StateOption,
    StudentProfileResponse,
    StudentProfileUpdate,
)
from app.services.application_workflow import resume_pending_intents_for_student

router = APIRouter(prefix="/api", tags=["student profile"])

# Fields that make a profile useful to the discovery assistant. Completeness is reported
# so the dashboard can nudge a student toward the details that actually improve matching.
_PROFILE_FIELDS = (
    "full_name",
    "date_of_birth",
    "gender",
    "state_code",
    "district",
    "institution_name",
    "board_or_university",
    "education_level",
    "course",
    "specialization",
    "course_year",
    "current_semester",
    "marks_percentage",
    "class_10_percentage",
    "class_10_passing_year",
    "class_12_percentage",
    "class_12_passing_year",
    "family_income_range",
    "photo_data_url",
)


def _completeness(setting: StudentSetting) -> int:
    filled = sum(1 for name in _PROFILE_FIELDS if getattr(setting, name, None) is not None)
    if setting.categories:
        filled += 1
    return round(filled * 100 / (len(_PROFILE_FIELDS) + 1))


def _profile_response(setting: StudentSetting) -> StudentProfileResponse:
    return StudentProfileResponse(
        full_name=setting.full_name,
        display_alias=setting.display_alias,
        date_of_birth=setting.date_of_birth,
        gender=setting.gender,
        state_code=setting.state_code,
        district=setting.district,
        institution_name=setting.institution_name,
        board_or_university=setting.board_or_university,
        education_level=setting.education_level,
        course=setting.course,
        specialization=setting.specialization,
        course_year=setting.course_year,
        current_semester=setting.current_semester,
        marks_percentage=(
            float(setting.marks_percentage) if setting.marks_percentage is not None else None
        ),
        class_10_percentage=(
            float(setting.class_10_percentage)
            if setting.class_10_percentage is not None
            else None
        ),
        class_10_passing_year=setting.class_10_passing_year,
        class_12_percentage=(
            float(setting.class_12_percentage)
            if setting.class_12_percentage is not None
            else None
        ),
        class_12_passing_year=setting.class_12_passing_year,
        family_income_range=setting.family_income_range,
        categories=list(setting.categories or []),
        preferred_language=setting.preferred_language or "en",
        photo_data_url=setting.photo_data_url,
        completeness=_completeness(setting),
        updated_at=setting.updated_at,
    )


def _get_or_create_setting(db: Session, account_id) -> StudentSetting:
    setting = db.get(StudentSetting, account_id)
    if setting is None:
        # Accounts created before student_settings existed, or any row lost to a cascade,
        # should still be able to build a profile instead of returning 404.
        setting = StudentSetting(
            account_id=account_id,
            account_domain=OwnershipDomain.STUDENT,
            preferred_language="en",
            categories=[],
        )
        db.add(setting)
        db.flush()
    return setting


@router.get("/states", response_model=list[StateOption])
def list_states(db: Session = Depends(get_db)) -> list[StateOption]:
    rows = db.scalars(select(State).where(State.is_active).order_by(State.name)).all()
    return [
        StateOption(
            code=row.code,
            name=row.name,
            is_union_territory=row.is_union_territory,
        )
        for row in rows
    ]


@router.get("/student/profile", response_model=StudentProfileResponse)
def get_student_profile(
    auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> StudentProfileResponse:
    setting = _get_or_create_setting(db, auth.account.id)
    db.commit()
    return _profile_response(setting)


@router.put("/student/profile", response_model=StudentProfileResponse)
def update_student_profile(
    payload: StudentProfileUpdate,
    auth: AuthContext = Depends(require_student_write),
    db: Session = Depends(get_db),
) -> StudentProfileResponse:
    if payload.state_code and not db.get(State, payload.state_code):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "State or Union Territory code is invalid",
        )

    setting = _get_or_create_setting(db, auth.account.id)
    setting.full_name = payload.full_name
    setting.display_alias = payload.display_alias
    setting.date_of_birth = payload.date_of_birth
    setting.gender = payload.gender
    setting.state_code = payload.state_code
    setting.district = payload.district
    setting.institution_name = payload.institution_name
    setting.board_or_university = payload.board_or_university
    setting.education_level = payload.education_level
    setting.course = payload.course
    setting.specialization = payload.specialization
    setting.course_year = payload.course_year
    setting.current_semester = payload.current_semester
    setting.marks_percentage = payload.marks_percentage
    setting.class_10_percentage = payload.class_10_percentage
    setting.class_10_passing_year = payload.class_10_passing_year
    setting.class_12_percentage = payload.class_12_percentage
    setting.class_12_passing_year = payload.class_12_passing_year
    setting.family_income_range = payload.family_income_range
    setting.categories = payload.categories
    setting.preferred_language = payload.preferred_language
    setting.photo_data_url = payload.photo_data_url
    db.commit()
    db.refresh(setting)
    response = _profile_response(setting)
    resume_pending_intents_for_student(db, auth.account.id)
    return response
