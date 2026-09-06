from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.schemas import AIClaim, DiscoveryProfile, ScholarshipAssessment

RuleOutcome = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class RuleCheck:
    outcome: RuleOutcome
    statement: str
    missing_detail: str | None = None


_INCOME_BOUNDS: dict[str, tuple[int, int | None]] = {
    "UP_TO_250000": (0, 250_000),
    "250001_TO_400000": (250_001, 400_000),
    "400001_TO_600000": (400_001, 600_000),
    "600001_TO_800000": (600_001, 800_000),
    "ABOVE_800000": (800_001, None),
}
_STEM_COURSES = frozenset({"STEM", "BTECH", "BE", "BARCH", "BSC"})


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _number_text(value: float) -> str:
    return f"{value:g}"


def _rupees(value: float) -> str:
    return f"₹{value:,.0f}"


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip().upper() for item in value if isinstance(item, str) and item.strip()]


def _eligibility_citations(candidate: dict[str, Any]) -> list[str]:
    evidence = candidate.get("evidence")
    if not isinstance(evidence, list):
        return []
    preferred = [
        item
        for item in evidence
        if isinstance(item, dict)
        and any(
            token in str(item.get("section", "")).lower()
            for token in ("eligib", "criteria", "requirement")
        )
    ]
    selected = preferred or [item for item in evidence if isinstance(item, dict)]
    for item in selected:
        citation_id = item.get("citation_id")
        if isinstance(citation_id, str) and citation_id:
            return [citation_id]
    return []


def _course_matches(profile: DiscoveryProfile, eligible_courses: list[str]) -> bool | None:
    if not eligible_courses:
        return None
    course = profile.course
    if not course:
        return None
    if course in eligible_courses or "ALL_RECOGNIZED_COURSES" in eligible_courses:
        return True
    if "ALL_UNDERGRADUATE" in eligible_courses:
        if profile.education_level is None:
            return None
        if profile.education_level == "UNDERGRADUATE":
            return True
    return "STEM" in eligible_courses and course in _STEM_COURSES


def _structured_checks(profile: DiscoveryProfile, rules: dict[str, Any]) -> list[RuleCheck]:
    checks: list[RuleCheck] = []

    minimum_marks = _number(rules.get("minimum_marks_percentage"))
    if minimum_marks is not None:
        if profile.marks_percentage is None:
            checks.append(
                RuleCheck(
                    "UNKNOWN",
                    "Your latest academic percentage is needed.",
                    "latest academic percentage",
                )
            )
        elif profile.marks_percentage >= minimum_marks:
            checks.append(
                RuleCheck(
                    "PASS",
                    f"Your {_number_text(profile.marks_percentage)}% meets the published minimum of "
                    f"{_number_text(minimum_marks)}%.",
                )
            )
        else:
            checks.append(
                RuleCheck(
                    "FAIL",
                    f"Your {_number_text(profile.marks_percentage)}% is below the published minimum of "
                    f"{_number_text(minimum_marks)}%.",
                )
            )

    maximum_income = _number(rules.get("maximum_family_income"))
    if maximum_income is not None:
        bounds = _INCOME_BOUNDS.get(profile.family_income_range or "")
        if bounds is None:
            checks.append(
                RuleCheck("UNKNOWN", "Your annual family income is needed.", "annual family income")
            )
        else:
            lower, upper = bounds
            if upper is not None and upper <= maximum_income:
                checks.append(
                    RuleCheck(
                        "PASS",
                        f"Your selected family-income range is within the published "
                        f"{_rupees(maximum_income)} limit.",
                    )
                )
            elif lower > maximum_income:
                checks.append(
                    RuleCheck(
                        "FAIL",
                        f"Your selected family-income range is above the published "
                        f"{_rupees(maximum_income)} limit.",
                    )
                )
            else:
                checks.append(
                    RuleCheck(
                        "UNKNOWN",
                        "Your selected income range overlaps the scholarship limit.",
                        "exact annual family income",
                    )
                )

    state_rule = rules.get("state_codes")
    if isinstance(state_rule, dict):
        operator = str(state_rule.get("operator", "")).upper()
        state_codes = _string_values(state_rule.get("values"))
        if operator == "ALL_INDIA" or "ALL" in state_codes:
            if profile.state:
                checks.append(RuleCheck("PASS", "Your State or UT is covered by this scholarship."))
        elif state_codes:
            if not profile.state:
                checks.append(RuleCheck("UNKNOWN", "Your State or UT is needed.", "State or UT"))
            elif profile.state in state_codes:
                checks.append(
                    RuleCheck("PASS", "Your State or UT is included in the published coverage.")
                )
            else:
                checks.append(
                    RuleCheck("FAIL", "Your State or UT is outside the published coverage.")
                )

    education_levels = _string_values(
        (rules.get("education_levels") or {}).get("values")
        if isinstance(rules.get("education_levels"), dict)
        else None
    )
    if education_levels:
        if not profile.education_level:
            checks.append(
                RuleCheck("UNKNOWN", "Your education level is needed.", "education level")
            )
        elif profile.education_level in education_levels:
            checks.append(
                RuleCheck("PASS", "Your education level matches the published requirement.")
            )
        else:
            checks.append(
                RuleCheck("FAIL", "Your education level does not match the published requirement.")
            )

    course_families = _string_values(
        (rules.get("course_families") or {}).get("values")
        if isinstance(rules.get("course_families"), dict)
        else None
    )
    if course_families:
        course_match = _course_matches(profile, course_families)
        if course_match is None:
            checks.append(RuleCheck("UNKNOWN", "Your current course is needed.", "current course"))
        elif course_match:
            checks.append(
                RuleCheck("PASS", "Your course matches the published course requirement.")
            )
        else:
            checks.append(
                RuleCheck("FAIL", "Your course does not match the published course requirement.")
            )

    eligible_years = [
        int(value)
        for value in rules.get("eligible_course_years", [])
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    if eligible_years:
        if profile.course_year is None:
            checks.append(
                RuleCheck("UNKNOWN", "Your current study year is needed.", "current study year")
            )
        elif profile.course_year in eligible_years:
            checks.append(
                RuleCheck("PASS", "Your current study year is included in the published rules.")
            )
        else:
            checks.append(
                RuleCheck("FAIL", "Your current study year is outside the published rules.")
            )

    eligible_categories = _string_values(rules.get("eligible_categories"))
    if eligible_categories and "ALL" not in eligible_categories:
        if not profile.categories:
            checks.append(
                RuleCheck("UNKNOWN", "Your applicable category is needed.", "applicable category")
            )
        elif set(profile.categories).intersection(eligible_categories):
            checks.append(
                RuleCheck("PASS", "Your category matches the published category requirement.")
            )
        else:
            checks.append(
                RuleCheck(
                    "FAIL", "Your categories do not match the published category requirement."
                )
            )

    eligible_genders = _string_values(rules.get("eligible_genders"))
    if eligible_genders and "ALL" not in eligible_genders:
        if not profile.gender or profile.gender == "PREFER_NOT_TO_SAY":
            checks.append(RuleCheck("UNKNOWN", "Your gender is needed for this rule.", "gender"))
        elif profile.gender in eligible_genders:
            checks.append(RuleCheck("PASS", "Your gender matches the published requirement."))
        else:
            checks.append(
                RuleCheck("FAIL", "Your gender does not match the published requirement.")
            )

    if rules.get("requires_disability") is True:
        if "DISABILITY" in profile.categories:
            checks.append(
                RuleCheck("PASS", "Your disability category matches the published requirement.")
            )
        else:
            checks.append(
                RuleCheck(
                    "UNKNOWN",
                    "This scholarship requires disability eligibility information.",
                    "disability eligibility",
                )
            )

    return checks


def evaluate_structured_eligibility(
    profile: DiscoveryProfile,
    candidate: dict[str, Any],
) -> ScholarshipAssessment | None:
    """Evaluate machine-readable provider rules without delegating arithmetic to an LLM."""
    rules = candidate.get("eligibility_rules")
    if not isinstance(rules, dict) or not rules:
        return None

    checks = _structured_checks(profile, rules)
    if not checks:
        return None

    citation_ids = _eligibility_citations(candidate)
    passing = [check for check in checks if check.outcome == "PASS"]
    failing = [check for check in checks if check.outcome == "FAIL"]
    unknown = [check for check in checks if check.outcome == "UNKNOWN"]

    if failing:
        label = "LIKELY_NOT_ELIGIBLE"
        confidence = 0.98
        summary = failing[0].statement
    elif unknown:
        label = "POSSIBLY_ELIGIBLE_NEEDS_INFORMATION"
        confidence = 0.72
        summary = (
            "Your known details meet the checks completed so far, but more information is "
            "needed for the remaining published rules."
        )
    else:
        label = "LIKELY_ELIGIBLE"
        confidence = 0.96
        summary = (
            "Your details meet the published structured eligibility checks for this scholarship."
        )

    return ScholarshipAssessment(
        scholarship_version_id=str(candidate["scholarship_version_id"]),
        assessment=label,
        confidence=confidence,
        summary=summary,
        matching_points=[
            AIClaim(statement=check.statement, citation_ids=citation_ids) for check in passing
        ],
        possible_conflicts=[
            AIClaim(statement=check.statement, citation_ids=citation_ids) for check in failing
        ],
        missing_information=list(
            dict.fromkeys(
                check.missing_detail for check in unknown if check.missing_detail is not None
            )
        ),
        next_steps=[
            "Open the scholarship to review every published condition and required document."
        ],
        warning="The scholarship provider makes the final eligibility decision.",
    )


def assessment_introduction(assessments: list[ScholarshipAssessment]) -> str:
    strong = sum(item.assessment == "LIKELY_ELIGIBLE" for item in assessments)
    possible = sum(item.assessment == "POSSIBLY_ELIGIBLE_NEEDS_INFORMATION" for item in assessments)
    if strong:
        suffix = f" {possible} more need additional information." if possible else ""
        return f"I checked the published rules and found {strong} strong match(es).{suffix}"
    if possible:
        return (
            f"I found {possible} possible match(es), but a few more details are needed before "
            "the published rules can be checked completely."
        )
    return "I checked your details against the published structured eligibility rules."
