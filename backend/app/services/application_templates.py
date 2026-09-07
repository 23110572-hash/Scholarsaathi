from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    ApplicationFieldType,
    ApplicationTemplate,
    ApplicationTemplateField,
    OwnershipDomain,
    StudentDocumentType,
)

PROFILE_BINDINGS_BY_FIELD_KEY: dict[str, str] = {
    "course": "course",
    "course_year": "course_year",
    "domicile_state": "state_code",
    "family_income_band": "family_income_range",
    "academic_score": "marks_percentage",
    "student_declaration": "explicit_apply_authorization",
}

DEFAULT_REQUIRED_DOCUMENT_TYPES = [
    StudentDocumentType.INCOME_CERTIFICATE.value,
    StudentDocumentType.CURRENT_MARKSHEET.value,
]


@dataclass(frozen=True, slots=True)
class DefaultFieldDefinition:
    key: str
    label: str
    help_text: str
    field_type: ApplicationFieldType
    profile_binding: str
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_step: float | None = None


DEFAULT_FIELD_DEFINITIONS = (
    DefaultFieldDefinition(
        key="course",
        label="Current course",
        help_text="Course in which the student is currently enrolled.",
        field_type=ApplicationFieldType.SELECT,
        profile_binding="course",
    ),
    DefaultFieldDefinition(
        key="course_year",
        label="Current course year",
        help_text="Current year of study.",
        field_type=ApplicationFieldType.NUMBER,
        profile_binding="course_year",
        numeric_min=1,
        numeric_max=12,
        numeric_step=1,
    ),
    DefaultFieldDefinition(
        key="domicile_state",
        label="Domicile State or Union Territory",
        help_text="State or Union Territory recorded in the student profile.",
        field_type=ApplicationFieldType.SELECT,
        profile_binding="state_code",
    ),
    DefaultFieldDefinition(
        key="family_income_band",
        label="Annual household-income range",
        help_text="Household-income range from the reusable student profile.",
        field_type=ApplicationFieldType.SELECT,
        profile_binding="family_income_range",
    ),
    DefaultFieldDefinition(
        key="academic_score",
        label="Most recent academic percentage",
        help_text="Current marks percentage from the reusable student profile.",
        field_type=ApplicationFieldType.NUMBER,
        profile_binding="marks_percentage",
        numeric_min=0,
        numeric_max=100,
        numeric_step=0.01,
    ),
    DefaultFieldDefinition(
        key="student_declaration",
        label="Application declaration",
        help_text="Recorded as true when the student explicitly asks ScholarSaathi to apply.",
        field_type=ApplicationFieldType.CHECKBOX,
        profile_binding="explicit_apply_authorization",
    ),
)


def _normalized_options(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    normalized = list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))
    return normalized or None


def create_default_application_template(
    db: Session,
    *,
    domain: OwnershipDomain,
    organization_id: uuid.UUID,
    scholarship_version_id: uuid.UUID,
    created_by: uuid.UUID,
    confirmed_at: datetime,
    source_chunk_id: uuid.UUID | None,
    course_options: list[str] | None,
    state_options: list[str] | None,
) -> ApplicationTemplate:
    """Create the owner-confirmed canonical v1 template for a new scholarship version."""
    template = ApplicationTemplate(
        domain=domain,
        organization_id=organization_id,
        scholarship_version_id=scholarship_version_id,
        template_version=1,
        status="OWNER_CONFIRMED",
        required_document_types=list(DEFAULT_REQUIRED_DOCUMENT_TYPES),
        created_by=created_by,
        confirmed_by=created_by,
        confirmed_at=confirmed_at,
    )
    db.add(template)
    db.flush()

    option_sets = {
        "course": _normalized_options(course_options),
        "domicile_state": _normalized_options(state_options),
        "family_income_band": [
            "UP_TO_250000",
            "250001_TO_400000",
            "400001_TO_600000",
            "600001_TO_800000",
            "ABOVE_800000",
        ],
    }
    for sort_order, definition in enumerate(DEFAULT_FIELD_DEFINITIONS, start=1):
        db.add(
            ApplicationTemplateField(
                domain=domain,
                organization_id=organization_id,
                scholarship_version_id=scholarship_version_id,
                application_template_id=template.id,
                field_key=definition.key,
                label=definition.label,
                help_text=definition.help_text,
                field_type=definition.field_type,
                required=True,
                options_json=option_sets.get(definition.key),
                profile_binding=definition.profile_binding,
                numeric_min=definition.numeric_min,
                numeric_max=definition.numeric_max,
                numeric_step=definition.numeric_step,
                source_chunk_id=source_chunk_id,
                sort_order=sort_order,
            )
        )
    return template
