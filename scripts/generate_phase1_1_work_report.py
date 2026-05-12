from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
import subprocess
from typing import Any

import _bootstrap  # noqa: F401
from shiva_discovery.db import connect


LGD_CATALOG_URL = "https://www.data.gov.in/catalog/local-government-directory-lgd"
MOPR_LGD_URL = "https://panchayat.gov.in/en/lgd/"
GOOGLE_TEXT_SEARCH_URL = (
    "https://developers.google.com/maps/documentation/places/web-service/text-search"
)

PHASE1_KEYWORDS = (
    "Shiva temple",
    "Shiv Mandir",
    "Mahadev temple",
    "Mahadev Mandir",
    "Shankar Mandir",
    "Someshwar temple",
    "Vishwanath temple",
    "Lingeshwar temple",
    "Rudreshwar temple",
)

COLORS = {
    "ink": "#17212b",
    "muted": "#607085",
    "paper": "#fbfaf7",
    "surface": "#ffffff",
    "line": "#d9e1ea",
    "accent": "#bf513b",
    "gold": "#d7a23a",
    "green": "#218a6a",
    "blue": "#4f6fa9",
    "purple": "#7662a8",
}


@dataclass(frozen=True)
class WorkReportData:
    generated_at: datetime
    summary: dict[str, str]
    prepared_lgd_districts: int
    candidate_rows: int
    active_districts: int
    active_districts_with_lgd_code: int
    inactive_districts: int
    district_task_status: dict[str, int]
    district_task_results: dict[str, int]
    confidence_counts: dict[str, int]
    first_alignment_status: dict[str, int]
    alias_alignment_status: dict[str, int]
    final_alignment_status: dict[str, int]
    top_states: list[dict[str, str]]
    top_districts: list[dict[str, str]]
    keyword_counts: Counter[str]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _as_int(value: object) -> int:
    if value in (None, ""):
        return 0
    return int(float(str(value)))


def _fmt_int(value: object) -> str:
    return f"{_as_int(value):,}"


def _pct(numerator: int, denominator: int) -> float:
    return (numerator / denominator * 100) if denominator else 0.0


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _group_status(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    counts: Counter[str] = Counter()
    for row in _read_csv(path):
        status = (row.get("match_status") or "unknown").strip() or "unknown"
        counts[status] += 1
    return dict(counts)


def _candidate_keyword_counts(path: Path) -> tuple[int, Counter[str]]:
    if not path.exists():
        return 0, Counter()

    rows = 0
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            query = (row.get("source_query") or "").strip()
            keyword = query.split(" in ", 1)[0].strip() if " in " in query else query
            if keyword:
                counts[keyword] += 1
    return rows, counts


def _fetch_db_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {
        "active_districts": 0,
        "active_districts_with_lgd_code": 0,
        "inactive_districts": 0,
        "district_task_status": {},
        "district_task_results": {},
        "confidence_counts": {},
    }
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE is_active = TRUE AND location_type = 'district'
                        ) AS active_districts,
                        COUNT(*) FILTER (
                            WHERE is_active = TRUE
                              AND location_type = 'district'
                              AND district_lgd_code IS NOT NULL
                              AND district_lgd_code <> ''
                        ) AS active_districts_with_lgd_code,
                        COUNT(*) FILTER (
                            WHERE is_active = FALSE AND location_type = 'district'
                        ) AS inactive_districts
                    FROM india_locations;
                    """
                )
                row = cursor.fetchone()
                stats["active_districts"] = int(row[0] or 0)
                stats["active_districts_with_lgd_code"] = int(row[1] or 0)
                stats["inactive_districts"] = int(row[2] or 0)

                cursor.execute(
                    """
                    SELECT task.status, COUNT(*), COALESCE(SUM(task.result_count), 0)
                    FROM temple_search_tasks AS task
                    JOIN india_locations AS loc ON loc.id = task.location_id
                    WHERE loc.location_type = 'district'
                      AND loc.is_active = TRUE
                    GROUP BY task.status;
                    """
                )
                for status, count, result_count in cursor.fetchall():
                    stats["district_task_status"][str(status)] = int(count or 0)
                    stats["district_task_results"][str(status)] = int(result_count or 0)

                cursor.execute(
                    """
                    SELECT candidate.confidence, COUNT(*)
                    FROM temple_candidates AS candidate
                    JOIN india_locations AS loc ON loc.id = candidate.source_location_id
                    WHERE loc.location_type = 'district'
                      AND loc.is_active = TRUE
                    GROUP BY candidate.confidence;
                    """
                )
                for confidence, count in cursor.fetchall():
                    stats["confidence_counts"][str(confidence)] = int(count or 0)
    except Exception as exc:  # pragma: no cover - report should still render from CSVs
        print(f"Database stats unavailable; using CSV fallback where possible: {exc}")

    return stats


def load_report_data(
    *,
    report_dir: Path,
    prepared_districts_path: Path,
    verification_dir: Path,
) -> WorkReportData:
    summary_rows = _read_csv(report_dir / "national_summary.csv")
    if not summary_rows:
        raise ValueError("national_summary.csv has no data rows.")
    summary = summary_rows[0]

    state_rows = _read_csv(report_dir / "state_counts.csv")
    district_rows = _read_csv(report_dir / "district_counts.csv")
    candidate_rows, keyword_counts = _candidate_keyword_counts(report_dir / "candidate_review.csv")
    prepared_lgd_districts = len(_read_csv(prepared_districts_path))

    db_stats = _fetch_db_stats()
    confidence_counts = dict(db_stats["confidence_counts"])
    if not confidence_counts:
        confidence_counts = {
            "high": _as_int(summary.get("high_confidence_shiva")),
            "medium": _as_int(summary.get("medium_confidence_shiva_candidates")),
            "low": _as_int(summary.get("low_confidence_possible_temples")),
        }

    return WorkReportData(
        generated_at=datetime.now(),
        summary=summary,
        prepared_lgd_districts=prepared_lgd_districts,
        candidate_rows=candidate_rows,
        active_districts=int(db_stats["active_districts"] or prepared_lgd_districts),
        active_districts_with_lgd_code=int(
            db_stats["active_districts_with_lgd_code"] or prepared_lgd_districts
        ),
        inactive_districts=int(db_stats["inactive_districts"] or 0),
        district_task_status=dict(db_stats["district_task_status"]),
        district_task_results=dict(db_stats["district_task_results"]),
        confidence_counts=confidence_counts,
        first_alignment_status=_group_status(verification_dir / "district_alignment_review.csv"),
        alias_alignment_status=_group_status(
            verification_dir / "district_alignment_review_after_aliases.csv"
        ),
        final_alignment_status=_group_status(
            verification_dir / "district_alignment_after_manual_exceptions.csv"
        ),
        top_states=sorted(
            state_rows,
            key=lambda row: _as_int(row.get("unique_google_place_ids")),
            reverse=True,
        )[:8],
        top_districts=sorted(
            district_rows,
            key=lambda row: _as_int(row.get("unique_google_place_ids")),
            reverse=True,
        )[:10],
        keyword_counts=keyword_counts,
    )


def _metric_card(label: str, value: str, note: str) -> str:
    return f"""
        <div class="metric-card">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(value)}</div>
            <div class="metric-note">{escape(note)}</div>
        </div>
    """


def _table(headers: list[str], rows: list[list[object]], classes: str = "") -> str:
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>")
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _status_table(label: str, counts: dict[str, int]) -> str:
    rows = [[status, _fmt_int(count)] for status, count in sorted(counts.items())]
    if not rows:
        rows = [["No file found", "0"]]
    return f"""
        <div class="panel compact">
            <h3>{escape(label)}</h3>
            {_table(["Status", "Rows"], rows)}
        </div>
    """


def _stacked_bar(segments: list[tuple[str, int, str]], total: int) -> str:
    parts = ['<div class="stacked-bar">']
    for label, value, color in segments:
        width = max(0.0, _pct(value, total))
        parts.append(
            f'<div title="{escape(label)}: {_fmt_int(value)}" '
            f'style="width:{width:.4f}%; background:{color};"></div>'
        )
    parts.append("</div>")
    parts.append('<div class="legend">')
    for label, value, color in segments:
        parts.append(
            f'<span><i style="background:{color};"></i>{escape(label)} '
            f'{_fmt_int(value)} ({_fmt_pct(_pct(value, total))})</span>'
        )
    parts.append("</div>")
    return "".join(parts)


def _rank_rows(rows: list[dict[str, str]], *, district: bool = False) -> list[list[object]]:
    output: list[list[object]] = []
    for row in rows:
        total = _as_int(row.get("unique_google_place_ids"))
        high = _as_int(row.get("high_confidence_shiva"))
        medium = _as_int(row.get("medium_confidence_shiva_candidates"))
        signal = high + medium
        if district:
            output.append(
                [
                    row.get("state", ""),
                    row.get("district", ""),
                    _fmt_int(total),
                    _fmt_int(high),
                    _fmt_pct(_pct(signal, total)),
                ]
            )
        else:
            output.append(
                [
                    row.get("state", ""),
                    _fmt_int(total),
                    _fmt_int(high),
                    _fmt_pct(_pct(signal, total)),
                ]
            )
    return output


def _keyword_rows(counter: Counter[str]) -> list[list[object]]:
    total = sum(counter.values())
    return [
        [keyword, _fmt_int(count), _fmt_pct(_pct(count, total))]
        for keyword, count in counter.most_common(9)
    ]


def render_html(data: WorkReportData) -> str:
    summary = data.summary
    total = _as_int(summary["total_discovered_candidates"])
    unique = _as_int(summary["unique_google_place_ids"])
    high = _as_int(summary["high_confidence_shiva"])
    medium = _as_int(summary["medium_confidence_shiva_candidates"])
    low = _as_int(summary["low_confidence_possible_temples"])
    duplicates = _as_int(summary["duplicates_removed"])
    signal = high + medium
    done_tasks = data.district_task_status.get("done", 0)
    failed_tasks = data.district_task_status.get("failed", 0)
    total_tasks = sum(data.district_task_status.values()) or data.active_districts * len(PHASE1_KEYWORDS)
    generated_label = data.generated_at.strftime("%B %d, %Y %I:%M %p")

    confidence_bar = _stacked_bar(
        [
            ("High", high, COLORS["green"]),
            ("Medium", medium, COLORS["gold"]),
            ("Low", low, COLORS["blue"]),
        ],
        unique,
    )
    task_bar = _stacked_bar(
        [
            ("Done", done_tasks, COLORS["green"]),
            ("Failed", failed_tasks, COLORS["accent"]),
        ],
        total_tasks,
    )

    alignment_rows = [
        [
            "Initial LGD vs DB review",
            _fmt_int(data.first_alignment_status.get("auto", 0)),
            _fmt_int(data.first_alignment_status.get("review", 0)),
            _fmt_int(data.first_alignment_status.get("missing_in_db", 0)),
            _fmt_int(data.first_alignment_status.get("db_only", 0)),
        ],
        [
            "After canonical aliases",
            _fmt_int(data.alias_alignment_status.get("auto", 0)),
            _fmt_int(data.alias_alignment_status.get("review", 0)),
            _fmt_int(data.alias_alignment_status.get("missing_in_db", 0)),
            _fmt_int(data.alias_alignment_status.get("db_only", 0)),
        ],
        [
            "After manual exceptions",
            _fmt_int(data.final_alignment_status.get("auto", 0)),
            _fmt_int(data.final_alignment_status.get("review", 0)),
            _fmt_int(data.final_alignment_status.get("missing_in_db", 0)),
            _fmt_int(data.final_alignment_status.get("db_only", 0)),
        ],
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Phase 1.1 Consolidated Work Report</title>
<style>
@page {{ size: A4; margin: 15mm 14mm; }}
* {{ box-sizing: border-box; }}
html {{ color: {COLORS["ink"]}; font-family: Arial, Helvetica, sans-serif; }}
body {{ margin: 0; background: {COLORS["paper"]}; font-size: 10pt; line-height: 1.45; }}
.page {{ page-break-after: always; min-height: 267mm; }}
.page:last-child {{ page-break-after: auto; }}
.cover {{ display: flex; flex-direction: column; justify-content: space-between; }}
.band {{ height: 12mm; border-radius: 7px; background: linear-gradient(90deg, {COLORS["accent"]}, {COLORS["gold"]}, {COLORS["green"]}); margin-bottom: 10mm; }}
.kicker {{ color: {COLORS["accent"]}; font-weight: 800; font-size: 10pt; letter-spacing: .04em; text-transform: uppercase; }}
h1 {{ font-size: 34pt; line-height: 1.04; margin: 5mm 0 5mm; letter-spacing: 0; }}
h2 {{ font-size: 18pt; margin: 0 0 5mm; }}
h3 {{ font-size: 11.5pt; margin: 0 0 3mm; }}
p {{ margin: 0 0 3.2mm; }}
.subtitle {{ font-size: 13pt; color: {COLORS["muted"]}; max-width: 165mm; }}
.notice {{ border-left: 4px solid {COLORS["accent"]}; background: #fff4ee; padding: 3mm 4mm; margin: 5mm 0; }}
.source-line {{ color: {COLORS["muted"]}; font-size: 8.8pt; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; margin: 6mm 0; }}
.metric-card {{ background: {COLORS["surface"]}; border: 1px solid {COLORS["line"]}; border-radius: 5px; padding: 4mm; min-height: 27mm; }}
.metric-label {{ color: {COLORS["muted"]}; font-size: 8pt; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }}
.metric-value {{ font-size: 20pt; font-weight: 800; margin: .7mm 0; }}
.metric-note {{ color: {COLORS["muted"]}; font-size: 8.5pt; }}
.split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; align-items: start; }}
.thirds {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; }}
.panel {{ background: {COLORS["surface"]}; border: 1px solid {COLORS["line"]}; border-radius: 5px; padding: 4mm; margin: 0 0 4mm; break-inside: avoid; }}
.compact {{ padding: 3mm; }}
ul {{ margin: 1mm 0 0 5mm; padding-left: 4mm; }}
li {{ margin-bottom: 1.8mm; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; font-size: 8.5pt; }}
th {{ text-align: left; color: {COLORS["muted"]}; border-bottom: 1px solid {COLORS["line"]}; font-size: 7.5pt; text-transform: uppercase; letter-spacing: .035em; padding: 2mm; }}
td {{ border-bottom: 1px solid #eef2f6; padding: 1.8mm 2mm; vertical-align: top; }}
td:nth-child(n+2), th:nth-child(n+2) {{ text-align: right; }}
.left-table td:nth-child(1), .left-table th:nth-child(1), .left-table td:nth-child(2), .left-table th:nth-child(2) {{ text-align: left; }}
.text-table td, .text-table th {{ text-align: left !important; }}
.method-step {{ display: grid; grid-template-columns: 11mm 1fr; gap: 3mm; margin-bottom: 3mm; }}
.step-num {{ width: 9mm; height: 9mm; border-radius: 50%; background: {COLORS["ink"]}; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 8pt; font-weight: 800; }}
.muted {{ color: {COLORS["muted"]}; }}
.stacked-bar {{ height: 13mm; display: flex; overflow: hidden; border-radius: 5px; border: 1px solid {COLORS["line"]}; background: #edf2f6; margin: 3mm 0 2mm; }}
.legend {{ display: flex; gap: 4mm; flex-wrap: wrap; color: {COLORS["muted"]}; font-size: 8.3pt; }}
.legend i {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }}
.reference {{ font-size: 8.8pt; color: {COLORS["muted"]}; overflow-wrap: anywhere; }}
.quote-box {{ border-top: 3px solid {COLORS["gold"]}; padding-top: 3mm; }}
@media screen {{
    body {{ background: #e8edf2; padding: 18px 0 36px; }}
    .page {{ width: min(210mm, calc(100% - 32px)); min-height: 297mm; margin: 24px auto; padding: 16mm 15mm; background: {COLORS["paper"]}; border: 1px solid #d4dce6; border-radius: 6px; box-shadow: 0 18px 55px rgba(23,33,43,.13); page-break-after: auto; }}
}}
@media screen and (max-width: 760px) {{
    .page {{ width: calc(100% - 20px); min-height: auto; padding: 8mm 5mm; }}
    .metric-grid, .split, .thirds {{ grid-template-columns: 1fr; }}
    h1 {{ font-size: 28pt; }}
}}
</style>
</head>
<body>
<section class="page cover">
    <div>
        <div class="band"></div>
        <div class="kicker">Phase 1.1 Consolidated Work Report</div>
        <h1>District Baseline<br>Research Methodology</h1>
        <p class="subtitle">A work report documenting the goal, source authority, cleanup decisions, validation gates, discovery protocol, deduplication logic, and research limitations behind the district-only Shiva temple discovery baseline.</p>
        <div class="notice"><strong>Boundary statement:</strong> this is a discovery baseline built from official district data and Google Places observations. It is not an exact count of all Shiva temples and not an official temple census.</div>
    </div>
    <div>
        <div class="metric-grid">
            {_metric_card("Active LGD Districts", _fmt_int(data.active_districts), "District-only administrative baseline")}
            {_metric_card("Search Tasks", _fmt_int(total_tasks), f"{len(PHASE1_KEYWORDS)} Shiva-related queries per district")}
            {_metric_card("Unique Candidates", _fmt_int(unique), "Current district-attributed Google Place IDs")}
        </div>
        <p class="source-line">Generated: {escape(generated_label)} | Report status: {escape(summary.get("status", ""))}</p>
    </div>
</section>

<section class="page">
    <h2>1. Goal And Research Frame</h2>
    <div class="panel">
        <h3>Goal Of Phase 1.1</h3>
        <p>Phase 1.1 establishes a clean, national, district-level discovery baseline for likely Shiva temple candidates in India. The purpose is to create a comparable administrative starting point before adding towns, urban local bodies, sub-districts, or villages.</p>
        <p>The working research question is: <strong>using official district geography and a bounded Google Places discovery protocol, where do Shiva-related temple candidates appear, and how strong is the name-based Shiva signal?</strong></p>
    </div>
    <div class="metric-grid">
        {_metric_card("Prepared LGD Rows", _fmt_int(data.prepared_lgd_districts), "Normalized from LGD district source")}
        {_metric_card("Districts With LGD Codes", _fmt_int(data.active_districts_with_lgd_code), "Active district rows carrying LGD district code")}
        {_metric_card("Inactive Audit Rows", _fmt_int(data.inactive_districts), "Retained for history, excluded from Phase 1.1")}
    </div>
    <div class="split">
        <div class="panel quote-box">
            <h3>Why District-Only First</h3>
            <ul>
                <li>Districts are official, recognizable units for research and government communication.</li>
                <li>A district layer prevents early mixing of towns, ULBs, tehsils, villages, and legacy pilot rows.</li>
                <li>The task volume is controlled: {escape(str(data.active_districts))} districts times {len(PHASE1_KEYWORDS)} keywords.</li>
                <li>It creates a national benchmark before deeper local expansion.</li>
            </ul>
        </div>
        <div class="panel quote-box">
            <h3>What This Work Can Support</h3>
            <ul>
                <li>District-level prioritization for manual review.</li>
                <li>Evidence packs for academic or government conversations.</li>
                <li>A repeatable pipeline for later location layers.</li>
                <li>An audit trail for administrative naming decisions.</li>
            </ul>
        </div>
    </div>
</section>

<section class="page">
    <h2>2. Source Authority</h2>
    <div class="panel">
        <h3>Source Of Truth Decisions</h3>
        {_table(
            ["Entity", "Phase 1.1 Source", "How It Was Treated"],
            [
                ["District names and codes", "Data.gov.in LGD district data from Ministry of Panchayati Raj", "Administrative source of truth for district rows and LGD district codes."],
                ["Location hierarchy", "LGD district/state columns", "Normalized into india_locations with active district scope."],
                ["Temple candidate names", "Google Places displayName", "Discovery observation only, not canonical temple name truth."],
                ["Unique candidate identity", "Google Place ID", "Operational dedupe key for API results."],
                ["Shiva relevance", "Configured high and medium Shiva term lexicon", "Name-based confidence classification for triage and review."],
            ],
            "text-table",
        )}
    </div>
    <div class="split">
        <div class="panel">
            <h3>District Names</h3>
            <p>The district layer uses Local Government Directory data as the administrative reference. The Ministry of Panchayati Raj describes LGD as a directory for land/revenue regions and local governments, with unique LGD codes assigned to government bodies and administrative entities.</p>
            <p class="reference">{escape(MOPR_LGD_URL)}</p>
        </div>
        <div class="panel">
            <h3>Temple Names</h3>
            <p>There is no final temple-name source of truth in Phase 1.1. Google Places names are treated as discovered field signals. A future verification phase should triangulate candidates against temple trusts, state religious/endowment departments, gazetteers, tourism boards, ASI/state archaeology sources, local records, and manual review.</p>
        </div>
    </div>
    <div class="panel">
        <h3>External Source Notes</h3>
        <ul>
            <li>Data.gov's LGD catalog is attributed to the Ministry of Panchayati Raj and is released through the Open Government Data platform. The catalog page observed on May 12, 2026 showed Published On 22/07/2022 and Updated On 10/05/2026.</li>
            <li>Google Places Text Search returns place objects based on a text query and selected field mask. The API documentation notes that result lists are not guaranteed to be identical for repeated requests and that pagination is bounded.</li>
        </ul>
    </div>
</section>

<section class="page">
    <h2>3. Data Cleanup And Validation</h2>
    <div class="panel">
        <h3>Administrative Baseline Workflow</h3>
        <div class="method-step"><div class="step-num">1</div><div><strong>Normalize LGD file.</strong><br><span class="muted">CSV headers and codes were mapped into the project's standard location schema.</span></div></div>
        <div class="method-step"><div class="step-num">2</div><div><strong>Compare LGD to database.</strong><br><span class="muted">Districts were compared by LGD code, exact normalized name, canonical name, and high-similarity fuzzy match within the same state.</span></div></div>
        <div class="method-step"><div class="step-num">3</div><div><strong>Resolve naming differences.</strong><br><span class="muted">Known administrative spelling and rename variants were captured as canonical aliases, then rechecked.</span></div></div>
        <div class="method-step"><div class="step-num">4</div><div><strong>Handle manual exceptions.</strong><br><span class="muted">Bajali and Tamulpur were inserted from LGD. Itanagar Capital Complex was retained inactive as a pilot/audit row outside the LGD district baseline.</span></div></div>
        <div class="method-step"><div class="step-num">5</div><div><strong>Lock Phase 1.1 scope.</strong><br><span class="muted">Only active district rows were used for task generation and scoped reporting.</span></div></div>
    </div>
    <div class="panel">
        <h3>Alignment Funnel</h3>
        {_table(["Validation pass", "Auto", "Review", "Missing in DB", "DB only"], alignment_rows)}
    </div>
    <div class="thirds">
        {_status_table("Initial Review", data.first_alignment_status)}
        {_status_table("After Aliases", data.alias_alignment_status)}
        {_status_table("Final Review", data.final_alignment_status)}
    </div>
</section>

<section class="page">
    <h2>4. Discovery Protocol</h2>
    <div class="split">
        <div class="panel">
            <h3>Search Design</h3>
            <ul>
                <li>Each active district received the same keyword set for comparability.</li>
                <li>Queries used the pattern: <strong>keyword in district, state, India</strong>.</li>
                <li>The run used Google Places Text Search with <strong>includedType: hindu_temple</strong>, <strong>strictTypeFiltering: true</strong>, <strong>regionCode: IN</strong>, and <strong>languageCode: en</strong>.</li>
                <li>Fields were limited to the needed result attributes, including ID, display name, address, location, type, and Maps URI.</li>
            </ul>
        </div>
        <div class="panel">
            <h3>Keyword Set</h3>
            {_table(["Keyword"], [[keyword] for keyword in PHASE1_KEYWORDS], "left-table")}
        </div>
    </div>
    <div class="metric-grid">
        {_metric_card("Done Tasks", _fmt_int(done_tasks), f"{_fmt_pct(_pct(done_tasks, total_tasks))} of district tasks")}
        {_metric_card("Failed Tasks", _fmt_int(failed_tasks), "Retained for audit and rerun")}
        {_metric_card("Raw Occurrences", _fmt_int(total), "Sum of completed district task result counts")}
    </div>
    <div class="panel">
        <h3>Task Completion</h3>
        {task_bar}
    </div>
</section>

<section class="page">
    <h2>5. Deduplication And Classification</h2>
    <div class="split">
        <div class="panel">
            <h3>Dedupe Method</h3>
            <p>Within each API response, repeated Google Place IDs were collapsed. During database writes, candidates were upserted by <strong>google_place_id</strong>, so rediscovery through another query updated the same candidate instead of creating a second candidate row.</p>
            <p>This is an operational dedupe method. It avoids repeated API hits becoming repeated candidate records, but it does not prove canonical cultural identity where Google itself has split or merged place records.</p>
        </div>
        <div class="panel">
            <h3>Classification Method</h3>
            <p>Candidate confidence is based on the discovered name only. High-confidence terms include direct Shiva variants such as Shiva, Shiv, Mahadev, Vishwanath, Somnath, Kedarnath, Omkareshwar, Lingeshwar, linga, and lingam. Medium-confidence terms include Shankar, Ishwar/Eshwar, Nath, Rudra, Someshwar, and Bholenath.</p>
            <p>Low confidence means no configured Shiva-specific term matched the discovered name. It does not mean the candidate is not a Shiva temple.</p>
        </div>
    </div>
    <div class="metric-grid">
        {_metric_card("Unique Place IDs", _fmt_int(unique), "Deduped current district-attributed candidates")}
        {_metric_card("Duplicates Removed", _fmt_int(duplicates), f"{_fmt_pct(_pct(duplicates, total))} of raw occurrences")}
        {_metric_card("High + Medium Signal", _fmt_int(signal), f"{_fmt_pct(_pct(signal, unique))} of unique candidates")}
    </div>
    <div class="panel">
        <h3>Confidence Mix</h3>
        {confidence_bar}
    </div>
</section>

<section class="page">
    <h2>6. Research Findings Snapshot</h2>
    <div class="split">
        <div class="panel">
            <h3>Top States By Unique Candidate Volume</h3>
            {_table(["State / UT", "Unique", "High", "High+Medium Share"], _rank_rows(data.top_states))}
        </div>
        <div class="panel">
            <h3>Top Districts By Unique Candidate Volume</h3>
            {_table(["State", "District", "Unique", "High", "High+Medium Share"], _rank_rows(data.top_districts, district=True), "left-table")}
        </div>
    </div>
    <div class="panel">
        <h3>Keyword Signal In Candidate Rows</h3>
        {_table(["Latest source keyword", "Candidate rows", "Share"], _keyword_rows(data.keyword_counts))}
        <p class="muted">Keyword signal is based on each candidate row's latest stored source query. It is useful for triage, but not a full attribution history across every rediscovery.</p>
    </div>
</section>

<section class="page">
    <h2>7. Challenges And Research Controls</h2>
    <div class="split">
        <div class="panel">
            <h3>Challenges Encountered</h3>
            <ul>
                <li>Some downloaded files were not what their filenames suggested. One "towns" file was actually Uttar Pradesh sub-district data.</li>
                <li>LGD local body data was valuable, but mixing it into Phase 1.1 would have blurred the district baseline.</li>
                <li>Administrative names vary across sources: spelling variants, renames, parenthetical labels, and legacy district names needed careful alignment.</li>
                <li>Two Assam districts were present in LGD but missing in the database, while one Arunachal pilot row sat outside the LGD district baseline.</li>
                <li>Google Places returns discovery evidence, not a canonical temple registry, so counts must remain uncertainty-aware.</li>
                <li>Repeated discoveries across keywords created heavy duplication, making stable place-ID dedupe essential.</li>
            </ul>
        </div>
        <div class="panel">
            <h3>Controls Applied</h3>
            <ul>
                <li>Phase 1.1 was explicitly restricted to active district rows.</li>
                <li>LGD district codes were preserved as administrative identifiers.</li>
                <li>Alignment output was written to review CSVs before applying changes.</li>
                <li>Manual exceptions were documented and retained in the audit trail.</li>
                <li>Google Places calls used bounded limits and a narrow field mask.</li>
                <li>Reports state discovery counts rather than final real-world temple counts.</li>
            </ul>
        </div>
    </div>
    <div class="panel">
        <h3>Known Limitations</h3>
        <ul>
            <li>Candidate names are Google Places display names, not verified canonical temple names.</li>
            <li>Some real temples may not be in Google Places, may be typed differently, or may not match the selected keywords.</li>
            <li>Some candidates may be non-Shiva temples whose names contain overlapping terms, or Shiva temples whose names do not contain configured terms.</li>
            <li>The report filters candidates by current source_location_id. A future candidate-discovery history table is needed for complete multi-query attribution.</li>
        </ul>
    </div>
</section>

<section class="page">
    <h2>8. Path Forward</h2>
    <div class="panel">
        <h3>Immediate Next Research Steps</h3>
        <ul>
            <li>Rerun or inspect the one failed district task and document the outcome.</li>
            <li>Sample high, medium, and low confidence candidates across top and low-volume districts.</li>
            <li>Add a candidate discovery history table to retain every query-to-place observation.</li>
            <li>Create a manual review protocol with fields for canonical name, deity verification, source URL, verifier, and confidence notes.</li>
            <li>Keep Phase 1.2 town and ULB expansion as a separate scoped report, not mixed into Phase 1.1.</li>
        </ul>
    </div>
    <div class="panel">
        <h3>Suggested External Positioning</h3>
        <p><strong>Use:</strong> An uncertainty-aware district-level discovery baseline of likely Shiva temple candidates in India, generated from official Indian district data and Google Places discovery results.</p>
        <p><strong>Avoid:</strong> exact number of Shiva temples, official census of temples, complete temple database.</p>
    </div>
    <div class="panel">
        <h3>References</h3>
        <p class="reference">Data.gov.in LGD catalog: {escape(LGD_CATALOG_URL)}</p>
        <p class="reference">Ministry of Panchayati Raj LGD overview: {escape(MOPR_LGD_URL)}</p>
        <p class="reference">Google Places Text Search documentation: {escape(GOOGLE_TEXT_SEARCH_URL)}</p>
        <p class="reference">Local project evidence: data/prepared_locations_lgd_districts.csv, reports/location_verification/*.csv, reports/phase_1_1_district_baseline/*.csv.</p>
    </div>
</section>
</body>
</html>"""


def _find_chrome() -> Path | None:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def write_pdf_with_chrome(html_path: Path, pdf_path: Path) -> bool:
    chrome = _find_chrome()
    if not chrome:
        return False

    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path.resolve()}",
            html_path.resolve().as_uri(),
        ],
        check=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Phase 1.1 research-style work report as HTML and PDF."
    )
    parser.add_argument(
        "--report-dir",
        default="reports/phase_1_1_district_baseline",
        help="Directory containing the Phase 1.1 district-only CSV reports.",
    )
    parser.add_argument(
        "--prepared-districts",
        default="data/prepared_locations_lgd_districts.csv",
        help="Prepared LGD districts CSV used for the baseline.",
    )
    parser.add_argument(
        "--verification-dir",
        default="reports/location_verification",
        help="Directory containing district alignment review CSVs.",
    )
    parser.add_argument(
        "--html-output",
        default="reports/phase_1_1_district_baseline/phase_1_1_consolidated_work_report.html",
        help="HTML output path.",
    )
    parser.add_argument(
        "--pdf-output",
        default="reports/phase_1_1_district_baseline/phase_1_1_consolidated_work_report.pdf",
        help="PDF output path.",
    )
    args = parser.parse_args()

    data = load_report_data(
        report_dir=Path(args.report_dir),
        prepared_districts_path=Path(args.prepared_districts),
        verification_dir=Path(args.verification_dir),
    )

    html_path = Path(args.html_output)
    pdf_path = Path(args.pdf_output)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote {html_path}")

    if write_pdf_with_chrome(html_path, pdf_path):
        print(f"Wrote {pdf_path}")
    else:
        print("Chrome or Edge was not found; HTML report was generated but PDF was not.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
