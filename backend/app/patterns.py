"""Transparent, conservative phrase-based grouping of complaint narratives.

This is NOT a defect classifier, a failure estimate, or a diagnosis. Only explicit
phrases from complaint text are counted; each group links to supporting ODI IDs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Iterable
from urllib.parse import quote


@dataclass(frozen=True)
class PatternRule:
    key: str
    title: str
    description: str
    expressions: tuple[str, ...]


RULES = (
    PatternRule(
        "engine_stall", "Engine stalling / power loss",
        "Narratives mentioning engine stalling or unexpected loss of propulsion.",
        (
            r"\b(?:engine|vehicle|car)\s+(?:suddenly\s+)?(?:stalled|stalls|shut\s*(?:off|down)|lost\s+power)\b",
            r"\bloss of (?:engine\s+)?power\b",
            r"\bengine (?:cut|cuts) out\b",
        ),
    ),
    PatternRule(
        "braking", "Brake performance concerns",
        "Narratives describing reduced braking or brake-pedal problems.",
        (
            r"\bbrakes?\s+(?:failed|fail|stopped working|not working|lost pressure)\b",
            r"\bbrake pedal\s+(?:went|goes|sank)\s+to\s+(?:the\s+)?floor\b",
            r"\bloss of braking\b",
        ),
    ),
    PatternRule(
        "steering", "Steering loss / lockup",
        "Narratives mentioning loss of steering assistance or steering lockup.",
        (
            r"\b(?:loss|lost) of (?:power\s+)?steering\b",
            r"\bsteering (?:wheel\s+)?(?:locked|locks|became stiff)\b",
            r"\bpower steering\s+(?:failed|stopped working)\b",
        ),
    ),
    PatternRule(
        "unexpected_acceleration", "Unexpected acceleration",
        "Narratives explicitly alleging acceleration without driver intent.",
        (
            r"\b(?:sudden|unintended|unexpected) acceleration\b",
            r"\baccelerated\s+(?:on its own|without (?:warning|driver input))\b",
            r"\bvehicle surged forward\b",
        ),
    ),
    PatternRule(
        "transmission", "Transmission / shifting concerns",
        "Narratives mentioning rough, delayed, or failed gear changes.",
        (
            r"\b(?:hard|rough|delayed|jerky)\s+shift(?:s|ing)?\b",
            r"\b(?:transmission|gearbox)\s+(?:would not|failed to|did not|does not)\s+shift\b",
            r"\btransmission\s+(?:slipped|slipping)\b",
        ),
    ),
    PatternRule(
        "airbag", "Airbag non-deployment reports",
        "Narratives explicitly reporting that an airbag did not deploy.",
        (
            r"\bair\s?bags?\s+(?:did not|didn't|failed to|never)\s+deploy\b",
            r"\bair\s?bag\s+failure to deploy\b",
        ),
    ),
    PatternRule(
        "electrical", "Electrical power problems",
        "Narratives mentioning electrical failures or unexpectedly drained batteries.",
        (
            r"\b(?:electrical|electronic) system\s+(?:failed|shut down)\b",
            r"\b(?:12[- ]?volt\s+|12v\s+)?battery\s+(?:drained|died|keeps dying)\b",
            r"\b(?:vehicle|car)\s+(?:lost|loses) all electrical power\b",
        ),
    ),
    PatternRule(
        "overheating", "Engine overheating",
        "Narratives explicitly mentioning engine overheating.",
        (
            r"\bengine\s+overheat(?:ed|s|ing)?\b",
            r"\bengine\s+(?:was|is) overheating\b",
        ),
    ),

    PatternRule(
        "engine_oil_leak",
        "Reported engine oil leaks",
        "Complaints explicitly mentioning engine oil leakage.",
        (
            r"\b(?:engine\s+)?oil\s+leak(?:s|ing|ed)?\b",
            r"\bleak(?:s|ing|ed)?\s+(?:engine\s+)?oil\b",
            r"\boil\s+(?:is\s+)?leaking\s+from\s+(?:the\s+)?engine\b",
        ),
    ),
)

# Compile once at module import, not on every complaint.
COMPILED_RULES = tuple(
    (rule, tuple(re.compile(expr, re.IGNORECASE) for expr in rule.expressions))
    for rule in RULES
)


def matched_phrases(summary: str | None) -> dict[str, str]:
    """Return at most one literal matched phrase per rule, never inferred causes."""
    if not summary or not summary.strip():
        return {}
    result = {}
    for rule, expressions in COMPILED_RULES:
        matches = [match for expr in expressions if (match := expr.search(summary))]
        if matches:
            first = min(matches, key=lambda match: match.start())
            result[rule.key] = first.group(0)
    return result


def group_complaints(complaints: Iterable) -> list[dict]:
    """Build evidence-backed groups from SQL Complaint objects, no schema migration.

    All matched ODI IDs are included for UI filtering; three sample records per
    group carry literal excerpts and official source links. The count is the
    number of distinct complaint IDs, not confirmed faults.
    """
    grouped = defaultdict(list)
    for complaint in complaints:
        for key, phrase in matched_phrases(complaint.summary).items():
            grouped[key].append((complaint, phrase))

    result = []
    for rule in RULES:
        rows = grouped.get(rule.key, [])
        if not rows:
            continue
        # Input rows are already unique by ODI number for a vehicle in SQL.
        odi_numbers = list(dict.fromkeys(str(c.odi_number) for c, _ in rows))
        examples = [
            {
                "odi_number": str(c.odi_number),
                "matched_phrase": phrase,
                "summary": c.summary,
                "source_url": "https://api.nhtsa.gov/complaints/odinumber?odinumber=" + quote(str(c.odi_number), safe=""),
            }
            for c, phrase in rows[:3]
        ]
        result.append({
            "key": rule.key,
            "title": rule.title,
            "description": rule.description,
            "count": len(odi_numbers),
            "odi_numbers": odi_numbers,
            "examples": examples,
        })
    return sorted(result, key=lambda item: (-item["count"], item["title"]))
