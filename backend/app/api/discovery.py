import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.scholarship_ai import AIWorkflowError
from app.database import get_db
from app.dependencies import AuthContext, require_student
from app.rate_limit import require_public_ai_capacity
from app.schemas import (
    DiscoveryProfile,
    DiscoveryResponse,
    ScholarshipQuestionRequest,
    ScholarshipQuestionResponse,
)
from app.services.ai_discovery import answer_scholarship_question, discover_scholarships

router = APIRouter(prefix="/api/ai", tags=["AI discovery"])


@router.post("/discover", response_model=DiscoveryResponse)
def discover(
    profile: DiscoveryProfile,
    _auth: AuthContext = Depends(require_student),
    db: Session = Depends(get_db),
) -> DiscoveryResponse:
    try:
        return discover_scholarships(db, profile)
    except AIWorkflowError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI service is temporarily unavailable. No assessment was stored.",
        ) from exc


@router.post(
    "/scholarships/{scholarship_id}/questions",
    response_model=ScholarshipQuestionResponse,
)
def ask_about_scholarship(
    scholarship_id: uuid.UUID,
    payload: ScholarshipQuestionRequest,
    _rate_limit: None = Depends(require_public_ai_capacity),
    db: Session = Depends(get_db),
) -> ScholarshipQuestionResponse:
    try:
        return answer_scholarship_question(db, scholarship_id, payload)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except AIWorkflowError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI service is temporarily unavailable. No question was stored.",
        ) from exc
