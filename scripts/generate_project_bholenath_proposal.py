"""Generate the Project Bholenath proposal PDF.

The proposal is intentionally a Phase 1 discovery document. It describes
Google Places results as candidates and never as a verified temple census.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "project_bholenath_proposal_v0.1.pdf"

W, H = 960, 540

PAGE = HexColor("#FAF8F4")
SURFACE = HexColor("#FFFFFF")
SURFACE_MUTED = HexColor("#F3F4F7")
INDIGO = HexColor("#232B45")
INDIGO_2 = HexColor("#303A56")
INK = HexColor("#292D35")
MUTED = HexColor("#606979")
LINE = HexColor("#DFE2E8")
LINE_STRONG = HexColor("#C7CDD8")
ACCENT = HexColor("#B85118")
ACCENT_DARK = HexColor("#954113")
ACCENT_SOFT = HexColor("#FFF1E6")
ACCENT_LINE = HexColor("#E8C5AA")
NAV_TEXT = HexColor("#CCD2E1")
NAV_MUTED = HexColor("#ABB5CB")
GREEN = HexColor("#458168")
AMBER = HexColor("#CC9B47")
LOW = HexColor("#9DA8AC")


def register_fonts() -> None:
    base = Path("/System/Library/Fonts/Supplemental")
    pdfmetrics.registerFont(TTFont("Georgia", str(base / "Georgia.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Bold", str(base / "Georgia Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Georgia-Italic", str(base / "Georgia Italic.ttf")))


def para(
    c: canvas.Canvas,
    text: str,
    x: float,
    top: float,
    width: float,
    *,
    font: str = "Helvetica",
    size: float = 12,
    leading: float | None = None,
    color=INK,
    align: int = TA_LEFT,
    max_height: float = 200,
    bold_font: str | None = None,
) -> float:
    style = ParagraphStyle(
        "inline",
        fontName=font,
        fontSize=size,
        leading=leading or size * 1.25,
        textColor=color,
        alignment=align,
        spaceAfter=0,
        spaceBefore=0,
        allowWidows=0,
        allowOrphans=0,
    )
    if bold_font:
        style.boldFontName = bold_font
    p = Paragraph(text, style)
    _, ph = p.wrap(width, max_height)
    p.drawOn(c, x, top - ph)
    return ph


def label(c: canvas.Canvas, text: str, x: float, y: float, color=MUTED, size=7.5) -> None:
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text.upper())


def pill(c: canvas.Canvas, text: str, cx: float, y: float, dark: bool = False) -> None:
    width = max(72, pdfmetrics.stringWidth(text.upper(), "Helvetica-Bold", 6.5) + 24)
    c.setFillColor(INDIGO if not dark else INDIGO_2)
    c.roundRect(cx - width / 2, y, width, 19, 9.5, fill=1, stroke=0)
    c.setFillColor(SURFACE if not dark else NAV_TEXT)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(cx, y + 6.2, text.upper())


def header(c: canvas.Canvas, section: str, number: int, dark: bool = False) -> None:
    fg = NAV_TEXT if dark else INK
    line = HexColor("#3B435D") if dark else LINE
    c.setStrokeColor(line)
    c.setLineWidth(0.8)
    c.line(26, 504, W - 26, 504)
    c.setFillColor(ACCENT)
    c.circle(31, 520, 3, fill=1, stroke=0)
    c.setFillColor(fg)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(39, 522, "PROJECT")
    c.drawString(39, 514, "BHOLENATH")
    pill(c, section, W / 2, 511, dark=dark)
    c.setFont("Helvetica", 7)
    c.drawRightString(W - 28, 516, f"{number:02d}")


def footer(c: canvas.Canvas, text: str, dark: bool = False) -> None:
    fg = NAV_MUTED if dark else MUTED
    c.setFillColor(fg)
    c.setFont("Helvetica", 6.5)
    c.drawString(28, 18, text)
    c.drawRightString(W - 28, 18, "Project Bholenath / Proposal v0.1")


def page(c: canvas.Canvas, section: str, number: int, dark: bool = False, footer_text: str = "") -> None:
    c.setFillColor(INDIGO if dark else PAGE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    header(c, section, number, dark)
    footer(c, footer_text or section.title(), dark)


def line(c: canvas.Canvas, x1, y1, x2, y2, color=LINE_STRONG, width=1) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)


def card(c: canvas.Canvas, x, top, width, height, *, dark=False, fill=None, stroke=None, radius=10) -> None:
    c.setFillColor(fill or (INDIGO_2 if dark else SURFACE))
    c.setStrokeColor(stroke or (HexColor("#414A65") if dark else LINE_STRONG))
    c.setLineWidth(0.8)
    c.roundRect(x, top - height, width, height, radius, fill=1, stroke=1)


def metric(c, x, top, width, value, title, note, *, dark=False, accent=False):
    card(c, x, top, width, 93, dark=dark, fill=(ACCENT if accent else None), stroke=(ACCENT if accent else None))
    fg = SURFACE if (dark or accent) else INK
    sub = NAV_TEXT if dark else (SURFACE if accent else MUTED)
    c.setFillColor(fg)
    c.setFont("Georgia", 25)
    c.drawString(x + 15, top - 34, value)
    label(c, title, x + 15, top - 53, color=fg, size=7)
    para(c, note, x + 15, top - 65, width - 30, size=7.5, leading=9.2, color=sub, max_height=24)


def step_card(c, x, top, width, num, title, body, *, dark=False):
    card(c, x, top, width, 88, dark=dark)
    label(c, f"{num:02d} / {title}", x + 14, top - 18, color=ACCENT if not dark else HexColor("#F7BD79"), size=6.8)
    para(c, body, x + 14, top - 30, width - 28, size=9.4, leading=11.3, color=NAV_TEXT if dark else INK, max_height=48)


def arrow(c, x1, y1, x2, y2, color=LINE_STRONG):
    line(c, x1, y1, x2, y2, color=color, width=1)
    c.setFillColor(color)
    c.setStrokeColor(color)
    c.line(x2 - 5, y2 + 3, x2, y2)
    c.line(x2 - 5, y2 - 3, x2, y2)


def draw_cover(c: canvas.Canvas) -> None:
    c.setFillColor(INDIGO)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#3B435D"))
    c.setLineWidth(1)
    c.line(28, 438, W - 28, 438)
    c.line(28, 316, W - 28, 316)
    c.line(28, 188, W - 28, 188)

    c.setFillColor(NAV_TEXT)
    c.setFont("Georgia", 25)
    c.drawString(28, 475, "01")
    label(c, "Internal proposal / September 2026", W - 232, 489, color=NAV_MUTED, size=7)

    c.setFillColor(ACCENT)
    c.circle(33, 382, 4, fill=1, stroke=0)
    c.setFillColor(SURFACE)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(43, 385, "PROJECT")
    c.drawString(43, 376, "BHOLENATH")
    c.setFont("Georgia", 30)
    c.drawRightString(W - 28, 371, "2026")

    c.setFillColor(SURFACE)
    c.setFont("Georgia", 39)
    c.drawString(28, 266, "Shiva Temple Discovery")
    c.drawString(28, 221, "for India")
    c.setFillColor(ACCENT)
    c.rect(28, 203, 104, 4, fill=1, stroke=0)

    para(
        c,
        "A proposal for turning Indian location data and bounded place search into a transparent, reproducible pipeline of Shiva temple candidates for independent verification.",
        28,
        145,
        570,
        size=10.5,
        leading=14,
        color=NAV_TEXT,
        max_height=50,
    )
    for i, color in enumerate([ACCENT, AMBER, GREEN, NAV_MUTED]):
        c.setFillColor(color)
        c.circle(W - 55 - i * 31, 64, 11, fill=1, stroke=0)
    c.setFillColor(NAV_MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(28, 36, "Discovery infrastructure, not a temple census")
    c.showPage()


def draw_thesis(c: canvas.Canvas) -> None:
    page(c, "The thesis", 2, footer_text="Opportunity and boundary")
    label(c, "The opportunity", 28, 476, color=ACCENT)
    para(c, "The temples already exist.<br/>Bholenath makes their discovery systematic.", 28, 456, 520, font="Georgia", size=29, leading=31, max_height=78)
    para(c, "India's temple landscape is culturally rich, locally named and unevenly documented. The first problem is not publishing a final directory. It is building a repeatable way to find likely records, preserve how they were found and make them reviewable.", 28, 360, 500, size=11, leading=14.5, color=INK, max_height=80)
    card(c, 28, 260, 500, 54, fill=INDIGO, stroke=INDIGO)
    para(c, "Location data -> bounded search -> candidate evidence -> review", 46, 242, 465, size=12.5, leading=16, color=SURFACE, max_height=30)

    metric(c, 565, 456, 174, "785", "LGD districts", "Frozen Phase 1.1 administrative baseline.")
    metric(c, 754, 456, 178, "7,065", "Search tasks", "Nine bounded Shiva-related queries per district.")
    metric(c, 565, 345, 174, "74,117", "Candidate records", "Unique district-attributed Google Place IDs.")
    metric(c, 754, 345, 178, "59%", "High confidence", "Strong Shiva name signal, not verification.")

    line(c, 565, 226, 932, 226)
    label(c, "Boundary", 565, 208, color=ACCENT)
    para(c, "These are observed discovery records from a dated Google Places run. They are not the exact number of Shiva temples in India and not an official cultural census.", 565, 196, 367, size=9, leading=12, color=MUTED, max_height=54)
    c.showPage()


def draw_problem(c: canvas.Canvas) -> None:
    page(c, "The problem", 3, dark=True, footer_text="Problem statement")
    c.setFillColor(HexColor("#7E88A2"))
    c.setFont("Georgia", 42)
    c.drawString(28, 446, "02")
    para(c, "Temple information is visible.<br/>A reliable national view is still hard.", 28, 400, 360, font="Georgia", size=27, leading=29, color=SURFACE, max_height=100)
    para(c, "Names, scripts, listings and administrative references vary. Search results overlap. Geography and platforms change. Without a controlled pipeline, counts become impossible to explain or reproduce.", 28, 286, 360, size=10.5, leading=14, color=NAV_TEXT, max_height=88)

    step_card(c, 420, 444, 236, 1, "Names vary", "Shiva, Shiv, Mahadev, Shankar, Vishwanath, local spellings and regional scripts.", dark=True)
    step_card(c, 674, 444, 258, 2, "Sources differ", "Administrative geography and place listings answer different questions.", dark=True)
    step_card(c, 420, 340, 236, 3, "Results repeat", "The same Place ID can appear across keywords and nearby search locations.", dark=True)
    step_card(c, 674, 340, 258, 4, "Evidence is incomplete", "A discovered name is a lead. Identity, history and location still require independent review.", dark=True)

    for i, text in enumerate([
        "Resolve official location identities before search",
        "Keep each query-to-place observation",
        "Deduplicate by a stable external reference",
        "Separate confidence signals from verification decisions",
    ]):
        y = 220 - i * 43
        card(c, 420, y, 512, 32, dark=True, fill=HexColor("#2D3651"), stroke=HexColor("#414A65"), radius=6)
        c.setFillColor(ACCENT)
        c.circle(435, y - 16, 3, fill=1, stroke=0)
        para(c, text, 448, y - 9, 465, size=8.8, leading=11, color=NAV_TEXT, max_height=20)
    c.showPage()


def draw_proposal(c: canvas.Canvas) -> None:
    page(c, "The proposal", 4, footer_text="Core product proposition")
    label(c, "What we build", 28, 476, color=ACCENT)
    para(c, "A discovery and evidence layer for Shiva temple candidates.", 28, 456, 520, font="Georgia", size=28, leading=31, max_height=72)
    para(c, "Bholenath connects official location data, bounded search tasks, place observations and name-based classification - then makes each record inspectable without presenting discovery as cultural truth.", 28, 372, 520, size=10.8, leading=14.5, color=MUTED, max_height=65)

    words = ["Import", "Search", "Observe", "Dedupe", "Classify", "Export"]
    for i, word in enumerate(words):
        x = 28 + i * 85
        c.setStrokeColor(ACCENT_LINE)
        c.roundRect(x, 293, 72, 21, 10, fill=0, stroke=1)
        c.setFillColor(ACCENT_DARK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + 36, 300, word.upper())

    items = [
        ("01", "Import", "Normalize official Indian location records and preserve hierarchy."),
        ("02", "Generate", "Create one safe, reviewable search task per place and keyword."),
        ("03", "Discover", "Call Google Places Text Search with strict limits and narrow fields."),
        ("04", "Deduplicate", "Keep one current candidate per Google Place ID, plus observation history."),
        ("05", "Classify", "Score discovered names as high, medium or low Shiva confidence."),
        ("06", "Report", "Export national, state, district and candidate review datasets."),
    ]
    for i, (n, t, b) in enumerate(items):
        col, row = i % 2, i // 2
        x = 566 + col * 184
        top = 460 - row * 129
        card(c, x, top, 170, 110)
        label(c, f"{n} / {t}", x + 14, top - 20, color=ACCENT, size=7)
        para(c, b, x + 14, top - 38, 142, size=9.4, leading=12, max_height=58)
    c.showPage()


def draw_experience(c: canvas.Canvas) -> None:
    page(c, "North-star experience", 5, dark=True, footer_text="District-first discovery experience")
    label(c, "Ask a district question", 28, 474, color=HexColor("#F7BD79"))
    para(c, "Which Shiva temple candidates were discovered here, and what evidence supports each result?", 28, 452, 510, font="Georgia", size=26, leading=29, color=SURFACE, max_height=95)
    para(c, "Bholenath should let a researcher move from a district summary to an individual candidate, then inspect the source query, discovered name, Place ID, confidence reason and observation history.", 28, 334, 510, size=10.5, leading=14, color=NAV_TEXT, max_height=65)
    line(c, 28, 252, 28, 205, color=ACCENT, width=2)
    para(c, "The record is useful only when the user can see what is known, what is inferred and what is still unverified.", 46, 250, 455, font="Georgia-Italic", size=14, leading=18, color=SURFACE, max_height=58)
    for i, word in enumerate(["Summary", "Record", "Evidence", "Method", "Limits"]):
        c.setStrokeColor(HexColor("#55607B"))
        c.roundRect(28 + i * 86, 157, 76, 22, 11, fill=0, stroke=1)
        c.setFillColor(NAV_TEXT)
        c.setFont("Helvetica", 7)
        c.drawCentredString(66 + i * 86, 164, word.upper())

    card(c, 562, 456, 370, 302, dark=True, fill=HexColor("#29324B"))
    label(c, "Bholenath / Candidate record", 582, 433, color=NAV_MUTED)
    para(c, "Example Shiva temple candidate", 582, 411, 300, font="Georgia", size=18, leading=21, color=SURFACE, max_height=32)
    label(c, "Source query", 582, 362, color=HexColor("#F7BD79"))
    para(c, "Mahadev temple in [district], [state], India", 582, 347, 320, size=9.4, leading=12, color=NAV_TEXT, max_height=30)
    line(c, 582, 304, 902, 304, color=HexColor("#414A65"))
    label(c, "Evidence package", 582, 284, color=HexColor("#F7BD79"))
    for i, text in enumerate([
        "Discovered name + address",
        "Google Place ID + Maps URI",
        "Search task + source location",
        "Confidence score + reason",
    ]):
        y = 260 - i * 31
        c.setFillColor(ACCENT)
        c.circle(588, y + 3, 2.4, fill=1, stroke=0)
        para(c, text, 598, y + 9, 288, size=8.5, leading=10.5, color=NAV_TEXT, max_height=18)
    c.showPage()


def draw_architecture(c: canvas.Canvas) -> None:
    page(c, "Reference architecture", 6, footer_text="Conceptual Phase 1 architecture")
    para(c, "Use different systems for different jobs.", 28, 468, 650, font="Georgia", size=27, leading=31, max_height=42)
    para(c, "Official geography anchors search scope. MySQL holds locations, tasks, candidates and evidence. Python runs deterministic discovery and classification. The portal explains the resulting dataset.", 28, 420, 800, size=10.5, leading=14, color=MUTED, max_height=48)

    boxes = [
        (42, 315, 142, 54, "LGD + prepared\nlocation files"),
        (220, 315, 142, 54, "MySQL\nlocation registry"),
        (398, 315, 142, 54, "Python\nsearch task generator"),
        (576, 315, 142, 54, "Google Places\nText Search"),
        (754, 315, 164, 54, "Candidate + event\nstorage"),
    ]
    for x, top, w, h, text in boxes:
        card(c, x, top, w, h, fill=SURFACE)
        para(c, text.replace("\n", "<br/>"), x + 10, top - 16, w - 20, size=8.4, leading=10.4, align=TA_CENTER, max_height=34)
    for i in range(len(boxes) - 1):
        x1 = boxes[i][0] + boxes[i][2]
        x2 = boxes[i + 1][0]
        arrow(c, x1 + 5, 288, x2 - 5, 288, color=ACCENT_LINE)

    lower = [
        (220, 207, 142, 56, "Aliases + district\nalignment audit"),
        (398, 207, 142, 56, "Safe limits +\nfield masks"),
        (576, 207, 142, 56, "Name confidence\nclassifier"),
        (754, 207, 164, 56, "CSV reports +\nreview workspace"),
    ]
    for x, top, w, h, text in lower:
        card(c, x, top, w, h, fill=SURFACE_MUTED)
        para(c, text.replace("\n", "<br/>"), x + 10, top - 16, w - 20, size=8.2, leading=10.3, align=TA_CENTER, max_height=35)
    arrow(c, 291, 261, 291, 217, color=LINE_STRONG)
    arrow(c, 469, 261, 469, 217, color=LINE_STRONG)
    arrow(c, 647, 207, 647, 261, color=LINE_STRONG)
    arrow(c, 836, 261, 836, 217, color=LINE_STRONG)

    card(c, 28, 104, 350, 57, fill=INDIGO, stroke=INDIGO)
    label(c, "Architecture principle", 44, 85, color=HexColor("#F7BD79"))
    para(c, "Discovery finds candidates. Verification establishes truth.", 44, 72, 315, font="Georgia", size=13, leading=16, color=SURFACE, max_height=32)
    c.showPage()


def draw_model(c: canvas.Canvas) -> None:
    page(c, "Evidence model", 7, dark=True, footer_text="Candidate observation contract")
    label(c, "The foundational object", 28, 474, color=HexColor("#F7BD79"))
    para(c, "Candidate observation", 28, 451, 420, font="Georgia", size=28, leading=31, color=SURFACE, max_height=42)
    para(c, "A place returned by a specific bounded search, tied to a source location, query, external ID, timestamp and classification result.", 28, 397, 410, size=10.3, leading=14, color=NAV_TEXT, max_height=55)
    card(c, 28, 303, 322, 130, dark=True, fill=HexColor("#29324B"))
    label(c, "Example fields", 45, 280, color=HexColor("#F7BD79"))
    para(c, "Discovered name: [candidate name]<br/>Geography: [district], [state]<br/>External identity: Google Place ID<br/>Source query: [keyword] in [location]<br/>Confidence: high / medium / low<br/>Status: pending independent verification", 45, 261, 285, size=8.4, leading=13, color=NAV_TEXT, max_height=104)

    cx, cy = 636, 271
    c.setFillColor(SURFACE)
    c.circle(cx, cy, 55, fill=1, stroke=0)
    para(c, "CANDIDATE<br/>OBSERVATION", cx - 45, cy + 13, 90, size=8, leading=10, color=INDIGO, align=TA_CENTER, max_height=28)
    nodes = [
        (506, 400, 120, 43, "PLACE ID"),
        (676, 400, 120, 43, "DISCOVERED NAME"),
        (806, 316, 120, 43, "GEOGRAPHY"),
        (745, 185, 120, 43, "CLASSIFICATION"),
        (574, 145, 120, 43, "TIMESTAMP"),
        (425, 185, 120, 43, "SOURCE QUERY"),
        (386, 316, 120, 43, "SEARCH TASK"),
    ]
    for x, top, w, h, title in nodes:
        card(c, x, top, w, h, dark=True, fill=HexColor("#29324B"), radius=8)
        para(c, title, x + 8, top - 16, w - 16, size=7, leading=9, color=NAV_TEXT, align=TA_CENTER, max_height=18)
        ex, ey = x + w / 2, top - h / 2
        line(c, cx, cy, ex, ey, color=HexColor("#55607B"), width=0.8)

    for i, word in enumerate(["Location", "Task", "Place", "Event", "Candidate", "Report", "Review"]):
        x = 378 + i * 77
        c.setStrokeColor(HexColor("#55607B"))
        c.roundRect(x, 69, 67, 20, 10, fill=0, stroke=1)
        c.setFillColor(NAV_MUTED)
        c.setFont("Helvetica", 6.2)
        c.drawCentredString(x + 33.5, 76, word.upper())
    c.showPage()


def draw_trust(c: canvas.Canvas) -> None:
    page(c, "Trust model", 8, footer_text="Interpretation discipline")
    para(c, "Every result should carry its limits.", 28, 466, 700, font="Georgia", size=28, leading=31, max_height=44)
    para(c, "Bholenath's credibility comes from keeping administrative truth, discovery evidence, automated inference and human verification separate - while making the path between them visible.", 28, 416, 860, size=10.5, leading=14, color=MUTED, max_height=52)

    cols = [
        (28, "OFFICIAL REFERENCE", "LGD district name and code", GREEN),
        (258, "DISCOVERY EVIDENCE", "Google Places result observed for a query", ACCENT),
        (488, "AUTOMATED INFERENCE", "Name-based Shiva confidence", AMBER),
        (718, "HUMAN VERIFICATION", "Independent review outcome", INDIGO),
    ]
    for i, (x, title, body, color) in enumerate(cols):
        card(c, x, 325, 202, 83, fill=SURFACE)
        c.setFillColor(color)
        c.rect(x, 242, 202, 5, fill=1, stroke=0)
        label(c, title, x + 14, 303, color=color, size=6.5)
        para(c, body, x + 14, 286, 174, size=9.3, leading=12, max_height=40)
        if i < 3:
            arrow(c, x + 207, 283, x + 223, 283, color=LINE_STRONG)

    labels = [
        (28, "OBSERVED", "Directly returned and stored from a bounded search."),
        (338, "CLASSIFIED", "Scored from the discovered name using explicit terms."),
        (648, "VERIFIED", "Reserved for a later independent evidence decision."),
    ]
    for x, title, body in labels:
        card(c, x, 183, 284, 87, fill=SURFACE_MUTED)
        label(c, title, x + 14, 160, color=ACCENT)
        para(c, body, x + 14, 143, 250, size=9, leading=12, max_height=45)
    para(c, "Confidence is a triage signal. It is not proof of identity, history, affiliation, boundaries or continued existence.", 28, 69, 850, font="Georgia-Italic", size=13, leading=17, color=INDIGO, max_height=34)
    c.showPage()


def draw_baseline(c: canvas.Canvas) -> None:
    page(c, "Phase 1.1 baseline", 9, dark=True, footer_text="Frozen district-only snapshot")
    label(c, "Start narrow", 28, 474, color=HexColor("#F7BD79"))
    para(c, "A district baseline before deeper geography.", 28, 451, 510, font="Georgia", size=28, leading=31, color=SURFACE, max_height=45)
    para(c, "Phase 1.1 uses active LGD districts only. Towns, urban local bodies, sub-districts and villages are excluded so the baseline remains comparable and auditable.", 28, 360, 470, size=10.3, leading=14, color=NAV_TEXT, max_height=65)
    metric(c, 28, 292, 143, "785", "Districts", "Active LGD rows", dark=True)
    metric(c, 184, 292, 143, "7,065", "Tasks", "Completed searches", dark=True)
    metric(c, 340, 292, 143, "74,117", "Candidates", "Unique Place IDs", dark=True)

    card(c, 530, 456, 402, 290, dark=True, fill=HexColor("#29324B"))
    label(c, "Observed snapshot", 550, 430, color=HexColor("#F7BD79"))
    para(c, "May 5-17, 2026", 550, 410, 260, font="Georgia", size=18, leading=21, color=SURFACE, max_height=30)
    values = [
        ("229,495", "raw discovered occurrences"),
        ("155,378", "repeats removed across queries"),
        ("43,877", "high-confidence name matches"),
        ("7,366", "medium-confidence candidates"),
        ("22,874", "low-confidence possible records"),
        ("772", "districts with at least one candidate event"),
    ]
    for i, (value, text) in enumerate(values):
        col, row = i % 2, i // 2
        x = 550 + col * 186
        y = 352 - row * 65
        c.setFillColor(SURFACE)
        c.setFont("Georgia", 18)
        c.drawString(x, y, value)
        para(c, text, x, y - 8, 165, size=7.4, leading=9.2, color=NAV_MUTED, max_height=22)

    card(c, 28, 150, 455, 84, dark=True, fill=ACCENT, stroke=ACCENT)
    label(c, "Interpretation", 44, 125, color=SURFACE)
    para(c, "A reproducible discovery baseline of likely candidates - not the number of Shiva temples in India.", 44, 106, 420, font="Georgia", size=12.5, leading=16, color=SURFACE, max_height=40)
    para(c, "Dataset status: district_level_discovery_count_not_final_cultural_count", 530, 128, 402, size=7.5, leading=10, color=NAV_MUTED, max_height=22)
    c.showPage()


def draw_delivery(c: canvas.Canvas) -> None:
    page(c, "Delivery plan", 10, footer_text="Gated Phase 1 expansion")
    para(c, "Expand geography without contaminating the baseline.", 28, 466, 820, font="Georgia", size=27, leading=31, max_height=44)
    para(c, "Phase 1.1 is frozen as a district-only release. Each later layer should be versioned separately, use the same safety controls and earn its way into combined views through validation gates.", 28, 416, 850, size=10.5, leading=14, color=MUTED, max_height=52)

    phases = [
        ("1.1", "DISTRICT BASELINE", "Complete", "785 active LGD districts; 7,065 tasks; frozen release."),
        ("1.2", "TOWN + ULB", "Next", "Prepare authoritative locations, size the task budget and run a bounded pilot."),
        ("1.3", "SUB-DISTRICT", "Later", "Add tehsil or sub-district searches only after overlap rules are tested."),
        ("1.4", "SELECTIVE VILLAGES", "Later", "Use targeted pilots where local coverage justifies the cost and complexity."),
    ]
    for i, (num, title, status, body) in enumerate(phases):
        x = 28 + i * 230
        card(c, x, 332, 210, 132, fill=SURFACE)
        c.setStrokeColor(ACCENT if i == 1 else LINE_STRONG)
        c.setLineWidth(2 if i == 1 else 0.8)
        c.line(x, 332, x + 210, 332)
        label(c, f"Phase {num}", x + 14, 307, color=ACCENT)
        para(c, title, x + 14, 289, 180, size=9.5, leading=12, max_height=20)
        label(c, status, x + 14, 253, color=GREEN if status == "Complete" else AMBER)
        para(c, body, x + 14, 236, 180, size=8.4, leading=11, color=MUTED, max_height=62)

    card(c, 28, 164, 438, 86, fill=SURFACE_MUTED)
    label(c, "Core workstream", 44, 140, color=ACCENT)
    para(c, "Location preparation + task budgeting + safe discovery + event lineage + scoped reporting", 44, 121, 404, font="Georgia", size=13, leading=17, max_height=42)
    card(c, 494, 164, 438, 86, fill=SURFACE_MUTED)
    label(c, "Gate before scale", 510, 140, color=ACCENT)
    para(c, "Authority checked, duplicate scope understood, query budget approved, tests green, dataset version named", 510, 121, 404, font="Georgia", size=13, leading=17, max_height=42)
    c.showPage()


def draw_guardrails(c: canvas.Canvas) -> None:
    page(c, "Success + guardrails", 11, dark=True, footer_text="Scope discipline")
    label(c, "Success means reliability", 28, 474, color=HexColor("#F7BD79"))
    para(c, "What Phase 1 must prove", 28, 451, 420, font="Georgia", size=27, leading=31, color=SURFACE, max_height=42)
    success = [
        ("01", "Coverage", "Every in-scope location has an explicit search status."),
        ("02", "Identity", "Candidates deduplicate by Google Place ID."),
        ("03", "Lineage", "Each observation connects to its query and source location."),
        ("04", "Reproducibility", "The same snapshot yields the same classified reports."),
        ("05", "Safety", "Task, page and field limits prevent uncontrolled runs."),
        ("06", "Clarity", "Every output distinguishes discovery, confidence and verification."),
    ]
    for i, (n, t, b) in enumerate(success):
        y = 386 - i * 47
        c.setFillColor(ACCENT)
        c.circle(36, y + 3, 8, fill=1, stroke=0)
        c.setFillColor(SURFACE)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(36, y + 0.5, n)
        para(c, f"<b>{t}</b>: {b}", 55, y + 12, 410, size=8.8, leading=11.2, color=NAV_TEXT, max_height=26, bold_font="Helvetica-Bold")

    label(c, "Explicit non-goals", 520, 474, color=HexColor("#F7BD79"))
    para(c, "What Bholenath is not", 520, 451, 390, font="Georgia", size=27, leading=31, color=SURFACE, max_height=42)
    non_goals = [
        ("Not a temple census", "The dataset does not measure the exact real-world population."),
        ("Not verified by default", "A name match does not establish identity or heritage."),
        ("Not a scraped directory", "Collection is bounded and source-aware."),
        ("Not a ranking of sanctity", "Confidence is operational triage, not spiritual judgment."),
        ("Not boundary truth", "Search attribution does not prove that a pin lies inside a district."),
        ("Not final public knowledge", "Discovery records require independent evidence and review."),
    ]
    for i, (t, b) in enumerate(non_goals):
        col, row = i % 2, i // 2
        x = 520 + col * 206
        top = 389 - row * 94
        card(c, x, top, 190, 78, dark=True, fill=HexColor("#29324B"))
        para(c, t, x + 12, top - 15, 166, size=8.4, leading=10, color=SURFACE, max_height=18)
        para(c, b, x + 12, top - 35, 166, size=7.6, leading=9.7, color=NAV_MUTED, max_height=36)
    c.showPage()


def draw_compounding(c: canvas.Canvas) -> None:
    page(c, "What compounds", 12, footer_text="Compounding project assets")
    label(c, "The moat is not a number", 28, 474, color=ACCENT)
    para(c, "The valuable asset is accumulated evidence quality.", 28, 451, 410, font="Georgia", size=27, leading=30, max_height=74)
    para(c, "Search results will change. The durable value is the project's ability to explain what was searched, what was observed, how identity was handled and what still needs review.", 28, 354, 410, size=10.3, leading=14, color=MUTED, max_height=80)
    card(c, 28, 145, 410, 72, fill=INDIGO, stroke=INDIGO)
    para(c, "Build evidence quality before geographic quantity.", 46, 121, 375, font="Georgia", size=15, leading=19, color=SURFACE, max_height=30)
    para(c, "District -> town / ULB -> sub-district -> selective village", 46, 90, 375, size=8, leading=10, color=NAV_TEXT, max_height=20)

    assets = [
        ("Location registry", "Official names, codes, aliases, hierarchy and active scope."),
        ("Observation ledger", "Task-to-place events that preserve how candidates were found."),
        ("Classification lexicon", "Explicit Shiva terms, scores and reasons that can be tested."),
        ("Review corpus", "Human evidence decisions that improve future prioritization."),
        ("Versioned snapshots", "Frozen datasets that keep analysis comparable over time."),
        ("Evaluation suite", "Known-good cases for dedupe, classification and reporting."),
    ]
    for i, (title, body) in enumerate(assets):
        col, row = i % 2, i // 2
        x = 492 + col * 220
        top = 458 - row * 122
        card(c, x, top, 204, 104, fill=SURFACE)
        label(c, f"0{i + 1}", x + 14, top - 21, color=ACCENT)
        para(c, title, x + 14, top - 37, 176, font="Georgia", size=12, leading=14, max_height=20)
        para(c, body, x + 14, top - 61, 176, size=8.2, leading=10.5, color=MUTED, max_height=39)
    c.showPage()


def draw_decision(c: canvas.Canvas) -> None:
    page(c, "Decision", 13, dark=True, footer_text="Recommended next step")
    label(c, "Recommended next step", 28, 474, color=HexColor("#F7BD79"))
    para(c, "Build Phase 1.2 as a separate, bounded location layer.", 28, 447, 540, font="Georgia", size=31, leading=33, color=SURFACE, max_height=108)
    para(c, "Preserve the Phase 1.1 district release unchanged. Prepare authoritative town and urban local body inputs, quantify the search budget, run a small pilot, evaluate overlap and only then authorize wider discovery.", 28, 317, 520, size=10.7, leading=14.5, color=NAV_TEXT, max_height=82)
    for i, word in enumerate(["Source", "Normalize", "Budget", "Pilot", "Evaluate", "Version"]):
        x = 28 + i * 87
        c.setStrokeColor(HexColor("#55607B"))
        c.roundRect(x, 202, 77, 22, 11, fill=0, stroke=1)
        c.setFillColor(NAV_TEXT)
        c.setFont("Helvetica", 6.3)
        c.drawCentredString(x + 38.5, 209, word.upper())

    card(c, 610, 453, 322, 164, dark=True, fill=HexColor("#29324B"))
    label(c, "The Bholenath test", 630, 427, color=HexColor("#F7BD79"))
    para(c, "Does this make a candidate easier to discover, trace and independently verify?", 630, 402, 282, font="Georgia", size=18, leading=22, color=SURFACE, max_height=76)
    para(c, "If not, it probably does not belong in Phase 1.", 630, 313, 282, size=9.3, leading=12, color=NAV_MUTED, max_height=28)
    line(c, 610, 249, 932, 249, color=HexColor("#55607B"))
    para(c, "The temples already exist.<br/>Bholenath makes their discovery systematic.", 610, 220, 322, font="Georgia", size=19, leading=22, color=SURFACE, max_height=58)
    c.showPage()


def draw_sources(c: canvas.Canvas) -> None:
    page(c, "Sources + design note", 14, footer_text="Prepared for internal discussion")
    label(c, "Primary references", 28, 474, color=ACCENT)
    para(c, "Public and project references used in this proposal", 28, 455, 430, font="Georgia", size=20, leading=23, max_height=32)

    refs = [
        ("Shiva Temple Discovery workspace", "https://jaibholenath.com/", "Current public theme, terminology and district-first data presentation."),
        ("Local Government Directory - Districts", "https://data.gov.in/resource/local-government-directory-lgd-districts", "Administrative district names and LGD codes for the Phase 1.1 baseline."),
        ("Google Places Text Search (New)", "https://developers.google.com/maps/documentation/places/web-service/text-search", "Bounded place discovery using text queries, type filters, field masks and Place IDs."),
        ("Project repository", "README.md; docs/DATA_POLICY.md; docs/PHASE_1_1_DISTRICT_BASELINE.md", "Implementation scope, safety limits, data language and frozen release notes."),
    ]
    for i, (title, url, body) in enumerate(refs):
        top = 396 - i * 80
        para(c, title, 28, top, 420, size=9.3, leading=11, color=INK, max_height=18)
        para(c, url, 28, top - 18, 420, size=6.8, leading=9, color=ACCENT_DARK, max_height=22)
        para(c, body, 28, top - 43, 420, size=7.7, leading=10, color=MUTED, max_height=30)

    label(c, "Visual direction", 510, 474, color=ACCENT)
    para(c, "Bholenath's website identity, translated into an editorial proposal", 510, 455, 410, font="Georgia", size=20, leading=23, max_height=55)
    para(c, "The layout borrows the Drishti proposal's disciplined pacing - oversized statements, alternating light and dark pages, thin rules, rounded panels and diagram-led storytelling - while using Bholenath's own palette and typography.", 510, 377, 410, size=9.4, leading=12.5, color=MUTED, max_height=82)

    swatches = [
        (INDIGO, "INDIGO"),
        (ACCENT, "SAFFRON"),
        (PAGE, "IVORY"),
        (GREEN, "GREEN"),
    ]
    for i, (color, name) in enumerate(swatches):
        x = 510 + i * 102
        c.setFillColor(color)
        c.setStrokeColor(LINE_STRONG)
        c.roundRect(x, 246, 84, 50, 8, fill=1, stroke=1)
        label(c, name, x, 228, color=MUTED, size=6.5)

    card(c, 510, 192, 410, 92, fill=SURFACE_MUTED)
    label(c, "Typography", 526, 168, color=ACCENT)
    para(c, "Georgia for the temple-story voice.<br/>Inter-style system sans for evidence, labels and data.", 526, 150, 378, font="Georgia", size=12.5, leading=17, max_height=50)

    label(c, "Status", 510, 77, color=ACCENT)
    para(c, "Internal concept proposal. Phase sequencing and future expansion remain planning decisions. Snapshot figures are discovery records, not verified real-world temple counts.", 510, 63, 410, size=8.2, leading=10.8, color=MUTED, max_height=42)
    c.showPage()


def build() -> Path:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=(W, H), pageCompression=1)
    c.setTitle("Project Bholenath - Proposal")
    c.setAuthor("Project Bholenath")
    c.setSubject("Phase 1 Shiva temple candidate discovery proposal")

    draw_cover(c)
    draw_thesis(c)
    draw_problem(c)
    draw_proposal(c)
    draw_experience(c)
    draw_architecture(c)
    draw_model(c)
    draw_trust(c)
    draw_baseline(c)
    draw_delivery(c)
    draw_guardrails(c)
    draw_compounding(c)
    draw_decision(c)
    draw_sources(c)

    c.save()
    return OUTPUT


if __name__ == "__main__":
    print(build())
