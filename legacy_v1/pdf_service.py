"""
pdf_service.py -- Generates a professional ProtoRyde policy PDF in-memory.
"""

from io import BytesIO
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
PRIMARY = HexColor("#1A1A2E")
ACCENT = HexColor("#E94560")
LIGHT_BG = HexColor("#F5F5F5")
WHITE = HexColor("#FFFFFF")
DARK_TEXT = HexColor("#222222")
MUTED = HexColor("#666666")


# ---------------------------------------------------------------------------
# Custom styles
# ---------------------------------------------------------------------------
def _build_styles():
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "DocTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )

    subtitle = ParagraphStyle(
        "DocSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    )

    section = ParagraphStyle(
        "SectionHead",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=ACCENT,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )

    body = ParagraphStyle(
        "BodyText2",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        textColor=DARK_TEXT,
        leading=14,
    )

    exclusion = ParagraphStyle(
        "Exclusion",
        parent=body,
        fontName="Helvetica",
        fontSize=10,
        textColor=DARK_TEXT,
        leftIndent=8 * mm,
        bulletIndent=4 * mm,
        spaceBefore=1 * mm,
    )

    footer = ParagraphStyle(
        "Footer",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=MUTED,
        alignment=TA_CENTER,
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "section": section,
        "body": body,
        "exclusion": exclusion,
        "footer": footer,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
EXCLUSIONS = [
    "War, armed conflict, or military operations.",
    "Pandemic or epidemic declared events.",
    "Health, injury, or vehicle damage.",
    "Income loss due to personal choice or active platform suspension.",
]


def generate_policy_pdf(policy_data: dict, rider_data: dict) -> BytesIO:
    """
    Build a policy PDF and return it as an in-memory BytesIO buffer.

    Expected keys
    -------------
    rider_data : name, zone, phone, delhivery_partner_id
    policy_data: id, base_premium, final_premium, premium_breakdown, status, created_at
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = _build_styles()
    story = []

    # ---- Header ----------------------------------------------------------
    story.append(Paragraph("ProtoRyde", styles["title"]))
    story.append(Paragraph("Parametric Policy Document", styles["subtitle"]))
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=ACCENT, spaceAfter=4 * mm
        )
    )

    # ---- Rider info table ------------------------------------------------
    story.append(Paragraph("Rider Information", styles["section"]))

    rider_table_data = [
        ["Rider Name", rider_data.get("name", "N/A")],
        ["Phone", rider_data.get("phone", "N/A")],
        ["Delhivery Partner ID", rider_data.get("delhivery_partner_id", "N/A")],
        ["Zone", rider_data.get("zone", "N/A")],
    ]

    rider_table = Table(rider_table_data, colWidths=[55 * mm, 110 * mm])
    rider_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
                ("TEXTCOLOR", (0, 0), (0, -1), DARK_TEXT),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, MUTED),
            ]
        )
    )
    story.append(rider_table)

    # ---- Policy details --------------------------------------------------
    story.append(Paragraph("Policy Details", styles["section"]))

    created_at = policy_data.get("created_at", "")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%d %b %Y, %H:%M UTC")

    policy_table_data = [
        ["Policy ID", str(policy_data.get("id", "N/A"))],
        ["Status", str(policy_data.get("status", "N/A")).upper()],
        ["Base Premium (INR)", str(policy_data.get("base_premium", "N/A"))],
        ["Final Premium (INR)", str(policy_data.get("final_premium", "N/A"))],
        ["Issued On", str(created_at)],
    ]

    policy_table = Table(policy_table_data, colWidths=[55 * mm, 110 * mm])
    policy_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BG),
                ("TEXTCOLOR", (0, 0), (0, -1), DARK_TEXT),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, MUTED),
            ]
        )
    )
    story.append(policy_table)

    # ---- Premium breakdown -----------------------------------------------
    breakdown = policy_data.get("premium_breakdown", [])
    if breakdown:
        story.append(Paragraph("Premium Breakdown", styles["section"]))

        bd_header = [["Factor", "Impact (INR)"]]
        bd_rows = [
            [item.get("factor", ""), str(item.get("impact_inr", 0))]
            for item in breakdown
        ]

        bd_table = Table(bd_header + bd_rows, colWidths=[120 * mm, 45 * mm])
        bd_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, MUTED),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_BG]),
                ]
            )
        )
        story.append(bd_table)

    # ---- Exclusions (CRITICAL) -------------------------------------------
    story.append(Spacer(1, 4 * mm))
    story.append(
        HRFlowable(
            width="100%", thickness=0.5, color=MUTED, spaceAfter=2 * mm
        )
    )
    story.append(Paragraph("Explicit Coverage Exclusions", styles["section"]))
    story.append(
        Paragraph(
            "This policy does <b>NOT</b> cover losses arising from:",
            styles["body"],
        )
    )
    story.append(Spacer(1, 2 * mm))

    for exc in EXCLUSIONS:
        story.append(
            Paragraph(
                f"&bull;  {exc}",
                styles["exclusion"],
            )
        )

    # ---- Footer ----------------------------------------------------------
    story.append(Spacer(1, 12 * mm))
    story.append(
        HRFlowable(
            width="100%", thickness=0.5, color=MUTED, spaceAfter=3 * mm
        )
    )
    now = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    story.append(
        Paragraph(
            f"Generated by ProtoRyde Engine on {now}. "
            "This document is system-generated and does not require a signature.",
            styles["footer"],
        )
    )

    doc.build(story)
    buf.seek(0)
    return buf
