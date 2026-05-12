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

CARD_SIZES = {
    "square": (1080, 1080),
    "linkedin": (1200, 627),
}


@dataclass(frozen=True)
class Card:
    slug: str
    kicker: str
    title: str
    body_html: str
    footer: str


@dataclass(frozen=True)
class SocialData:
    total_occurrences: int
    unique_places: int
    high: int
    medium: int
    low: int
    duplicates_removed: int
    active_districts: int
    active_district_codes: int
    done_tasks: int
    failed_tasks: int
    first_alignment: dict[str, int]
    alias_alignment: dict[str, int]
    final_alignment: dict[str, int]
    top_states: list[dict[str, str]]
    top_districts: list[dict[str, str]]
    generated_at: datetime


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


def _fetch_db_stats(fallback_districts: int) -> dict[str, int]:
    stats = {
        "active_districts": fallback_districts,
        "active_district_codes": fallback_districts,
        "done_tasks": fallback_districts * len(PHASE1_KEYWORDS),
        "failed_tasks": 0,
    }
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (
                            WHERE is_active = TRUE AND location_type = 'district'
                        ),
                        COUNT(*) FILTER (
                            WHERE is_active = TRUE
                              AND location_type = 'district'
                              AND district_lgd_code IS NOT NULL
                              AND district_lgd_code <> ''
                        )
                    FROM india_locations;
                    """
                )
                row = cursor.fetchone()
                stats["active_districts"] = int(row[0] or fallback_districts)
                stats["active_district_codes"] = int(row[1] or fallback_districts)

                cursor.execute(
                    """
                    SELECT task.status, COUNT(*)
                    FROM temple_search_tasks AS task
                    JOIN india_locations AS loc ON loc.id = task.location_id
                    WHERE loc.location_type = 'district'
                      AND loc.is_active = TRUE
                    GROUP BY task.status;
                    """
                )
                statuses = {str(status): int(count or 0) for status, count in cursor.fetchall()}
                stats["done_tasks"] = statuses.get("done", stats["done_tasks"])
                stats["failed_tasks"] = statuses.get("failed", 0)
    except Exception as exc:  # pragma: no cover - cards can be built from CSVs alone
        print(f"Database stats unavailable; using CSV fallback where possible: {exc}")
    return stats


def load_social_data(
    *,
    report_dir: Path,
    prepared_districts: Path,
    verification_dir: Path,
) -> SocialData:
    summary_rows = _read_csv(report_dir / "national_summary.csv")
    if not summary_rows:
        raise ValueError("national_summary.csv has no data rows.")
    summary = summary_rows[0]
    prepared_count = len(_read_csv(prepared_districts))
    db_stats = _fetch_db_stats(prepared_count)

    state_rows = sorted(
        _read_csv(report_dir / "state_counts.csv"),
        key=lambda row: _as_int(row.get("unique_google_place_ids")),
        reverse=True,
    )
    district_rows = sorted(
        _read_csv(report_dir / "district_counts.csv"),
        key=lambda row: _as_int(row.get("unique_google_place_ids")),
        reverse=True,
    )

    return SocialData(
        total_occurrences=_as_int(summary["total_discovered_candidates"]),
        unique_places=_as_int(summary["unique_google_place_ids"]),
        high=_as_int(summary["high_confidence_shiva"]),
        medium=_as_int(summary["medium_confidence_shiva_candidates"]),
        low=_as_int(summary["low_confidence_possible_temples"]),
        duplicates_removed=_as_int(summary["duplicates_removed"]),
        active_districts=db_stats["active_districts"],
        active_district_codes=db_stats["active_district_codes"],
        done_tasks=db_stats["done_tasks"],
        failed_tasks=db_stats["failed_tasks"],
        first_alignment=_group_status(verification_dir / "district_alignment_review.csv"),
        alias_alignment=_group_status(
            verification_dir / "district_alignment_review_after_aliases.csv"
        ),
        final_alignment=_group_status(
            verification_dir / "district_alignment_after_manual_exceptions.csv"
        ),
        top_states=state_rows[:6],
        top_districts=district_rows[:6],
        generated_at=datetime.now(),
    )


def metric(label: str, value: object, note: str = "") -> str:
    return f"""
        <div class="metric">
            <div class="metric-label">{escape(label)}</div>
            <div class="metric-value">{escape(str(value))}</div>
            <div class="metric-note">{escape(note)}</div>
        </div>
    """


def pill(label: str, value: object) -> str:
    return f'<div class="pill"><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>'


def flow_step(index: int, title: str, detail: str) -> str:
    return f"""
        <div class="flow-step">
            <div class="step-index">{index}</div>
            <div>
                <strong>{escape(title)}</strong>
                <span>{escape(detail)}</span>
            </div>
        </div>
    """


def bar_row(label: str, value: int, maximum: int, detail: str = "") -> str:
    width = max(2.0, _pct(value, maximum))
    return f"""
        <div class="bar-row">
            <div class="bar-label"><span>{escape(label)}</span><strong>{_fmt_int(value)}</strong></div>
            <div class="bar-track"><div class="bar-fill" style="width:{width:.3f}%"></div></div>
            <div class="bar-detail">{escape(detail)}</div>
        </div>
    """


def build_cards(data: SocialData) -> list[Card]:
    tasks_total = data.done_tasks + data.failed_tasks
    signal = data.high + data.medium
    duplicate_rate = _pct(data.duplicates_removed, data.total_occurrences)
    high_share = _pct(data.high, data.unique_places)
    medium_share = _pct(data.medium, data.unique_places)
    low_share = _pct(data.low, data.unique_places)
    max_state = max((_as_int(row["unique_google_place_ids"]) for row in data.top_states), default=1)
    max_district = max(
        (_as_int(row["unique_google_place_ids"]) for row in data.top_districts),
        default=1,
    )

    return [
        Card(
            slug="01_baseline_snapshot",
            kicker="Phase 1.1 | District Baseline",
            title="A district-first map of likely Shiva temple candidates",
            body_html=f"""
                <div class="metric-grid three">
                    {metric("Active LGD districts", _fmt_int(data.active_districts), "Official district layer")}
                    {metric("District search tasks", _fmt_int(tasks_total), "9 Shiva-related queries per district")}
                    {metric("Unique candidates", _fmt_int(data.unique_places), "Deduped Google Place IDs")}
                </div>
                <div class="statement">Built as a discovery baseline, not a final temple census.</div>
            """,
            footer="Source: LGD district data + Google Places discovery | India",
        ),
        Card(
            slug="02_methodology_pipeline",
            kicker="Methodology",
            title="From official districts to reviewable evidence",
            body_html=f"""
                <div class="flow-grid">
                    {flow_step(1, "LGD districts", "Use official district names and codes")}
                    {flow_step(2, "Normalize", "Clean headers, names, codes, and scope")}
                    {flow_step(3, "Align", "Match database rows to LGD with review gates")}
                    {flow_step(4, "Search", "Bounded Google Places Text Search")}
                    {flow_step(5, "Dedupe", "Collapse records by Google Place ID")}
                    {flow_step(6, "Classify", "High, medium, low Shiva-name signal")}
                </div>
            """,
            footer="Research design: comparable district-only baseline before town or village expansion",
        ),
        Card(
            slug="03_source_of_truth",
            kicker="Source Of Truth",
            title="Separate administrative truth from discovery evidence",
            body_html=f"""
                <div class="truth-grid">
                    {pill("District names", "LGD / Ministry of Panchayati Raj")}
                    {pill("Temple candidate names", "Google Places displayName")}
                    {pill("Dedupe key", "Google Place ID")}
                    {pill("Shiva confidence", "Configured name-term lexicon")}
                    {pill("Final verification", "Future manual and source triangulation")}
                </div>
                <div class="statement small">Google Places is used as a discovery source, not as the final cultural record.</div>
            """,
            footer="This wording keeps the research honest and government-readable",
        ),
        Card(
            slug="04_confidence_signal",
            kicker="Candidate Signal",
            title="What the district baseline found",
            body_html=f"""
                <div class="split">
                    <div class="signal-number">
                        <span>High + medium signal</span>
                        <strong>{_fmt_int(signal)}</strong>
                        <em>{_fmt_pct(_pct(signal, data.unique_places))} of unique candidates</em>
                    </div>
                    <div class="bars">
                        {bar_row("High confidence", data.high, data.unique_places, _fmt_pct(high_share))}
                        {bar_row("Medium confidence", data.medium, data.unique_places, _fmt_pct(medium_share))}
                        {bar_row("Low confidence", data.low, data.unique_places, _fmt_pct(low_share))}
                    </div>
                </div>
                <div class="statement small">Low confidence means review queue, not rejection.</div>
            """,
            footer=f"{_fmt_int(data.total_occurrences)} raw occurrences deduped to {_fmt_int(data.unique_places)} unique Place IDs",
        ),
        Card(
            slug="05_cleanup_validation",
            kicker="Data Cleanup",
            title="The validation funnel mattered",
            body_html=f"""
                <div class="funnel">
                    <div>
                        <span>Initial review</span>
                        <strong>{_fmt_int(data.first_alignment.get("auto", 0))} auto</strong>
                        <em>{_fmt_int(data.first_alignment.get("review", 0))} review | {_fmt_int(data.first_alignment.get("missing_in_db", 0))} missing | {_fmt_int(data.first_alignment.get("db_only", 0))} DB-only</em>
                    </div>
                    <div>
                        <span>After aliases</span>
                        <strong>{_fmt_int(data.alias_alignment.get("auto", 0))} auto</strong>
                        <em>{_fmt_int(data.alias_alignment.get("missing_in_db", 0))} missing | {_fmt_int(data.alias_alignment.get("db_only", 0))} DB-only</em>
                    </div>
                    <div>
                        <span>Final baseline</span>
                        <strong>{_fmt_int(data.final_alignment.get("auto", data.active_districts))} aligned</strong>
                        <em>Bajali and Tamulpur added | one pilot row made inactive</em>
                    </div>
                </div>
            """,
            footer=f"{_fmt_int(data.active_district_codes)} active district rows now carry LGD district codes",
        ),
        Card(
            slug="06_geographic_signal",
            kicker="Geographic Signal",
            title="Where review could start first",
            body_html=f"""
                <div class="geo-grid">
                    <div>
                        <h2>Top states</h2>
                        {"".join(bar_row(row["state"], _as_int(row["unique_google_place_ids"]), max_state, f'{_fmt_int(row["high_confidence_shiva"])} high') for row in data.top_states)}
                    </div>
                    <div>
                        <h2>Top districts</h2>
                        {"".join(bar_row(f'{row["district"]}, {row["state"]}', _as_int(row["unique_google_place_ids"]), max_district, f'{_fmt_int(row["high_confidence_shiva"])} high') for row in data.top_districts)}
                    </div>
                </div>
            """,
            footer="Use as prioritization signals for manual verification, not as final rankings",
        ),
    ]


def render_card_html(card: Card, *, width: int, height: int, size_name: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(card.title)}</title>
<style>
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; }}
body {{
    font-family: Arial, Helvetica, sans-serif;
    color: #17212b;
    background: #f6f3eb;
}}
.card {{
    width: {width}px;
    height: {height}px;
    padding: var(--pad);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background:
        linear-gradient(135deg, rgba(255,255,255,.95), rgba(251,250,247,.96)),
        radial-gradient(circle at 9% 12%, rgba(191,81,59,.14), transparent 28%),
        radial-gradient(circle at 92% 82%, rgba(33,138,106,.14), transparent 30%);
    border: 0;
    position: relative;
}}
.card::before {{
    content: "";
    position: absolute;
    left: var(--pad);
    right: var(--pad);
    top: var(--pad);
    height: 8px;
    border-radius: 999px;
    background: linear-gradient(90deg, #bf513b, #d7a23a, #218a6a, #4f6fa9);
}}
.content {{ position: relative; z-index: 1; padding-top: 24px; }}
.kicker {{
    color: #bf513b;
    font-size: var(--kicker);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .08em;
    margin-bottom: 18px;
}}
h1 {{
    font-size: var(--title);
    line-height: .98;
    letter-spacing: 0;
    max-width: 930px;
    margin: 0 0 var(--title-gap);
}}
.metric-grid {{ display: grid; gap: var(--gap); }}
.metric-grid.three {{ grid-template-columns: repeat(3, 1fr); }}
.metric {{
    background: #fff;
    border: 1px solid #dae2ea;
    border-radius: 14px;
    padding: var(--box-pad);
    min-height: var(--metric-min);
    box-shadow: 0 16px 36px rgba(23,33,43,.08);
}}
.metric-label {{
    color: #607085;
    font-size: var(--small);
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .05em;
}}
.metric-value {{
    font-size: var(--metric-value);
    font-weight: 900;
    margin: 6px 0 4px;
}}
.metric-note, .bar-detail, .flow-step span, .pill span, .funnel em, .signal-number em {{
    color: #607085;
    font-size: var(--small);
    font-style: normal;
}}
.statement {{
    margin-top: var(--gap);
    background: #fff4ee;
    border-left: 6px solid #bf513b;
    padding: var(--box-pad);
    border-radius: 12px;
    font-size: var(--statement);
    font-weight: 800;
}}
.statement.small {{ font-size: var(--body); font-weight: 700; }}
.flow-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--gap); }}
.flow-step {{
    display: grid;
    grid-template-columns: var(--step) 1fr;
    gap: 16px;
    align-items: center;
    background: #fff;
    border: 1px solid #dae2ea;
    border-radius: 14px;
    padding: var(--box-pad);
}}
.step-index {{
    width: var(--step);
    height: var(--step);
    border-radius: 50%;
    background: #17212b;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: var(--body);
}}
.flow-step strong {{ display: block; font-size: var(--body); margin-bottom: 4px; }}
.truth-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--gap); }}
.pill {{
    background: #fff;
    border: 1px solid #dae2ea;
    border-radius: 14px;
    padding: var(--box-pad);
}}
.pill span {{ display: block; text-transform: uppercase; font-weight: 800; letter-spacing: .05em; }}
.pill strong {{ display: block; font-size: var(--body); margin-top: 6px; }}
.split {{ display: grid; grid-template-columns: .9fr 1.1fr; gap: var(--gap); align-items: stretch; }}
.signal-number {{
    background: #17212b;
    color: #fff;
    border-radius: 16px;
    padding: var(--box-pad);
    display: flex;
    flex-direction: column;
    justify-content: center;
}}
.signal-number span {{ color: #d7a23a; font-size: var(--small); font-weight: 800; text-transform: uppercase; letter-spacing: .06em; }}
.signal-number strong {{ font-size: var(--hero-number); line-height: .95; margin: 10px 0; }}
.signal-number em {{ color: #dfe7ee; }}
.bars {{ display: grid; gap: 14px; }}
.bar-row {{ display: grid; gap: 7px; }}
.bar-label {{ display: flex; justify-content: space-between; gap: 16px; font-size: var(--small); font-weight: 800; }}
.bar-track {{ height: var(--bar); background: #e8edf2; border-radius: 999px; overflow: hidden; }}
.bar-fill {{ height: 100%; background: linear-gradient(90deg, #218a6a, #d7a23a); border-radius: 999px; }}
.funnel {{ display: grid; gap: var(--gap); }}
.funnel div {{
    background: #fff;
    border: 1px solid #dae2ea;
    border-left: 9px solid #4f6fa9;
    border-radius: 14px;
    padding: var(--box-pad);
}}
.funnel span {{ display: block; color: #607085; font-size: var(--small); font-weight: 800; text-transform: uppercase; letter-spacing: .05em; }}
.funnel strong {{ display: block; font-size: var(--metric-value); margin: 4px 0; }}
.funnel em {{ display: block; }}
.geo-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); }}
.geo-grid h2 {{ margin: 0 0 12px; font-size: var(--body); }}
.footer {{
    color: #607085;
    border-top: 1px solid #d9e1ea;
    padding-top: 14px;
    font-size: var(--footer);
    font-weight: 700;
}}
body.square {{
    --pad: 66px;
    --title: 72px;
    --title-gap: 46px;
    --kicker: 21px;
    --body: 25px;
    --small: 18px;
    --statement: 30px;
    --metric-value: 47px;
    --hero-number: 86px;
    --gap: 22px;
    --box-pad: 24px;
    --step: 50px;
    --bar: 18px;
    --metric-min: 174px;
    --footer: 18px;
}}
body.linkedin {{
    --pad: 44px;
    --title: 47px;
    --title-gap: 26px;
    --kicker: 15px;
    --body: 18px;
    --small: 13px;
    --statement: 22px;
    --metric-value: 34px;
    --hero-number: 63px;
    --gap: 15px;
    --box-pad: 17px;
    --step: 38px;
    --bar: 12px;
    --metric-min: 110px;
    --footer: 13px;
}}
body.linkedin h1 {{ max-width: 1030px; }}
body.linkedin .content {{ padding-top: 16px; }}
body.linkedin .flow-grid {{ grid-template-columns: repeat(3, 1fr); }}
body.linkedin .truth-grid {{ grid-template-columns: repeat(5, 1fr); }}
body.linkedin .metric-grid.three {{ grid-template-columns: repeat(3, 1fr); }}
body.linkedin .statement {{ margin-top: 15px; }}
body.linkedin .funnel {{ grid-template-columns: repeat(3, 1fr); }}
body.linkedin .geo-grid h2 {{ margin-bottom: 8px; }}
</style>
</head>
<body class="{escape(size_name)}">
<main class="card">
    <section class="content">
        <div class="kicker">{escape(card.kicker)}</div>
        <h1>{escape(card.title)}</h1>
        {card.body_html}
    </section>
    <footer class="footer">{escape(card.footer)}</footer>
</main>
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


def _write_png(chrome: Path, html_path: Path, png_path: Path, width: int, height: int) -> None:
    subprocess.run(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            f"--screenshot={png_path.resolve()}",
            "--virtual-time-budget=1000",
            html_path.resolve().as_uri(),
        ],
        check=True,
    )


def _write_gallery(output_dir: Path, png_paths: list[Path]) -> None:
    items = "\n".join(
        f'<figure><img src="{escape(path.name)}" alt="{escape(path.stem)}"><figcaption>{escape(path.name)}</figcaption></figure>'
        for path in png_paths
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Phase 1.1 Social Cards</title>
<style>
body {{ margin: 0; padding: 32px; background: #e8edf2; font-family: Arial, Helvetica, sans-serif; color: #17212b; }}
h1 {{ margin-top: 0; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }}
figure {{ margin: 0; background: #fff; padding: 12px; border-radius: 8px; border: 1px solid #d9e1ea; }}
img {{ width: 100%; height: auto; display: block; border-radius: 4px; }}
figcaption {{ margin-top: 8px; color: #607085; font-size: 13px; }}
</style>
</head>
<body>
<h1>Phase 1.1 Social Cards</h1>
<div class="grid">{items}</div>
</body>
</html>"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate shareable Phase 1.1 social infographic cards."
    )
    parser.add_argument(
        "--report-dir",
        default="reports/phase_1_1_district_baseline",
        help="Directory containing Phase 1.1 district-only CSV reports.",
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
        "--output-dir",
        default="reports/phase_1_1_district_baseline/social_cards",
        help="Directory for generated social card HTML and PNG files.",
    )
    parser.add_argument(
        "--size",
        choices=["all", *CARD_SIZES.keys()],
        default="all",
        help="Card size to render. Defaults to all.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_social_data(
        report_dir=Path(args.report_dir),
        prepared_districts=Path(args.prepared_districts),
        verification_dir=Path(args.verification_dir),
    )
    cards = build_cards(data)
    chrome = _find_chrome()
    if chrome is None:
        raise RuntimeError("Chrome or Edge was not found; cannot render PNG screenshots.")

    sizes = CARD_SIZES.keys() if args.size == "all" else [args.size]
    png_paths: list[Path] = []
    for size_name in sizes:
        width, height = CARD_SIZES[size_name]
        for card in cards:
            stem = f"{size_name}_{card.slug}"
            html_path = output_dir / f"{stem}.html"
            png_path = output_dir / f"{stem}.png"
            html_path.write_text(
                render_card_html(card, width=width, height=height, size_name=size_name),
                encoding="utf-8",
            )
            _write_png(chrome, html_path, png_path, width, height)
            png_paths.append(png_path)
            print(f"Wrote {png_path}")

    _write_gallery(output_dir, png_paths)
    print(f"Wrote {output_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
