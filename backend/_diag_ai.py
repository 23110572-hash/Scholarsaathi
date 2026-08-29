"""Temporary diagnostic: reproduce the discovery agent Groq call and print the real error."""

from __future__ import annotations

import json
import traceback

from app.agents.scholarship_ai import DISCOVERY_INSTRUCTIONS, _chat_model
from app.core.config import get_settings
from app.schemas import DiscoveryAssessmentBundle
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_json_schema

settings = get_settings()
print("model:", settings.groq_model)
print("api key present:", bool(settings.groq_api_key))

print("\n--- strict json schema that gets sent ---")
try:
    schema = convert_to_json_schema(DiscoveryAssessmentBundle, strict=True)
    print(json.dumps(schema, indent=2)[:4000])
except Exception:
    traceback.print_exc()

payload = {
    "student_facts": {"state": "OD", "education_level": "UG", "course": "BTECH"},
    "candidate_scholarships": [
        {
            "scholarship_id": "11111111-1111-1111-1111-111111111111",
            "scholarship_version_id": "22222222-2222-2222-2222-222222222222",
            "title": "Test Merit Scholarship",
            "provider": "Test Provider",
            "provider_type": "GOVERNMENT",
            "deadline": None,
            "evidence": [
                {
                    "citation_id": "33333333-3333-3333-3333-333333333333",
                    "section": "Eligibility",
                    "page": 1,
                    "text": "Open to UG BTech students domiciled in Odisha.",
                }
            ],
        }
    ],
}

print("\n--- attempt 1: current code path (json_schema, strict=True) ---")
try:
    model = _chat_model(5000).with_structured_output(
        DiscoveryAssessmentBundle, method="json_schema", strict=True
    )
    out = model.invoke(
        [
            SystemMessage(content=DISCOVERY_INSTRUCTIONS),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
    )
    print("OK ->", out)
except Exception as exc:
    print("FAILED:", type(exc).__module__ + "." + type(exc).__name__)
    print(exc)

print("\n--- attempt 2: plain chat call (is the model/key itself fine?) ---")
try:
    out = _chat_model(64).invoke([HumanMessage(content="Reply with the single word: pong")])
    print("OK ->", repr(out.content))
except Exception as exc:
    print("FAILED:", type(exc).__module__ + "." + type(exc).__name__)
    print(exc)
