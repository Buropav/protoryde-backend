from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PRIMARY = HexColor("#1A1A2E")
ACCENT = HexColor("#E94560")
LIGHT_BG = HexColor("#F5F5F5")
WHITE = HexColor("#FFFFFF")
DARK_TEXT = HexColor("#222222")
MUTED = HexColor("#666666")


def _build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=PRIMARY,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "section": ParagraphStyle(
            "SectionHead",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=ACCENT,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "BodyText2",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            textColor=DARK_TEXT,
            leading=14,
        ),
        "exclusion": ParagraphStyle(
            "Exclusion",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            textColor=DARK_TEXT,
            leftIndent=8 * mm,
            bulletIndent=4 * mm,
            spaceBefore=1 * mm,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _table(data: List[List[str]], header: bool = False) -> Table:
    table = Table(data, colWidths=[55 * mm, 110 * mm] if not header else [120 * mm, 45 * mm])
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, MUTED),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
        ]
    else:
        style += [
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
            ("TEXTCOLOR", (0, 0), (0, -1), DARK_TEXT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ]
    table.setStyle(TableStyle(style))
    return table


def generate_policy_pdf(
    policy_data: Dict[str, Any],
    rider_data: Dict[str, Any],
    exclusions: List[str],
    exclusions_version: str,
    thresholds: Dict[str, Any],
    fixture_version: str,
) -> bytes:
    styles = _build_styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )
    story = []

    story.append(Paragraph("ProtoRyde", styles["title"]))
    story.append(Paragraph("Parametric Policy Document", styles["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=4 * mm))

    story.append(Paragraph("Rider Information", styles["section"]))
    story.append(
        _table(
            [
                ["Rider Name", str(rider_data.get("name", "N/A"))],
                ["Phone", str(rider_data.get("phone", "N/A"))],
                ["Delhivery Partner ID", str(rider_data.get("delhivery_partner_id", "N/A"))],
                ["Zone", str(rider_data.get("zone", "N/A"))],
            ]
        )
    )

    created_at = policy_data.get("created_at", "")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%d %b %Y, %H:%M UTC")

    story.append(Paragraph("Policy Details", styles["section"]))
    story.append(
        _table(
            [
                ["Policy ID", str(policy_data.get("id", "N/A"))],
                ["Status", str(policy_data.get("status", "N/A")).upper()],
                ["Base Premium (INR)", str(policy_data.get("base_premium", "N/A"))],
                ["Final Premium (INR)", str(policy_data.get("final_premium", "N/A"))],
                ["Issued On", str(created_at)],
                ["Exclusions Version", exclusions_version],
                ["Fixture Version", fixture_version],
            ]
        )
    )

    breakdown = policy_data.get("premium_breakdown", []) or []
    if breakdown:
        story.append(Paragraph("Premium Breakdown", styles["section"]))
        rows = [["Factor", "Impact (INR)"]]
        for item in breakdown:
            rows.append([str(item.get("factor", "")), str(item.get("impact_inr", item.get("amount", 0.0)))])
        story.append(_table(rows, header=True))

    story.append(Paragraph("Trigger Thresholds", styles["section"]))
    for key, value in thresholds.items():
        story.append(Paragraph(f"&bull; {key}: {value}", styles["body"]))

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED, spaceAfter=2 * mm))
    story.append(Paragraph("Explicit Coverage Exclusions", styles["section"]))
    story.append(Paragraph("This policy does <b>NOT</b> cover losses arising from:", styles["body"]))
    story.append(Spacer(1, 2 * mm))
    for item in exclusions:
        story.append(Paragraph(f"&bull; {item}", styles["exclusion"]))

    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MUTED, spaceAfter=3 * mm))
    story.append(
        Paragraph(
            f"Generated by ProtoRyde Engine on {now}. System-generated document.",
            styles["footer"],
        )
    )

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
