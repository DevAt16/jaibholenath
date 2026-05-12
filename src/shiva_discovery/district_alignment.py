from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .normalization import normalize_name


_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")

DISTRICT_SYNONYMS = {
    "ananthapuramu": "anantapur",
    "anugul": "angul",
    "bagalkote": "bagalkot",
    "baghpat": "bagpat",
    "balodabazar bhatapara": "baloda bazar",
    "baleshwar": "balasore",
    "balrampur ramanujganj": "balrampur",
    "purbi": "east",
    "pashchim": "west",
    "paschim": "west",
    "dakshin": "south",
    "uttar": "north",
    "mancachar": "mankachar",
    "marigaon": "morigaon",
    "salmara mancachar": "salmara mankachar",
    "budaun": "badaun",
    "bara banki": "barabanki",
    "chikkaballapura": "chikballapur",
    "chhatrapati sambhajinagar": "aurangabad",
    "dang": "dangs",
    "dharashiv": "osmanabad",
    "dakshin bastar dantewada": "dantewada",
    "dr b r ambedkar konaseema": "konaseema",
    "devbhumi dwarka": "devbhoomi dwarka",
    "gariyaband": "gariaband",
    "gramin": "rural",
    "jajapur": "jajpur",
    "jangoan": "jangaon",
    "kanniyakumari": "kanyakumari",
    "kancheepuram": "kanchipuram",
    "kachchh": "kutch",
    "kamrup metropolitan": "kamrup metro",
    "korea": "koriya",
    "kumuram bheem asifabad": "kumuram bheem",
    "leparada": "lepa rada",
    "lakhimpur kheri": "kheri",
    "lakshadweep district": "lakshadweep",
    "mahesana": "mehsana",
    "mumbai city": "mumbai",
    "narsimhapur": "narsinghpur",
    "nicobars": "nicobar",
    "panch mahals": "panchmahal",
    "sahebganj": "sahibganj",
    "sahibzada ajit singh nagar": "s a s nagar",
    "shahid bhagat singh nagar": "nawanshahr",
    "shrawasti": "shravasti",
    "siaha": "saiha",
    "sonepur": "subarnapur",
    "south andamans": "south andaman",
    "sri muktsar sahib": "muktsar",
    "the nilgiris": "nilgiris",
    "uttar bastar kanker": "kanker",
    "uttar kashi": "uttarkashi",
    "vijayanagar": "vijayanagara",
    "y s r kadapa": "y s r",
    "chhotaudepur": "chhota udaipur",
    "balodabazar": "baloda bazar",
    "kabeerdham": "kabirdham",
}


@dataclass(frozen=True)
class DistrictMatch:
    lgd_row: dict[str, str]
    db_row: dict[str, object] | None
    match_status: str
    match_method: str
    match_score: float
    review_reason: str


def canonical_state_name(value: object) -> str:
    normalized = normalize_name(value)
    if normalized.startswith("the "):
        normalized = normalized[4:]
    return normalized


def canonical_district_name(value: object, *, state_name: object = "") -> str:
    def replace_parenthetical(match: re.Match[str]) -> str:
        content = normalize_name(match.group(0).strip("()"))
        if content == "gramin":
            return " gramin "
        return " "

    text = _PARENTHETICAL_RE.sub(replace_parenthetical, "" if value is None else str(value))
    normalized = normalize_name(text)
    if normalized.startswith("the "):
        normalized = normalized[4:]
    if normalized.endswith(" district"):
        normalized = normalized.removesuffix(" district").strip()

    state = canonical_state_name(state_name)
    if state:
        state_tokens = state.split()
        district_tokens = normalized.split()
        if len(district_tokens) > len(state_tokens) and district_tokens[-len(state_tokens) :] == state_tokens:
            normalized = " ".join(district_tokens[: -len(state_tokens)]).strip()

    for source, target in sorted(DISTRICT_SYNONYMS.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)

    return " ".join(normalized.split())


def _state_key(row: Mapping[str, object]) -> str:
    return canonical_state_name(row.get("state_name"))


def _district_key(row: Mapping[str, object]) -> str:
    return canonical_district_name(row.get("district_name") or row.get("name"), state_name=row.get("state_name"))


def _score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if len(left) >= 5 and len(right) >= 5 and (left in right or right in left):
        shorter, longer = sorted((left, right), key=len)
        return max(0.9, len(shorter) / len(longer))
    return SequenceMatcher(None, left, right).ratio()


def _best_candidate(
    lgd_row: Mapping[str, str],
    db_rows: list[dict[str, object]],
) -> tuple[dict[str, object] | None, str, float, str]:
    lgd_state = _state_key(lgd_row)
    lgd_name = _district_key(lgd_row)
    lgd_code = str(lgd_row.get("district_lgd_code") or "").strip()

    for db_row in db_rows:
        db_code = str(db_row.get("district_lgd_code") or "").strip()
        if lgd_code and db_code and lgd_code == db_code:
            return db_row, "code", 1.0, "District LGD code already matches."

    exact_candidates = [
        db_row
        for db_row in db_rows
        if _state_key(db_row) == lgd_state and normalize_name(db_row.get("district_name") or db_row.get("name")) == normalize_name(lgd_row.get("district_name"))
    ]
    if len(exact_candidates) == 1:
        return exact_candidates[0], "exact_name", 1.0, "State and district names match exactly after normalization."

    scored: list[tuple[float, dict[str, object]]] = []
    for db_row in db_rows:
        if _state_key(db_row) != lgd_state:
            continue
        scored.append((_score(lgd_name, _district_key(db_row)), db_row))

    if not scored:
        return None, "none", 0.0, "No existing district rows in this state."

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_row = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score == 1.0:
        return best_row, "canonical_name", best_score, "Names match after canonical district-name cleanup."
    if best_score >= 0.93 and best_score - second_score >= 0.05:
        return best_row, "fuzzy_high", best_score, "High similarity within the same state."
    if best_score >= 0.82 and best_score - second_score >= 0.03:
        return best_row, "fuzzy_review", best_score, "Possible match; needs manual review."
    return None, "none", best_score, "No safe candidate above review threshold."


def build_district_alignment(
    *,
    lgd_rows: Iterable[Mapping[str, str]],
    db_rows: Iterable[Mapping[str, object]],
) -> list[DistrictMatch]:
    db_list = [dict(row) for row in db_rows]
    matches: list[DistrictMatch] = []
    matched_db_ids: set[str] = set()
    pending_conflicts: defaultdict[str, list[DistrictMatch]] = defaultdict(list)

    for lgd_raw in lgd_rows:
        lgd_row = {str(key): "" if value is None else str(value) for key, value in lgd_raw.items()}
        db_row, method, score, reason = _best_candidate(lgd_row, db_list)
        if db_row is None:
            status = "missing_in_db"
        elif method in {"code", "exact_name", "canonical_name", "fuzzy_high"}:
            status = "auto"
        else:
            status = "review"

        match = DistrictMatch(lgd_row, db_row, status, method, score, reason)
        if db_row is not None:
            pending_conflicts[str(db_row.get("id"))].append(match)
        matches.append(match)

    conflicted_ids = {
        db_id for db_id, db_matches in pending_conflicts.items() if len(db_matches) > 1
    }
    resolved: list[DistrictMatch] = []
    for match in matches:
        db_id = str(match.db_row.get("id")) if match.db_row is not None else ""
        if db_id in conflicted_ids:
            resolved.append(
                DistrictMatch(
                    match.lgd_row,
                    match.db_row,
                    "review",
                    match.match_method,
                    match.match_score,
                    "Multiple LGD districts matched the same existing DB row.",
                )
            )
        elif db_id and match.match_status == "auto":
            matched_db_ids.add(db_id)
            resolved.append(match)
        else:
            resolved.append(match)

    matched_lgd_db_ids = {
        str(match.db_row.get("id"))
        for match in resolved
        if match.db_row is not None and match.match_status in {"auto", "review"}
    }
    for db_row in db_list:
        db_id = str(db_row.get("id"))
        if db_id not in matched_lgd_db_ids:
            resolved.append(
                DistrictMatch(
                    {},
                    db_row,
                    "db_only",
                    "none",
                    0.0,
                    "Existing DB district did not match an LGD district.",
                )
            )

    return resolved


def alignment_row(match: DistrictMatch) -> dict[str, object]:
    lgd = match.lgd_row
    db = match.db_row or {}
    return {
        "match_status": match.match_status,
        "match_method": match.match_method,
        "match_score": f"{match.match_score:.3f}",
        "review_reason": match.review_reason,
        "db_id": db.get("id", ""),
        "db_state_name": db.get("state_name", ""),
        "db_district_name": db.get("district_name") or db.get("name", ""),
        "db_state_lgd_code": db.get("state_lgd_code", ""),
        "db_district_lgd_code": db.get("district_lgd_code", ""),
        "db_source": db.get("source", ""),
        "lgd_state_name": lgd.get("state_name", ""),
        "lgd_district_name": lgd.get("district_name", ""),
        "lgd_state_lgd_code": lgd.get("state_lgd_code", ""),
        "lgd_district_lgd_code": lgd.get("district_lgd_code", ""),
        "lgd_source": lgd.get("source", ""),
    }
