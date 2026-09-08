from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.scholarship_ai import (
    AICapacityError,
    run_chat_agent,
    run_discovery_agent,
    run_question_agent,
)
from app.api.scholarships import published_scholarship_query
from app.core.config import get_settings
from app.models import KnowledgeChunk, Scholarship, ScholarshipVersion
from app.presenters import scholarship_card
from app.schemas import (
    ChatExtractedFacts,
    DiscoveryProfile,
    DiscoveryResponse,
    ScholarshipAssessment,
    ScholarshipChatParsed,
    ScholarshipQuestionRequest,
    ScholarshipQuestionResponse,
    SourceExcerpt,
)
from app.services.eligibility_rules import (
    assessment_introduction,
    evaluate_structured_eligibility,
)

settings = get_settings()

_SENSITIVE_MESSAGE_PATTERN = re.compile(
    r"\b(?:aadhaar|aadhar|pan(?:\s+(?:card|number|no))?|bank\s+(?:account|details)|"
    r"account\s+number|ifsc|upi(?:\s+id)?|otp|password|passcode|cvv|"
    r"credit\s+card|debit\s+card)\b",
    re.IGNORECASE,
)
_EXTRACTED_SCALAR_FIELDS = (
    "state",
    "gender",
    "education_level",
    "course",
    "course_year",
    "marks_percentage",
    "family_income_range",
)


def _contains_sensitive_information(message: str | None) -> bool:
    return bool(message and _SENSITIVE_MESSAGE_PATTERN.search(message))


def _only_new_extracted_facts(
    profile: DiscoveryProfile,
    extracted: ChatExtractedFacts,
) -> ChatExtractedFacts:
    values: dict[str, Any] = {}
    for field in _EXTRACTED_SCALAR_FIELDS:
        value = getattr(extracted, field)
        if value is not None and value != getattr(profile, field):
            values[field] = value
    known_categories = set(profile.categories)
    values["categories"] = [
        category for category in extracted.categories if category not in known_categories
    ]
    return ChatExtractedFacts(**values)


def _profile_with_extracted_facts(
    profile: DiscoveryProfile,
    extracted: ChatExtractedFacts,
) -> DiscoveryProfile:
    values = profile.model_dump()
    for field in _EXTRACTED_SCALAR_FIELDS:
        value = getattr(extracted, field)
        if value is not None:
            values[field] = value
    values["categories"] = list(dict.fromkeys([*profile.categories, *extracted.categories]))
    return DiscoveryProfile(**values)


def _privacy_discovery_response() -> DiscoveryResponse:
    return DiscoveryResponse(
        ai_available=bool(settings.openrouter_api_key),
        model=settings.ai_model if settings.openrouter_api_key else None,
        notice="Sensitive identifiers are not sent to the AI service or stored in this chat.",
        candidates=[],
        introduction=(
            "Please do not share Aadhaar, PAN, bank, card, password, or OTP details in chat. "
            "Use the secure document-upload area when an application asks for evidence; "
            "you can safely tell me only your State, course, study year, marks, income range, "
            "and scholarship category."
        ),
        assessments=[],
        mode="CONVERSATION",
        intent="GENERAL_QUESTION",
        requested_details=[],
        suggested_replies=["Help me find scholarships", "What details do you need?"],
        extracted=ChatExtractedFacts(),
    )


# OpenRouter / AI providers count prompt tokens plus max_tokens against the tokens-per-minute ceiling and
# rejects the request with HTTP 413 when the sum exceeds it. These constants keep the
# estimate deliberately pessimistic so a request is trimmed rather than refused.
_CHARS_PER_TOKEN = 3
_PROMPT_OVERHEAD_TOKENS = 400
_SAFETY_MARGIN_TOKENS = 600
# A four-candidate bundle measured at 546 completion tokens per assessment against
# openai/gpt-oss-20b. Allowing 620 leaves headroom for a wordier reply, because a
# completion truncated by max_tokens produces invalid JSON and fails the whole request.
_OUTPUT_TOKENS_PER_CANDIDATE = 620
_INTRODUCTION_TOKENS = 700
_MAX_OUTPUT_TOKENS = 5000


def _estimate_tokens(payload: object) -> int:
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    return len(serialized) // _CHARS_PER_TOKEN + _PROMPT_OVERHEAD_TOKENS


def _plan_discovery_request(
    student_facts: dict[str, Any],
    candidate_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Trim candidates until prompt + output tokens fit the configured AI token budget.

    Returns the candidates to assess and the max_tokens to request. Dropping the tail is
    safe: candidates are ordered by nearest deadline and every one still reaches the
    student through the unfiltered ``candidates`` list.
    """
    candidates = candidate_payload[: settings.ai_discovery_max_candidates]
    while candidates:
        prompt_tokens = _estimate_tokens(
            {"student_facts": student_facts, "candidate_scholarships": candidates}
        )
        available = settings.ai_token_budget - prompt_tokens - _SAFETY_MARGIN_TOKENS
        wanted = min(
            _MAX_OUTPUT_TOKENS,
            _OUTPUT_TOKENS_PER_CANDIDATE * len(candidates) + _INTRODUCTION_TOKENS,
        )
        # Only accept a plan whose full output allowance fits, so the model is never
        # cut off mid-JSON by a max_tokens value the budget could not cover.
        if available >= wanted:
            return candidates, wanted
        candidates = candidates[:-1]
    return [], 0


# Facts that make an eligibility assessment meaningful. Without at least one of these the
# assistant has nothing to compare against provider evidence, so assessing every catalog
# candidate would only produce "cannot determine" noise.
_ELIGIBILITY_FIELDS = (
    "state",
    "gender",
    "education_level",
    "course",
    "course_year",
    "marks_percentage",
    "family_income_range",
)


def _has_eligibility_facts(profile: DiscoveryProfile) -> bool:
    if any(getattr(profile, name) is not None for name in _ELIGIBILITY_FIELDS):
        return True
    return bool(profile.categories)


def _scripted_chat_reply() -> DiscoveryResponse:
    """Deterministic conversational reply used when the AI provider is unavailable."""
    return DiscoveryResponse(
        ai_available=False,
        model=None,
        notice="AI chat is not configured, so this is a standard reply.",
        candidates=[],
        introduction=(
            "Hello, I am ScholarSaathi. Tell me your State or UT, your course, and your "
            "current study year, and I will look for scholarships that fit you."
        ),
        assessments=[],
        mode="CONVERSATION",
        intent="GREETING",
        requested_details=["state", "course", "course_year"],
        suggested_replies=[
            "I study BTech in Odisha",
            "I am in my 2nd year",
            "What details do you need?",
        ],
        extracted=ChatExtractedFacts(),
    )


def _run_chat_preflight(
    db: Session,
    profile: DiscoveryProfile,
) -> ScholarshipChatParsed | None:
    if not settings.openrouter_api_key:
        return None

    titles = db.execute(
        published_scholarship_query().order_by(ScholarshipVersion.application_deadline_at).limit(12)
    ).all()
    catalog_titles = [
        f"{version.title} — {organization.display_name}" for _, version, organization in titles
    ]
    return run_chat_agent(
        {
            "message": profile.message,
            "preferred_language": profile.preferred_language,
            "known_student_facts": profile.model_dump(
                mode="json",
                exclude_none=True,
                exclude={"message", "preferred_language", "history"},
            ),
            # Earlier turns of this session, oldest first, so the model can resolve
            # references such as "those ones" instead of treating each message as new.
            "conversation_history": [
                {"role": turn.role, "text": turn.text} for turn in profile.history
            ],
            "catalog_titles": catalog_titles,
            "catalog_count": len(catalog_titles),
        }
    )


def _conversation_response(
    db: Session,
    profile: DiscoveryProfile,
    parsed: ScholarshipChatParsed | None = None,
    *,
    chat_attempted: bool = False,
) -> DiscoveryResponse:
    """Return a conversational turn without scholarship assessments."""
    if not settings.openrouter_api_key:
        return _scripted_chat_reply()

    if not chat_attempted:
        try:
            parsed = _run_chat_preflight(db, profile)
        except AICapacityError:
            return _scripted_chat_reply()

    if parsed is None:
        return _scripted_chat_reply()

    return DiscoveryResponse(
        ai_available=True,
        model=settings.ai_model,
        notice=(
            "Share a few details and I will compare them against provider-confirmed "
            "scholarship information."
        ),
        candidates=[],
        introduction=parsed.reply,
        assessments=[],
        mode="CONVERSATION",
        intent=parsed.intent,
        requested_details=parsed.requested_details,
        suggested_replies=parsed.suggested_replies,
        extracted=_only_new_extracted_facts(profile, parsed.extracted),
    )


# Structured eligibility is evaluated in-process for every candidate, so this cap only
# bounds response size and evidence loading. The AI slice stays limited separately by
# ai_discovery_max_candidates and the token budget, so raising this adds no model cost.
_MAX_DISCOVERY_CANDIDATES = 60


def _candidate_query(profile: DiscoveryProfile):
    query = published_scholarship_query()
    if profile.state:
        query = query.where(
            or_(
                ScholarshipVersion.applicable_state_codes.any("ALL"),
                ScholarshipVersion.applicable_state_codes.any(profile.state),
            )
        )
    if profile.education_level:
        query = query.where(ScholarshipVersion.education_levels.any(profile.education_level))
    if profile.course:
        course_conditions = [
            ScholarshipVersion.course_families.any(profile.course),
            ScholarshipVersion.course_families.any("ALL_RECOGNIZED_COURSES"),
        ]
        if profile.education_level == "UNDERGRADUATE":
            course_conditions.append(ScholarshipVersion.course_families.any("ALL_UNDERGRADUATE"))
        if profile.course in {"STEM", "BTECH", "BE", "BARCH", "BSC"}:
            course_conditions.append(ScholarshipVersion.course_families.any("STEM"))
        query = query.where(or_(*course_conditions))
    return query.order_by(ScholarshipVersion.application_deadline_at).limit(
        _MAX_DISCOVERY_CANDIDATES
    )


def discover_scholarships(db: Session, profile: DiscoveryProfile) -> DiscoveryResponse:
    # Sensitive identifiers must never be forwarded to the external model. Students use
    # the private document workflow for evidence instead of placing identifiers in chat.
    if _contains_sensitive_information(profile.message):
        return _privacy_discovery_response()

    chat_parsed: ScholarshipChatParsed | None = None
    chat_attempted = False
    effective_profile = profile
    if profile.message and settings.openrouter_api_key:
        chat_attempted = True
        try:
            chat_parsed = _run_chat_preflight(db, profile)
        except AICapacityError:
            chat_parsed = None
        if chat_parsed is not None:
            effective_profile = _profile_with_extracted_facts(profile, chat_parsed.extracted)

    # The model owns intent classification. Deterministic code only decides whether we
    # have enough facts to run the rules engine, and handles the model being unavailable.
    has_facts = _has_eligibility_facts(effective_profile)

    if chat_parsed is None:
        # No model verdict available (no API key or capacity error). Fall back to facts.
        if not has_facts:
            return _conversation_response(
                db,
                profile,
                chat_parsed,
                chat_attempted=chat_attempted,
            )
    else:
        # An apply request is a routing decision for the client, not a search turn.
        if chat_parsed.intent == "APPLY_REQUEST":
            return _conversation_response(
                db,
                profile,
                chat_parsed,
                chat_attempted=chat_attempted,
            )
        # Sharing details is an implicit search once the facts are usable, which is why
        # it is not treated as a conversation-only intent here.
        wants_matches = chat_parsed.intent in {"SCHOLARSHIP_SEARCH", "SHARING_DETAILS"}
        if not wants_matches or not has_facts:
            return _conversation_response(
                db,
                profile,
                chat_parsed,
                chat_attempted=chat_attempted,
            )

    turn_extracted = (
        _only_new_extracted_facts(profile, chat_parsed.extracted)
        if chat_parsed is not None
        else ChatExtractedFacts()
    )
    rows = db.execute(_candidate_query(effective_profile)).all()
    cards = [scholarship_card(*row) for row in rows]

    if not rows:
        return DiscoveryResponse(
            ai_available=bool(settings.openrouter_api_key),
            model=settings.ai_model if settings.openrouter_api_key else None,
            notice="No active published scholarships matched the initial search scope.",
            candidates=[],
            introduction=(
                "I could not find a published scholarship matching those details yet. Try a "
                "wider course or education level, or leave the State blank to see all-India "
                "programmes."
            ),
            assessments=[],
            mode="ASSESSMENT",
            intent="SCHOLARSHIP_SEARCH",
            extracted=turn_extracted,
        )

    version_ids = [version.id for _, version, _ in rows]
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.scholarship_version_id.in_(version_ids),
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .order_by(KnowledgeChunk.scholarship_version_id, KnowledgeChunk.ordinal)
    ).all()
    chunks_by_version: dict[str, list[KnowledgeChunk]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_version[str(chunk.scholarship_version_id)].append(chunk)

    candidate_payload: list[dict[str, Any]] = []
    citations_by_version: dict[str, set[str]] = {}
    evidence_limit = settings.ai_discovery_evidence_char_limit
    for scholarship, version, organization in rows:
        version_key = str(version.id)
        evidence = [
            {
                "citation_id": str(chunk.id),
                "section": chunk.section_title,
                "page": chunk.page_number,
                "text": (chunk.provider_text or "")[:evidence_limit],
            }
            for chunk in chunks_by_version[version_key]
        ]
        citations_by_version[version_key] = {item["citation_id"] for item in evidence}
        candidate_payload.append(
            {
                "scholarship_id": str(scholarship.id),
                "scholarship_version_id": version_key,
                "title": version.title,
                "provider": organization.display_name,
                "provider_type": organization.type.value,
                "deadline": (
                    version.application_deadline_at.isoformat()
                    if version.application_deadline_at
                    else None
                ),
                "benefit": {
                    "summary": version.benefit_summary,
                    "minimum": (
                        float(version.benefit_amount_min)
                        if version.benefit_amount_min is not None
                        else None
                    ),
                    "maximum": (
                        float(version.benefit_amount_max)
                        if version.benefit_amount_max is not None
                        else None
                    ),
                },
                "eligibility_rules": version.eligibility_rules_json,
                "document_requirements": version.document_requirements_json,
                "application_process": version.application_process_json,
                "evidence": evidence,
            }
        )

    student_facts = effective_profile.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"message"},
    )
    structured_by_version: dict[str, ScholarshipAssessment] = {}
    unstructured_candidates: list[dict[str, Any]] = []
    for candidate in candidate_payload:
        assessment = evaluate_structured_eligibility(effective_profile, candidate)
        if assessment is None:
            unstructured_candidates.append(candidate)
        else:
            structured_by_version[assessment.scholarship_version_id] = assessment

    model_by_version: dict[str, ScholarshipAssessment] = {}
    if unstructured_candidates and settings.openrouter_api_key:
        assessed, max_output_tokens = _plan_discovery_request(
            student_facts,
            unstructured_candidates,
        )
        if assessed:
            allowed_citations = {
                candidate["scholarship_version_id"]: citations_by_version[
                    candidate["scholarship_version_id"]
                ]
                for candidate in assessed
            }
            try:
                parsed_assessments = run_discovery_agent(
                    {"student_facts": student_facts, "candidate_scholarships": assessed},
                    allowed_citations,
                    max_output_tokens,
                )
            except AICapacityError:
                parsed_assessments = None
            if parsed_assessments is not None:
                model_by_version = {
                    item.scholarship_version_id: item for item in parsed_assessments.assessments
                }

    assessments = [
        assessment
        for candidate in candidate_payload
        if (
            assessment := structured_by_version.get(candidate["scholarship_version_id"])
            or model_by_version.get(candidate["scholarship_version_id"])
        )
        is not None
    ]
    notice = ""
    if unstructured_candidates:
        notice = (
            f"{len(unstructured_candidates)} scholarship(s) did not publish enough "
            "structured rules for a complete automatic check."
        )

    missing = [name for name in _ELIGIBILITY_FIELDS if getattr(effective_profile, name) is None]
    if not effective_profile.categories:
        missing.append("categories")

    return DiscoveryResponse(
        ai_available=bool(settings.openrouter_api_key),
        model=settings.ai_model if settings.openrouter_api_key else None,
        notice=notice,
        candidates=cards,
        introduction=assessment_introduction(assessments),
        assessments=assessments,
        mode="ASSESSMENT",
        intent="SCHOLARSHIP_SEARCH",
        requested_details=missing[:3],
        suggested_replies=[],
        extracted=turn_extracted,
    )


def answer_scholarship_question(
    db: Session,
    scholarship_id: uuid.UUID,
    request: ScholarshipQuestionRequest,
) -> ScholarshipQuestionResponse:
    if _contains_sensitive_information(request.question):
        return ScholarshipQuestionResponse(
            ai_available=bool(settings.openrouter_api_key),
            model=settings.ai_model if settings.openrouter_api_key else None,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer=(
                "Please do not share Aadhaar, PAN, bank, card, password, or OTP details "
                "in chat. Upload requested evidence only through the secure document area."
            ),
            citations=[],
            suggested_questions=[
                "Which documents are required?",
                "What is the application deadline?",
            ],
        )

    row = db.execute(
        published_scholarship_query().where(Scholarship.id == scholarship_id)
    ).one_or_none()
    if not row:
        raise LookupError("Scholarship was not found")

    _scholarship, version, organization = row
    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.domain == version.domain,
            KnowledgeChunk.organization_id == version.organization_id,
            KnowledgeChunk.scholarship_version_id == version.id,
            KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
        )
        .order_by(KnowledgeChunk.ordinal)
    ).all()
    excerpts = {
        str(chunk.id): SourceExcerpt(
            citation_id=str(chunk.id),
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            text=chunk.provider_text,
        )
        for chunk in chunks
    }

    if not settings.openrouter_api_key:
        return ScholarshipQuestionResponse(
            ai_available=False,
            model=None,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer=(
                "Question answering is temporarily unavailable. Review the scholarship "
                "information below or contact the provider."
            ),
            citations=[],
            suggested_questions=[],
        )

    try:
        parsed = run_question_agent(
            {
                "question": request.question,
                "preferred_language": request.preferred_language,
                "scholarship": {
                    "version_id": str(version.id),
                    "title": version.title,
                    "provider": organization.display_name,
                    "last_confirmed_at": version.last_provider_confirmed_at.isoformat(),
                    "evidence": [excerpt.model_dump() for excerpt in excerpts.values()],
                },
            },
            set(excerpts),
        )
    except AICapacityError:
        return ScholarshipQuestionResponse(
            ai_available=False,
            model=settings.ai_model,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer=(
                "AI answering is at its usage limit for the moment. Please try again in a "
                "minute, or review the provider information on this page."
            ),
            citations=[],
            suggested_questions=[],
        )
    if parsed is None:
        return ScholarshipQuestionResponse(
            ai_available=True,
            model=settings.ai_model,
            label="PROVIDER_CONFIRMATION_REQUIRED",
            answer="I could not confirm an answer from the provider-published information.",
            citations=[],
            suggested_questions=[],
        )

    return ScholarshipQuestionResponse(
        ai_available=True,
        model=settings.ai_model,
        label=parsed.label,
        answer=parsed.answer,
        citations=[excerpts[citation_id] for citation_id in parsed.citation_ids],
        suggested_questions=parsed.suggested_questions,
    )
