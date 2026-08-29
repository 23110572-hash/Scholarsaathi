from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from app.models import (
    AccountRealm,
    ApplicationFieldType,
    ApplicationStatus,
    OrganizationType,
    OwnershipDomain,
    PublicationStatus,
)


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class MessageResponse(APIModel):
    message: str


class LoginRequest(APIModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_login_identifier(cls, value: str) -> str:
        normalized = value.strip().lower()
        local_part, separator, domain = normalized.partition("@")
        if (
            not separator
            or not local_part
            or not domain
            or "." not in domain
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("Enter a valid email address")
        return normalized


class StudentRegisterRequest(LoginRequest):
    email: EmailStr
    password_confirmation: str = Field(min_length=8, max_length=128)
    display_alias: str | None = Field(default=None, max_length=80)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)

    @model_validator(mode="after")
    def validate_password_confirmation(self) -> StudentRegisterRequest:
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match")
        return self


class OrganizationRegisterRequest(LoginRequest):
    email: EmailStr
    legal_name: str = Field(min_length=3, max_length=240)
    display_name: str = Field(min_length=2, max_length=180)
    organization_type: OrganizationType
    jurisdiction_state_code: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_jurisdiction(self) -> OrganizationRegisterRequest:
        if (
            self.organization_type == OrganizationType.STATE_GOVERNMENT
            and not self.jurisdiction_state_code
        ):
            raise ValueError("State Government organizations require a State/UT code")
        if self.organization_type != OrganizationType.STATE_GOVERNMENT:
            self.jurisdiction_state_code = None
        elif self.jurisdiction_state_code:
            self.jurisdiction_state_code = self.jurisdiction_state_code.upper()
        return self


class OrganizationSummary(APIModel):
    id: uuid.UUID
    display_name: str
    organization_type: OrganizationType
    ownership_domain: OwnershipDomain
    jurisdiction_state_code: str | None
    is_synthetic: bool
    member_role: str | None = None


class SessionUserResponse(APIModel):
    id: uuid.UUID
    login_identifier: str
    realm: AccountRealm
    display_alias: str | None = None
    preferred_language: str | None = None
    organization: OrganizationSummary | None = None


class ProviderSourceSection(APIModel):
    section_title: str = Field(min_length=2, max_length=240)
    text: str = Field(min_length=20, max_length=6000)


class ScholarshipDraftCreate(APIModel):
    title: str = Field(min_length=5, max_length=240)
    summary: str = Field(min_length=20, max_length=1200)
    academic_year: str = Field(pattern=r"^20\d{2}-\d{2}$")
    scope: str = Field(min_length=3, max_length=40)
    applicable_state_codes: list[str] = Field(min_length=1, max_length=40)
    education_levels: list[str] = Field(min_length=1, max_length=20)
    course_families: list[str] = Field(min_length=1, max_length=40)
    category_tags: list[str] = Field(default_factory=list, max_length=40)
    benefit_summary: str = Field(min_length=10, max_length=1600)
    benefit_amount_min: float | None = Field(default=None, ge=0)
    benefit_amount_max: float | None = Field(default=None, ge=0)
    application_opens_at: datetime | None = None
    application_deadline_at: datetime | None = None
    official_source_url: HttpUrl
    provider_helpdesk_url: HttpUrl
    source_sections: list[ProviderSourceSection] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> ScholarshipDraftCreate:
        self.applicable_state_codes = [value.upper() for value in self.applicable_state_codes]
        self.education_levels = [value.upper() for value in self.education_levels]
        self.course_families = [value.upper() for value in self.course_families]
        self.category_tags = [value.upper() for value in self.category_tags]
        if (
            self.application_opens_at
            and self.application_deadline_at
            and self.application_deadline_at < self.application_opens_at
        ):
            raise ValueError("Application deadline cannot be before the opening date")
        if (
            self.benefit_amount_min is not None
            and self.benefit_amount_max is not None
            and self.benefit_amount_max < self.benefit_amount_min
        ):
            raise ValueError("Maximum benefit cannot be lower than minimum benefit")
        return self


class ScholarshipCard(APIModel):
    id: uuid.UUID
    version_id: uuid.UUID
    slug: str
    title: str
    summary: str
    academic_year: str
    scope: str
    applicable_state_codes: list[str]
    education_levels: list[str]
    course_families: list[str]
    category_tags: list[str]
    benefit_summary: str
    benefit_amount_min: float | None
    benefit_amount_max: float | None
    application_deadline_at: datetime | None
    official_source_url: str
    last_provider_confirmed_at: datetime
    publication_status: PublicationStatus
    is_synthetic: bool
    organization: OrganizationSummary


class ScholarshipListResponse(APIModel):
    items: list[ScholarshipCard]
    total: int


class SourceExcerpt(APIModel):
    citation_id: str
    section_title: str
    page_number: int | None
    text: str


class ApplicationFieldResponse(APIModel):
    id: uuid.UUID
    field_key: str
    label: str
    help_text: str
    field_type: ApplicationFieldType
    required: bool
    options: list[str] | None
    sort_order: int


class ScholarshipDetailResponse(ScholarshipCard):
    knowledge_summary: str
    provider_helpdesk_url: str
    evidence: list[SourceExcerpt]
    application_template_id: uuid.UUID | None
    application_fields: list[ApplicationFieldResponse]


class DiscoveryProfile(APIModel):
    message: str | None = Field(default=None, max_length=1200)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    education_level: str | None = Field(default=None, max_length=60)
    course: str | None = Field(default=None, max_length=80)
    course_year: int | None = Field(default=None, ge=1, le=12)
    marks_percentage: float | None = Field(default=None, ge=0, le=100)
    family_income_range: str | None = Field(default=None, max_length=80)
    categories: list[str] = Field(default_factory=list, max_length=20)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)

    @model_validator(mode="after")
    def normalize(self) -> DiscoveryProfile:
        if self.state:
            self.state = self.state.upper()
        if self.education_level:
            self.education_level = self.education_level.upper()
        if self.course:
            self.course = self.course.upper()
        self.categories = [value.upper() for value in self.categories]
        return self


class AIClaim(APIModel):
    statement: str
    citation_ids: list[str]


AssessmentLabel = Literal[
    "LIKELY_ELIGIBLE",
    "POSSIBLY_ELIGIBLE_NEEDS_INFORMATION",
    "LIKELY_NOT_ELIGIBLE",
    "CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION",
]


class ScholarshipAssessment(APIModel):
    scholarship_version_id: str
    assessment: AssessmentLabel
    confidence: float = Field(ge=0, le=1)
    summary: str
    matching_points: list[AIClaim]
    possible_conflicts: list[AIClaim]
    missing_information: list[str]
    next_steps: list[str]
    warning: str


class DiscoveryAssessmentBundle(APIModel):
    introduction: str
    assessments: list[ScholarshipAssessment]


class DiscoveryResponse(APIModel):
    ai_available: bool
    model: str | None
    notice: str
    candidates: list[ScholarshipCard]
    introduction: str | None = None
    assessments: list[ScholarshipAssessment] = Field(default_factory=list)


class SavedScholarshipResponse(APIModel):
    scholarship_id: uuid.UUID
    saved: bool


class StateOption(APIModel):
    code: str
    name: str
    is_union_territory: bool


# A downscaled square avatar encodes well under this ceiling. The limit is on the encoded
# data URL because that is what is transported and stored.
MAX_PHOTO_DATA_URL_LENGTH = 300_000
_PHOTO_DATA_URL_PATTERN = r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$"


class StudentProfileUpdate(APIModel):
    full_name: str | None = Field(default=None, max_length=120)
    display_alias: str | None = Field(default=None, max_length=80)
    state_code: str | None = Field(default=None, min_length=2, max_length=2)
    education_level: str | None = Field(default=None, max_length=60)
    course: str | None = Field(default=None, max_length=80)
    course_year: int | None = Field(default=None, ge=1, le=12)
    marks_percentage: float | None = Field(default=None, ge=0, le=100)
    family_income_range: str | None = Field(default=None, max_length=80)
    categories: list[str] = Field(default_factory=list, max_length=20)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)
    photo_data_url: str | None = Field(default=None, max_length=MAX_PHOTO_DATA_URL_LENGTH)

    @field_validator(
        "full_name",
        "display_alias",
        "education_level",
        "course",
        "family_income_range",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("photo_data_url")
    @classmethod
    def validate_photo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(_PHOTO_DATA_URL_PATTERN, value):
            raise ValueError("Profile photo must be a PNG, JPEG, or WebP image")
        return value

    @model_validator(mode="after")
    def normalize(self) -> StudentProfileUpdate:
        if self.full_name:
            self.full_name = self.full_name.strip()
        if self.display_alias:
            self.display_alias = self.display_alias.strip()
        if self.state_code:
            self.state_code = self.state_code.upper()
        if self.education_level:
            self.education_level = self.education_level.upper()
        if self.course:
            self.course = self.course.upper()
        # De-duplicate while preserving order so the stored list matches what was entered.
        self.categories = list(
            dict.fromkeys(
                value.strip().upper() for value in self.categories if value and value.strip()
            )
        )
        return self


class StudentProfileResponse(APIModel):
    full_name: str | None
    display_alias: str | None
    state_code: str | None
    education_level: str | None
    course: str | None
    course_year: int | None
    marks_percentage: float | None
    family_income_range: str | None
    categories: list[str]
    preferred_language: str
    photo_data_url: str | None
    completeness: int = Field(ge=0, le=100)
    updated_at: datetime | None = None


class ApplicationCreateRequest(APIModel):
    consent_to_store_application: bool


class ApplicationCreateResponse(APIModel):
    id: uuid.UUID
    status: ApplicationStatus
    scholarship_version_id: uuid.UUID
    application_template_id: uuid.UUID
    is_synthetic: bool


class ApplicationAnswersUpdate(APIModel):
    answers: dict[uuid.UUID, Any] = Field(min_length=1, max_length=60)


class ApplicationEventResponse(APIModel):
    event_type: str
    safe_message: str
    created_at: datetime


class ApplicationDetailResponse(APIModel):
    id: uuid.UUID
    status: ApplicationStatus
    scholarship_id: uuid.UUID
    scholarship_title: str
    organization_name: str
    is_synthetic: bool
    consent_recorded_at: datetime | None
    submitted_at: datetime | None
    fields: list[ApplicationFieldResponse]
    answered_field_ids: list[uuid.UUID]
    events: list[ApplicationEventResponse]


class ApplicationListItem(APIModel):
    id: uuid.UUID
    status: ApplicationStatus
    scholarship_title: str
    organization_name: str
    is_synthetic: bool
    updated_at: datetime


class ApplicationStatusUpdate(APIModel):
    status: Literal[
        "UNDER_ORGANIZATION_REVIEW",
        "CORRECTION_REQUESTED",
        "APPROVED",
        "REJECTED",
    ]
    message: str = Field(min_length=5, max_length=1000)


class ScholarshipQuestionRequest(APIModel):
    question: str = Field(min_length=3, max_length=1200)
    preferred_language: str = Field(default="en", min_length=2, max_length=10)


class ScholarshipQuestionParsed(APIModel):
    label: Literal[
        "SUPPORTED_BY_PROVIDER_SOURCE",
        "MORE_INFORMATION_NEEDED",
        "PROVIDER_CONFIRMATION_REQUIRED",
    ]
    answer: str
    citation_ids: list[str]
    suggested_questions: list[str] = Field(default_factory=list)


class ScholarshipQuestionResponse(APIModel):
    ai_available: bool
    model: str | None
    label: Literal[
        "SUPPORTED_BY_PROVIDER_SOURCE",
        "MORE_INFORMATION_NEEDED",
        "PROVIDER_CONFIRMATION_REQUIRED",
    ]
    answer: str
    citations: list[SourceExcerpt]
    suggested_questions: list[str]
