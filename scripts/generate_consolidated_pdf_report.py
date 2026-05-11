from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
import subprocess


REPORT_FILES = {
    "national": "national_summary.csv",
    "states": "state_counts.csv",
    "districts": "district_counts.csv",
    "candidates": "candidate_review.csv",
}

CONFIDENCE_LABELS = {
    "high": "High confidence",
    "medium": "Medium confidence",
    "low": "Low confidence",
}

COLORS = {
    "ink": "#17212b",
    "muted": "#617085",
    "line": "#d9e0e8",
    "paper": "#fbfaf7",
    "surface": "#ffffff",
    "high": "#1f9d73",
    "medium": "#d18b12",
    "low": "#5969b2",
    "accent": "#c74f35",
    "gold": "#d6a63f",
}


@dataclass(frozen=True)
class ReportData:
    generated_at: datetime
    summary: dict[str, str]
    states: list[dict[str, object]]
    districts: list[dict[str, object]]
    candidate_rows: int
    keyword_counts: Counter[str]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _as_int(value: object) -> int:
    if value in (None, ""):
        return 0
    return int(str(value))


def _pct(numerator: int, denominator: int) -> float:
    return (numerator / denominator * 100) if denominator else 0.0


def _fmt_int(value: int | str | object) -> str:
    return f"{_as_int(value):,}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _to_int_rows(rows: list[dict[str, str]], text_keys: set[str]) -> list[dict[str, object]]:
    converted: list[dict[str, object]] = []
    for row in rows:
        converted.append(
            {
                key: value if key in text_keys else _as_int(value)
                for key, value in row.items()
            }
        )
    return converted


def _candidate_keyword_counts(path: Path) -> tuple[int, Counter[str]]:
    counts: Counter[str] = Counter()
    rows = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            query = row.get("source_query", "").strip()
            keyword = query.split(" in ", 1)[0].strip() if " in " in query else query
            if keyword:
                counts[keyword] += 1
    return rows, counts


def load_report_data(report_dir: Path) -> ReportData:
    for filename in REPORT_FILES.values():
        path = report_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing required non-sample report: {path}")

    national_rows = _read_csv(report_dir / REPORT_FILES["national"])
    if not national_rows:
        raise ValueError("national_summary.csv has no data rows.")

    candidate_rows, keyword_counts = _candidate_keyword_counts(
        report_dir / REPORT_FILES["candidates"]
    )

    return ReportData(
        generated_at=datetime.now(),
        summary=national_rows[0],
        states=_to_int_rows(_read_csv(report_dir / REPORT_FILES["states"]), {"state"}),
        districts=_to_int_rows(
            _read_csv(report_dir / REPORT_FILES["districts"]),
            {"state", "district"},
        ),
        candidate_rows=candidate_rows,
        keyword_counts=keyword_counts,
    )


def _signal(row: dict[str, object]) -> int:
    return _as_int(row["high_confidence_shiva"]) + _as_int(
        row["medium_confidence_shiva_candidates"]
    )


def _confidence_share(summary: dict[str, str]) -> dict[str, float]:
    unique = _as_int(summary["unique_google_place_ids"])
    return {
        "high": _pct(_as_int(summary["high_confidence_shiva"]), unique),
        "medium": _pct(_as_int(summary["medium_confidence_shiva_candidates"]), unique),
        "low": _pct(_as_int(summary["low_confidence_possible_temples"]), unique),
    }


def _bar_chart(
    rows: list[dict[str, object]],
    *,
    label_keys: tuple[str, ...],
    value_key: str,
    color: str,
    max_rows: int = 12,
    width: int = 760,
) -> str:
    rows = rows[:max_rows]
    if not rows:
        return ""

    left = 190
    right = 80
    row_h = 30
    top = 8
    chart_w = width - left - right
    height = top * 2 + len(rows) * row_h
    max_value = max(_as_int(row[value_key]) for row in rows) or 1

    parts = [
        f'<svg class="chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">'
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        label = ", ".join(str(row[key]) for key in label_keys if row.get(key))
        value = _as_int(row[value_key])
        bar_w = max(2, int(chart_w * value / max_value))
        parts.append(
            f'<text x="0" y="{y + 18}" class="chart-label">{escape(label[:40])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{chart_w}" height="14" rx="7" class="bar-bg" />'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{bar_w}" height="14" rx="7" fill="{color}" />'
        )
        parts.append(
            f'<text x="{left + chart_w + 12}" y="{y + 18}" class="chart-value">{_fmt_int(value)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _stacked_chart(
    rows: list[dict[str, object]],
    *,
    label_keys: tuple[str, ...],
    max_rows: int = 12,
    width: int = 760,
) -> str:
    rows = rows[:max_rows]
    if not rows:
        return ""

    left = 190
    right = 80
    row_h = 31
    top = 8
    chart_w = width - left - right
    height = top * 2 + len(rows) * row_h
    max_value = max(_as_int(row["unique_google_place_ids"]) for row in rows) or 1
    keys = (
        ("high_confidence_shiva", COLORS["high"]),
        ("medium_confidence_shiva_candidates", COLORS["medium"]),
        ("low_confidence_possible_temples", COLORS["low"]),
    )

    parts = [
        f'<svg class="chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">'
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        label = ", ".join(str(row[key]) for key in label_keys if row.get(key))
        total = _as_int(row["unique_google_place_ids"])
        x = left
        parts.append(
            f'<text x="0" y="{y + 18}" class="chart-label">{escape(label[:40])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{chart_w}" height="15" rx="7.5" class="bar-bg" />'
        )
        for key, color in keys:
            value = _as_int(row[key])
            seg_w = int(chart_w * value / max_value)
            if value and seg_w < 2:
                seg_w = 2
            if seg_w:
                parts.append(
                    f'<rect x="{x}" y="{y + 5}" width="{seg_w}" height="15" fill="{color}" />'
                )
            x += seg_w
        parts.append(
            f'<text x="{left + chart_w + 12}" y="{y + 18}" class="chart-value">{_fmt_int(total)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


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
    body_rows = []
    for row in rows:
        body = "".join(f"<td>{escape(str(value))}</td>" for value in row)
        body_rows.append(f"<tr>{body}</tr>")
    return f'<table class="{classes}"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'


def _keyword_rows(data: ReportData, limit: int = 9) -> list[dict[str, object]]:
    return [
        {"keyword": keyword, "count": count}
        for keyword, count in data.keyword_counts.most_common(limit)
    ]


def render_html(data: ReportData) -> str:
    summary = data.summary
    total = _as_int(summary["total_discovered_candidates"])
    unique = _as_int(summary["unique_google_place_ids"])
    duplicates = _as_int(summary["duplicates_removed"])
    high = _as_int(summary["high_confidence_shiva"])
    medium = _as_int(summary["medium_confidence_shiva_candidates"])
    low = _as_int(summary["low_confidence_possible_temples"])
    signal = high + medium
    duplicate_rate = _pct(duplicates, total)
    signal_share = _pct(signal, unique)
    shares = _confidence_share(summary)

    states_by_unique = sorted(
        data.states,
        key=lambda row: _as_int(row["unique_google_place_ids"]),
        reverse=True,
    )
    states_by_high = sorted(
        data.states,
        key=lambda row: _as_int(row["high_confidence_shiva"]),
        reverse=True,
    )
    districts_by_unique = sorted(
        data.districts,
        key=lambda row: _as_int(row["unique_google_place_ids"]),
        reverse=True,
    )
    districts_by_high = sorted(
        data.districts,
        key=lambda row: _as_int(row["high_confidence_shiva"]),
        reverse=True,
    )

    top5_state_total = sum(
        _as_int(row["unique_google_place_ids"]) for row in states_by_unique[:5]
    )
    top10_state_total = sum(
        _as_int(row["unique_google_place_ids"]) for row in states_by_unique[:10]
    )
    top5_state_share = _pct(top5_state_total, unique)
    top10_state_share = _pct(top10_state_total, unique)

    keyword_rows = _keyword_rows(data)
    keyword_chart_rows = [
        {"keyword": row["keyword"], "count": row["count"]} for row in keyword_rows
    ]

    state_table_rows = []
    for row in states_by_unique[:15]:
        row_total = _as_int(row["unique_google_place_ids"])
        row_signal = _signal(row)
        state_table_rows.append(
            [
                row["state"],
                _fmt_int(row_total),
                _fmt_int(row["high_confidence_shiva"]),
                _fmt_int(row["medium_confidence_shiva_candidates"]),
                _fmt_pct(_pct(row_signal, row_total)),
            ]
        )

    district_table_rows = []
    for row in districts_by_unique[:18]:
        row_total = _as_int(row["unique_google_place_ids"])
        row_signal = _signal(row)
        district_table_rows.append(
            [
                row["state"],
                row["district"],
                _fmt_int(row_total),
                _fmt_int(row["high_confidence_shiva"]),
                _fmt_pct(_pct(row_signal, row_total)),
            ]
        )

    high_district_rows = []
    for row in districts_by_high[:15]:
        row_total = _as_int(row["unique_google_place_ids"])
        high_district_rows.append(
            [
                row["state"],
                row["district"],
                _fmt_int(row["high_confidence_shiva"]),
                _fmt_pct(_pct(_as_int(row["high_confidence_shiva"]), row_total)),
                _fmt_int(row_total),
            ]
        )

    keyword_table_rows = [
        [row["keyword"], _fmt_int(row["count"]), _fmt_pct(_pct(row["count"], unique))]
        for row in keyword_rows
    ]

    generated_label = data.generated_at.strftime("%B %d, %Y %I:%M %p")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Phase 1 Shiva Temple Discovery Consolidated Report</title>
<style>
@page {{ size: A4; margin: 16mm 15mm; }}
* {{ box-sizing: border-box; }}
html {{ color: {COLORS["ink"]}; font-family: Arial, Helvetica, sans-serif; }}
body {{ margin: 0; background: {COLORS["paper"]}; font-size: 10.2pt; line-height: 1.44; }}
.page {{ page-break-after: always; min-height: 245mm; padding: 0; }}
.page:last-child {{ page-break-after: auto; }}
.cover {{ display: flex; flex-direction: column; justify-content: space-between; min-height: 265mm; }}
.kicker {{ color: {COLORS["accent"]}; font-size: 10pt; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }}
h1 {{ font-size: 36pt; line-height: 1.02; margin: 15mm 0 5mm; letter-spacing: 0; }}
h2 {{ font-size: 18pt; margin: 0 0 5mm; letter-spacing: 0; }}
h3 {{ font-size: 12pt; margin: 8mm 0 3mm; letter-spacing: 0; }}
p {{ margin: 0 0 3.4mm; }}
.subtitle {{ font-size: 13pt; max-width: 150mm; color: {COLORS["muted"]}; }}
.notice {{ border-left: 4px solid {COLORS["accent"]}; padding: 3mm 4mm; background: #fff5ee; color: #5a2a1f; margin: 5mm 0; }}
.source-line {{ color: {COLORS["muted"]}; font-size: 9.4pt; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; margin: 7mm 0 5mm; }}
.metric-card {{ background: {COLORS["surface"]}; border: 1px solid {COLORS["line"]}; border-radius: 5px; padding: 4mm; min-height: 29mm; }}
.metric-label {{ color: {COLORS["muted"]}; font-size: 8.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; }}
.metric-value {{ font-size: 21pt; font-weight: 800; margin: 1mm 0; letter-spacing: 0; }}
.metric-note {{ color: {COLORS["muted"]}; font-size: 8.7pt; }}
.split {{ display: grid; grid-template-columns: 1.05fr .95fr; gap: 7mm; align-items: start; }}
.panel {{ background: {COLORS["surface"]}; border: 1px solid {COLORS["line"]}; border-radius: 5px; padding: 5mm; margin: 0 0 5mm; }}
.panel h3 {{ margin-top: 0; }}
.keep-together {{ break-inside: avoid; page-break-inside: avoid; }}
.callout {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin: 4mm 0; }}
.callout div {{ border-top: 3px solid {COLORS["gold"]}; background: #fff; padding: 3mm; }}
.big-number {{ font-size: 17pt; font-weight: 800; }}
.muted {{ color: {COLORS["muted"]}; }}
.legend {{ display: flex; gap: 5mm; flex-wrap: wrap; margin: 2mm 0 4mm; color: {COLORS["muted"]}; font-size: 8.8pt; }}
.legend span::before {{ content: ""; display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 5px; vertical-align: -1px; background: var(--c); }}
.stacked-total {{ display: grid; grid-template-columns: {_fmt_pct(shares["high"])} {_fmt_pct(shares["medium"])} {_fmt_pct(shares["low"])}; width: 100%; height: 16mm; border-radius: 6px; overflow: hidden; border: 1px solid {COLORS["line"]}; margin: 4mm 0; }}
.stack-high {{ background: {COLORS["high"]}; }}
.stack-medium {{ background: {COLORS["medium"]}; }}
.stack-low {{ background: {COLORS["low"]}; }}
.chart {{ width: 100%; max-width: 100%; height: auto; }}
.chart-label {{ font-size: 10px; fill: {COLORS["ink"]}; }}
.chart-value {{ font-size: 10px; fill: {COLORS["muted"]}; font-weight: 700; }}
.bar-bg {{ fill: #edf1f5; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; font-size: 8.8pt; }}
th {{ text-align: left; color: {COLORS["muted"]}; font-size: 7.8pt; text-transform: uppercase; letter-spacing: .04em; border-bottom: 1px solid {COLORS["line"]}; padding: 2.2mm 2mm; }}
td {{ border-bottom: 1px solid #edf1f5; padding: 2mm; vertical-align: top; }}
td:nth-child(n+2):not(:first-child), th:nth-child(n+2):not(:first-child) {{ text-align: right; }}
.district-table td:nth-child(1), .district-table td:nth-child(2), .district-table th:nth-child(1), .district-table th:nth-child(2) {{ text-align: left; }}
.keyword-table td:nth-child(1), .keyword-table th:nth-child(1) {{ text-align: left; }}
.footer-note {{ margin-top: 5mm; color: {COLORS["muted"]}; font-size: 8.8pt; }}
ul {{ margin: 2mm 0 0 5mm; padding: 0 0 0 4mm; }}
li {{ margin-bottom: 2mm; }}
.cover-band {{ height: 13mm; background: linear-gradient(90deg, {COLORS["accent"]}, {COLORS["gold"]} 45%, {COLORS["high"]}); border-radius: 8px; }}
@media screen {{
    body {{
        background: #e8edf2;
        padding: 18px 0 36px;
    }}
    .page {{
        width: min(210mm, calc(100% - 32px));
        min-height: 297mm;
        margin: 24px auto;
        padding: 16mm 15mm;
        background: {COLORS["paper"]};
        border: 1px solid #d4dce6;
        border-radius: 6px;
        box-shadow: 0 18px 55px rgba(23, 33, 43, 0.13);
        overflow: hidden;
        page-break-after: auto;
    }}
    .page:last-child {{
        margin-bottom: 0;
    }}
    .cover {{
        min-height: 297mm;
    }}
}}
@media screen and (max-width: 760px) {{
    body {{
        padding: 10px 0 24px;
    }}
    .page {{
        width: calc(100% - 20px);
        min-height: auto;
        padding: 8mm 5mm;
    }}
    .cover {{
        min-height: auto;
    }}
    .metric-grid,
    .split,
    .callout {{
        grid-template-columns: 1fr;
    }}
    h1 {{
        font-size: 30pt;
    }}
}}
</style>
</head>
<body>
<section class="page cover">
    <div>
        <div class="cover-band"></div>
        <div class="kicker">Phase 1 Discovery Report</div>
        <h1>Shiva Temple Discovery<br>Consolidated Insights</h1>
        <p class="subtitle">A single report generated from the non-sample CSV exports in <strong>reports/</strong>, summarizing Google Places discovery output, deduplication, confidence classification, and geographic concentration.</p>
        <div class="notice"><strong>Important:</strong> these are discovery counts from Google Places API and name-based classification, not exact real-world temple counts or an official cultural census.</div>
    </div>
    <div>
        <div class="metric-grid">
            {_metric_card("Unique Google Place IDs", _fmt_int(unique), "Deduplicated candidate records")}
            {_metric_card("High-confidence Shiva", _fmt_int(high), f"{_fmt_pct(shares['high'])} of unique candidates")}
            {_metric_card("High + Medium Signal", _fmt_int(signal), f"{_fmt_pct(signal_share)} of unique candidates")}
        </div>
        <p class="source-line">Generated: {escape(generated_label)} | Source file status: {escape(summary.get("status", ""))}</p>
    </div>
</section>

<section class="page">
    <h2>Executive Summary</h2>
    <div class="metric-grid">
        {_metric_card("Discovered Occurrences", _fmt_int(total), "Raw result-count total from completed search tasks")}
        {_metric_card("Duplicates Removed", _fmt_int(duplicates), f"{_fmt_pct(duplicate_rate)} of discovered occurrences")}
        {_metric_card("Candidate Export Rows", _fmt_int(data.candidate_rows), "Rows in candidate_review.csv")}
        {_metric_card("States / UTs", _fmt_int(len(data.states)), "Rows in state_counts.csv")}
        {_metric_card("District Rows", _fmt_int(len(data.districts)), "Rows in district_counts.csv")}
        {_metric_card("Low-confidence Possible Temples", _fmt_int(low), f"{_fmt_pct(shares['low'])} of unique candidates")}
    </div>
    <div class="split">
        <div class="panel">
            <h3>What The Data Says</h3>
            <ul>
                <li>The pipeline reduced <strong>{_fmt_int(total)}</strong> discovered occurrences to <strong>{_fmt_int(unique)}</strong> unique Google Place IDs, which is a strong signal that cross-query deduplication is doing real work.</li>
                <li><strong>{_fmt_int(signal)}</strong> candidates are high or medium confidence by name classification, representing <strong>{_fmt_pct(signal_share)}</strong> of the unique candidate set.</li>
                <li>The top five states by unique discovered candidates account for <strong>{_fmt_pct(top5_state_share)}</strong> of the current candidate set; the top ten account for <strong>{_fmt_pct(top10_state_share)}</strong>.</li>
                <li><strong>{escape(str(states_by_unique[0]["state"]))}</strong> currently has the largest unique candidate volume, while <strong>{escape(str(states_by_high[0]["state"]))}</strong> has the largest high-confidence count.</li>
            </ul>
        </div>
        <div class="panel">
            <h3>Confidence Mix</h3>
            <div class="legend">
                <span style="--c: {COLORS['high']}">High {_fmt_pct(shares['high'])}</span>
                <span style="--c: {COLORS['medium']}">Medium {_fmt_pct(shares['medium'])}</span>
                <span style="--c: {COLORS['low']}">Low {_fmt_pct(shares['low'])}</span>
            </div>
            <div class="stacked-total"><div class="stack-high"></div><div class="stack-medium"></div><div class="stack-low"></div></div>
            <div class="callout">
                <div><span class="big-number">{_fmt_int(high)}</span><br><span class="muted">High-confidence names</span></div>
                <div><span class="big-number">{_fmt_int(medium)}</span><br><span class="muted">Medium-confidence names</span></div>
            </div>
            <p class="muted">Low confidence is a review queue, not a negative label. It means the candidate name did not match the configured Shiva terms strongly enough.</p>
        </div>
    </div>
</section>

<section class="page">
    <h2>State-Level Patterns</h2>
    <div class="panel keep-together">
        <h3>Top States By Unique Candidate Volume</h3>
        <div class="legend">
            <span style="--c: {COLORS['high']}">High</span>
            <span style="--c: {COLORS['medium']}">Medium</span>
            <span style="--c: {COLORS['low']}">Low</span>
        </div>
        {_stacked_chart(states_by_unique, label_keys=("state",), max_rows=12)}
    </div>
    <div class="panel keep-together">
        <h3>Top States By High-Confidence Candidates</h3>
        {_bar_chart(states_by_high, label_keys=("state",), value_key="high_confidence_shiva", color=COLORS["high"], max_rows=12)}
    </div>
</section>

<section class="page">
    <h3>State Ranking Detail</h3>
    {_table(["State / UT", "Unique", "High", "Medium", "High+Medium Share"], state_table_rows)}
</section>

<section class="page">
    <h2>District Hotspots</h2>
    <div class="panel keep-together">
        <h3>Top Districts By Unique Candidate Volume</h3>
        {_stacked_chart(districts_by_unique, label_keys=("state", "district"), max_rows=15)}
    </div>
</section>

<section class="page">
    <h2>District Hotspots</h2>
    <div class="panel keep-together">
        <h3>Top Districts By High-Confidence Candidates</h3>
        {_bar_chart(districts_by_high, label_keys=("state", "district"), value_key="high_confidence_shiva", color=COLORS["accent"], max_rows=15)}
    </div>
</section>

<section class="page">
    <h2>District Detail</h2>
    <h3>Highest Unique Candidate Volumes</h3>
    {_table(["State", "District", "Unique", "High", "High+Medium Share"], district_table_rows, "district-table")}
</section>

<section class="page">
    <h2>District Detail</h2>
    <h3>Highest High-Confidence Volumes</h3>
    {_table(["State", "District", "High", "High Share", "Unique"], high_district_rows, "district-table")}
</section>

<section class="page">
    <h2>Query Signal</h2>
    <div class="panel keep-together">
        <h3>Last Recorded Source Query Keywords</h3>
        {_bar_chart(keyword_chart_rows, label_keys=("keyword",), value_key="count", color=COLORS["gold"], max_rows=9)}
    </div>
    <div class="panel keep-together">
        <h3>How To Read This</h3>
        <p>The keyword distribution comes from <strong>candidate_review.csv</strong>. Because candidates are deduplicated by Google Place ID and rediscovery can update the stored source query, this is best read as the latest recorded query signal for unique candidate rows, not as full attribution across every API occurrence.</p>
        <p>The strongest keyword signals in this export are direct Shiva and Mahadev variants, followed by Shankar and other configured Phase 1 terms.</p>
    </div>
    {_table(["Keyword", "Candidate Rows", "Share Of Unique"], keyword_table_rows, "keyword-table")}
</section>

<section class="page">
    <h2>Interpretation Notes</h2>
    <div class="panel">
        <h3>What This Report Is Good For</h3>
        <ul>
            <li>Prioritizing states and districts for manual review.</li>
            <li>Spotting where duplicate discovery is heavy and deduplication is valuable.</li>
            <li>Understanding how much of the current candidate set has strong Shiva-name evidence.</li>
            <li>Choosing the next controlled Google Places discovery batches.</li>
        </ul>
    </div>
    <div class="panel">
        <h3>Limits And Caveats</h3>
        <ul>
            <li>Google Places is a discovery source only. The output should be verified with additional sources before publication.</li>
            <li>Confidence is based primarily on discovered names. A low-confidence row may still be a Shiva temple.</li>
            <li>Google Place IDs help deduplicate API results, but they do not prove cultural completeness or canonical temple identity.</li>
            <li>Counts can change when more search tasks are run, when Google updates Places data, or when classification terms are refined.</li>
        </ul>
    </div>
    <div class="panel">
        <h3>Suggested Next Moves</h3>
        <ul>
            <li>Review the highest-volume districts first, especially where high+medium share is strong.</li>
            <li>Sample low-confidence rows in high-volume states to improve classification terms.</li>
            <li>Run remaining pending search tasks in small batches and regenerate this PDF after each batch.</li>
            <li>Keep village-level expansion separate and intentional because it will rapidly increase task volume.</li>
        </ul>
    </div>
    <p class="footer-note">Input files: national_summary.csv, state_counts.csv, district_counts.csv, candidate_review.csv. Sample CSV files were intentionally excluded.</p>
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

    url = html_path.resolve().as_uri()
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path.resolve()}",
            url,
        ],
        check=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate one consolidated Phase 1 PDF report from non-sample CSV reports."
    )
    parser.add_argument("--report-dir", default="reports", help="Directory containing report CSVs.")
    parser.add_argument(
        "--html-output",
        default="reports/consolidated_phase1_discovery_report.html",
        help="HTML output path.",
    )
    parser.add_argument(
        "--pdf-output",
        default="reports/consolidated_phase1_discovery_report.pdf",
        help="PDF output path.",
    )
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    html_path = Path(args.html_output)
    pdf_path = Path(args.pdf_output)
    data = load_report_data(report_dir)
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
