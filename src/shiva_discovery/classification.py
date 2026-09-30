from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .keywords import HIGH_CONFIDENCE_TERMS, MEDIUM_CONFIDENCE_TERMS
from .normalization import normalize_name


HIGH_DEVANAGARI_TERMS = (
    "शिव", "महादेव", "महाकाल", "विश्वनाथ", "सोमनाथ", "केदारनाथ",
    "ओंकारेश्वर", "नागेश्वर", "लिंगेश्वर", "रामेश्वर", "शिवालय",
)
MEDIUM_DEVANAGARI_TERMS = ("शंकर", "रुद्र", "भोलेनाथ", "ईश्वर")
NON_TEMPLE_VENUES = frozenset({
    "house", "home", "residence", "shop", "store", "hotel", "cafe", "office",
    "घर", "दुकान", "होटल", "कार्यालय",
})
TEMPLE_WORDS = frozenset({"temple", "mandir", "mandirji", "मंदिर", "मन्दिर", "देवालय", "शिवालय"})


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


def _hindi_words(name: str) -> list[str]:
    return re.findall(r"[\u0900-\u097f]+", unicodedata.normalize("NFKC", name))


def _matched_hindi_terms(name: str, terms: tuple[str, ...]) -> list[str]:
    words = _hindi_words(name)
    return [term for term in terms if any(term in word for word in words)]


def _has_explicit_non_temple_venue(name: str) -> bool:
    latin_words = set(normalize_name(name).split())
    hindi_words = _hindi_words(name)
    venue = bool(latin_words & NON_TEMPLE_VENUES or set(hindi_words) & NON_TEMPLE_VENUES)
    temple = bool(latin_words & TEMPLE_WORDS or set(hindi_words) & TEMPLE_WORDS)
    return venue and not temple


def classify_candidate_name(discovered_name: str | None) -> ConfidenceResult:
    """Classify a candidate from its discovered name only."""
    name = discovered_name or ""
    if _has_explicit_non_temple_venue(name):
        return ConfidenceResult(
            confidence="low",
            confidence_score=0.2,
            classification_reason="Name identifies a non-temple venue; needs manual review.",
        )
    high_matches = (_matched_terms(name, HIGH_CONFIDENCE_TERMS)
                    + _matched_hindi_terms(name, HIGH_DEVANAGARI_TERMS))
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

    medium_matches = (_matched_terms(name, MEDIUM_CONFIDENCE_TERMS)
                      + _matched_hindi_terms(name, MEDIUM_DEVANAGARI_TERMS))
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
