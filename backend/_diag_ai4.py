"""Confirm the real discovery payload's token request vs the Groq 8000 TPM ceiling."""

from __future__ import annotations

import json
import time
import traceback

from app.agents.scholarship_ai import run_discovery_agent
from app.core.config import get_settings
from app.database import SessionLocal
from app.models import KnowledgeChunk
from app.schemas import DiscoveryProfile
from app.services.ai_discovery import _candidate_query
from sqlalchemy import select

settings = get_settings()
profile = DiscoveryProfile(message="I study BTech in Odisha. Which scholarships fit me?")

db = SessionLocal()
rows = db.execute(_candidate_query(profile)).all()
version_ids = [v.id for _, v, _ in rows]
chunks = db.scalars(
    select(KnowledgeChunk).where(
        KnowledgeChunk.scholarship_version_id.in_(version_ids),
        KnowledgeChunk.confirmation_status == "OWNER_CONFIRMED",
    )
).all()
db.close()

payload_chars = sum(len(c.provider_text or "") for c in chunks) + sum(
    len(v.title or "") for _, v, _ in rows
)
est_input = payload_chars // 4 + 400  # evidence + instructions/scaffolding
print(f"candidates={len(rows)} chunks={len(chunks)}")
print(f"estimated input tokens ~{est_input}")
print(f"max_tokens requested by _generate_discovery = 5000")
print(f"=> Groq counts requested ~= {est_input + 5000} against a free-tier limit of 8000 TPM")

print("\nFiring two back-to-back discovery calls (as two users a few seconds apart would):")
for attempt in (1, 2):
    started = time.time()
    try:
        result = run_discovery_agent(
            {
                "student_facts": profile.model_dump(mode="json", exclude_none=True),
                "candidate_scholarships": [
                    {"scholarship_version_id": str(v.id), "title": v.title, "evidence": []}
                    for _, v, _ in rows
                ],
            },
            {str(v.id): set() for _, v, _ in rows},
        )
        print(f"  call {attempt}: OK in {time.time() - started:.1f}s "
              f"({len(result.assessments)} assessments)")
    except Exception as exc:
        print(f"  call {attempt}: FAILED in {time.time() - started:.1f}s -> {type(exc).__name__}")
        cause = exc.__cause__
        print(f"    underlying: {type(cause).__name__ if cause else None}")
        print(f"    detail: {str(cause)[:400] if cause else str(exc)[:400]}")
