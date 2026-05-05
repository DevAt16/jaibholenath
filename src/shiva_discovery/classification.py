from __future__ import annotations

from dataclasses import dataclass

from .keywords import HIGH_CONFIDENCE_TERMS, MEDIUM_CONFIDENCE_TERMS
from .normalization import normalize_name


@dataclass(frozen=True)
class ConfidenceResult:
    confidence: str
    confidence_score: float
    classification_reason: str


def _matched_terms(name: str, terms: tuple[str, ...]) -> list[str]:
    normalized = normalize_name(name)
    tokens = normalized.split()
    matches: list[str] = []

    for term in terms:
        normalized_term = normalize_name(term)
        compact_term = normalized_term.replace(" ", "")
        if not compact_term:
            continue

        if " " in normalized_term:
            if compact_term in "".join(tokens):
                matches.append(term)
            continue

        if any(compact_term in token for token in tokens):
            matches.append(term)

    return matches


def classify_candidate_name(discovered_name: str | None) -> ConfidenceResult:
    """Classify a candidate from its discovered name only."""
    name = discovered_name or ""
    high_matches = _matched_terms(name, HIGH_CONFIDENCE_TERMS)
    if high_matches:
        score = min(1.0, 0.85 + (0.03 * len(high_matches)))
        return ConfidenceResult(
            confidence="high",
            confidence_score=round(score, 2),
            classification_reason=(
                "Matched high-confidence Shiva terms: "
                + ", ".join(sorted(set(high_matches)))
            ),
        )

    medium_matches = _matched_terms(name, MEDIUM_CONFIDENCE_TERMS)
    if medium_matches:
        score = min(0.79, 0.55 + (0.03 * len(medium_matches)))
        return ConfidenceResult(
            confidence="medium",
            confidence_score=round(score, 2),
            classification_reason=(
                "Matched medium-confidence Shiva terms: "
                + ", ".join(sorted(set(medium_matches)))
            ),
        )

    return ConfidenceResult(
        confidence="low",
        confidence_score=0.2,
        classification_reason="No configured Shiva-specific terms matched the discovered name.",
    )
