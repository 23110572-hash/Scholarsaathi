"""Isolate whether Groq strict json_schema rejects the minimum/maximum keywords."""

from __future__ import annotations

import copy
import json

import httpx
from langchain_core.utils.function_calling import convert_to_json_schema

from app.core.config import get_settings
from app.schemas import DiscoveryAssessmentBundle

settings = get_settings()
KEY = settings.groq_api_key.get_secret_value()
URL = "https://api.groq.com/openai/v1/chat/completions"

schema_with_bounds = convert_to_json_schema(DiscoveryAssessmentBundle, strict=True)

# Same schema, but with the numeric range keywords removed.
schema_no_bounds = copy.deepcopy(schema_with_bounds)
conf = schema_no_bounds["properties"]["assessments"]["items"]["properties"]["confidence"]
conf.pop("minimum", None)
conf.pop("maximum", None)

messages = [
    {"role": "system", "content": "Return one assessment for the given scholarship."},
    {
        "role": "user",
        "content": json.dumps(
            {
                "student_facts": {"state": "OD", "course": "BTECH"},
                "candidate_scholarships": [
                    {
                        "scholarship_version_id": "22222222-2222-2222-2222-222222222222",
                        "title": "Test Merit Scholarship",
                        "evidence": [
                            {
                                "citation_id": "33333333-3333-3333-3333-333333333333",
                                "text": "Open to UG BTech students domiciled in Odisha.",
                            }
                        ],
                    }
                ],
            }
        ),
    },
]


def attempt(label: str, schema: dict) -> None:
    body = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 5000,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "DiscoveryAssessmentBundle", "schema": schema, "strict": True},
        },
    }
    resp = httpx.post(
        URL,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    print(f"\n=== {label} ===")
    print("HTTP", resp.status_code)
    if resp.status_code != 200:
        print(json.dumps(resp.json(), indent=2)[:1500])
    else:
        print("OK, content starts:", resp.json()["choices"][0]["message"]["content"][:160])


attempt("A) strict schema AS THE APP SENDS IT (has minimum/maximum)", schema_with_bounds)
attempt("B) identical schema WITHOUT minimum/maximum", schema_no_bounds)
