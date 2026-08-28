from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

from app.core.config import get_settings
from app.schemas import (
    DiscoveryAssessmentBundle,
    ScholarshipAssessment,
    ScholarshipQuestionParsed,
)

settings = get_settings()

DISCOVERY_INSTRUCTIONS = """
You are ScholarSaathi, an evidence-grounded scholarship discovery assistant.
You receive temporary, non-identifying student facts and candidate scholarships from the
ScholarSaathi database. Assess every candidate independently using only the supplied,
provider-confirmed evidence. Never use model memory, invent a condition, or mix evidence between
scholarships. Every matching point and possible conflict must cite one or more exact citation IDs
belonging to that scholarship version. If evidence is incomplete or contradictory, use
CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION. LIKELY_ELIGIBLE is advisory guidance, never an
official decision. The scholarship provider always makes the final decision. Return concise,
supportive language in the student's preferred language when possible.
""".strip()

QUESTION_INSTRUCTIONS = """
Answer only from the supplied provider-confirmed evidence for this scholarship version. Do not use
model memory or infer an unstated rule. Use exact citation IDs from the supplied evidence. If the
evidence is missing or ambiguous, use PROVIDER_CONFIRMATION_REQUIRED. Never claim an official
eligibility or selection decision. Answer in the requested language when possible.
""".strip()


class AIWorkflowError(RuntimeError):
    """Raised when a LangGraph AI workflow cannot produce a safe typed result."""


class DiscoveryAgentState(TypedDict, total=False):
    payload: dict[str, Any]
    allowed_citations: dict[str, set[str]]
    parsed: DiscoveryAssessmentBundle
    result: DiscoveryAssessmentBundle


class QuestionAgentState(TypedDict, total=False):
    payload: dict[str, Any]
    allowed_citations: set[str]
    parsed: ScholarshipQuestionParsed
    result: ScholarshipQuestionParsed


def _chat_model(max_tokens: int) -> ChatGroq:
    if not settings.groq_api_key:
        raise AIWorkflowError("GROQ_API_KEY is not configured")
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key.get_secret_value(),
        temperature=0,
        max_tokens=max_tokens,
        timeout=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
    )


def _generate_discovery(state: DiscoveryAgentState) -> dict[str, DiscoveryAssessmentBundle]:
    structured_model = _chat_model(5000).with_structured_output(
        DiscoveryAssessmentBundle,
        method="json_schema",
        strict=True,
    )
    parsed = structured_model.invoke(
        [
            SystemMessage(content=DISCOVERY_INSTRUCTIONS),
            HumanMessage(content=json.dumps(state["payload"], ensure_ascii=False)),
        ]
    )
    if not isinstance(parsed, DiscoveryAssessmentBundle):
        raise AIWorkflowError("Discovery agent returned an unexpected response type")
    return {"parsed": parsed}


def _cannot_determine(version_id: str, reason: str) -> ScholarshipAssessment:
    return ScholarshipAssessment(
        scholarship_version_id=version_id,
        assessment="CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION",
        confidence=0,
        summary=reason,
        matching_points=[],
        possible_conflicts=[],
        missing_information=["Provider source confirmation is required."],
        next_steps=["Open the provider source or contact the provider helpdesk."],
        warning="The scholarship provider makes the final decision.",
    )


def _validate_discovery(state: DiscoveryAgentState) -> dict[str, DiscoveryAssessmentBundle]:
    parsed = state.get("parsed")
    if parsed is None:
        raise AIWorkflowError("Discovery agent returned no structured assessment")

    allowed_citations = state["allowed_citations"]
    parsed_by_version: dict[str, ScholarshipAssessment] = {}
    for assessment in parsed.assessments:
        version_id = assessment.scholarship_version_id
        if version_id in allowed_citations and version_id not in parsed_by_version:
            parsed_by_version[version_id] = assessment

    validated: list[ScholarshipAssessment] = []
    for version_id, citation_ids in allowed_citations.items():
        assessment = parsed_by_version.get(version_id)
        if assessment is None:
            validated.append(
                _cannot_determine(
                    version_id,
                    "The AI response did not include a source-confirmed assessment.",
                )
            )
            continue

        claims = [*assessment.matching_points, *assessment.possible_conflicts]
        claims_have_evidence = all(
            claim.citation_ids
            and all(citation_id in citation_ids for citation_id in claim.citation_ids)
            for claim in claims
        )
        conclusion_has_evidence = bool(claims) or (
            assessment.assessment == "CANNOT_DETERMINE_FROM_PUBLISHED_INFORMATION"
        )
        if claims_have_evidence and conclusion_has_evidence:
            validated.append(assessment)
        else:
            validated.append(
                _cannot_determine(
                    version_id,
                    "The assessment could not be confirmed against provider source evidence.",
                )
            )

    return {
        "result": DiscoveryAssessmentBundle(
            introduction=parsed.introduction,
            assessments=validated,
        )
    }


def _generate_question(state: QuestionAgentState) -> dict[str, ScholarshipQuestionParsed]:
    structured_model = _chat_model(1800).with_structured_output(
        ScholarshipQuestionParsed,
        method="json_schema",
        strict=True,
    )
    parsed = structured_model.invoke(
        [
            SystemMessage(content=QUESTION_INSTRUCTIONS),
            HumanMessage(content=json.dumps(state["payload"], ensure_ascii=False)),
        ]
    )
    if not isinstance(parsed, ScholarshipQuestionParsed):
        raise AIWorkflowError("Question agent returned an unexpected response type")
    return {"parsed": parsed}


def _question_fallback(
    answer: str,
    suggested_questions: list[str] | None = None,
) -> ScholarshipQuestionParsed:
    return ScholarshipQuestionParsed(
        label="PROVIDER_CONFIRMATION_REQUIRED",
        answer=answer,
        citation_ids=[],
        suggested_questions=suggested_questions or [],
    )


def _validate_question(state: QuestionAgentState) -> dict[str, ScholarshipQuestionParsed]:
    parsed = state.get("parsed")
    if parsed is None:
        raise AIWorkflowError("Question agent returned no structured answer")

    citation_ids = list(dict.fromkeys(parsed.citation_ids))
    if any(citation_id not in state["allowed_citations"] for citation_id in citation_ids):
        result = _question_fallback(
            "I could not confirm the generated answer against the provider source.",
            parsed.suggested_questions,
        )
    elif parsed.label == "SUPPORTED_BY_PROVIDER_SOURCE" and not citation_ids:
        result = _question_fallback(
            "The provider source did not contain enough evidence for an answer.",
            parsed.suggested_questions,
        )
    else:
        result = parsed.model_copy(update={"citation_ids": citation_ids})
    return {"result": result}


@lru_cache
def _discovery_graph():
    graph = StateGraph(DiscoveryAgentState)
    graph.add_node("generate_assessments", _generate_discovery)
    graph.add_node("validate_provider_evidence", _validate_discovery)
    graph.add_edge(START, "generate_assessments")
    graph.add_edge("generate_assessments", "validate_provider_evidence")
    graph.add_edge("validate_provider_evidence", END)
    return graph.compile()


@lru_cache
def _question_graph():
    graph = StateGraph(QuestionAgentState)
    graph.add_node("generate_answer", _generate_question)
    graph.add_node("validate_provider_evidence", _validate_question)
    graph.add_edge(START, "generate_answer")
    graph.add_edge("generate_answer", "validate_provider_evidence")
    graph.add_edge("validate_provider_evidence", END)
    return graph.compile()


def run_discovery_agent(
    payload: dict[str, Any],
    allowed_citations: dict[str, set[str]],
) -> DiscoveryAssessmentBundle | None:
    if not settings.groq_api_key:
        return None
    try:
        final_state = _discovery_graph().invoke(
            {"payload": payload, "allowed_citations": allowed_citations}
        )
    except AIWorkflowError:
        raise
    except Exception as exc:
        raise AIWorkflowError("The discovery agent workflow failed") from exc

    result = final_state.get("result")
    if not isinstance(result, DiscoveryAssessmentBundle):
        raise AIWorkflowError("The discovery agent produced no validated result")
    return result


def run_question_agent(
    payload: dict[str, Any],
    allowed_citations: set[str],
) -> ScholarshipQuestionParsed | None:
    if not settings.groq_api_key:
        return None
    try:
        final_state = _question_graph().invoke(
            {"payload": payload, "allowed_citations": allowed_citations}
        )
    except AIWorkflowError:
        raise
    except Exception as exc:
        raise AIWorkflowError("The scholarship question workflow failed") from exc

    result = final_state.get("result")
    if not isinstance(result, ScholarshipQuestionParsed):
        raise AIWorkflowError("The question agent produced no validated result")
    return result
