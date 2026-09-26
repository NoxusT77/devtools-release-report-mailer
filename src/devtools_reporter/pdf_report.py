from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .report_models import ReportRequest, ReleaseDecision


def render_release_report(
    request: ReportRequest, decision: ReleaseDecision, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    operation = request.operation
    document = SimpleDocTemplate(
        str(output_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm
    )
    story = [
        Paragraph(f"Release report: {operation.release_id}", styles["Title"]),
        Paragraph(
            f"{operation.environment} / {operation.commit_sha} / {decision.value.upper()}",
            styles["Heading2"],
        ),
        Paragraph(f"Started {operation.started_at.isoformat()}", styles["BodyText"]),
        Spacer(1, 8 * mm),
    ]
    rows = [["Check", "State", "Seconds", "Diagnostic"]]
    rows.extend(
        [event.check, event.state.value, f"{event.duration_seconds:.2f}", event.detail]
        for event in request.events
    )
    table = Table(rows, colWidths=[35 * mm, 22 * mm, 20 * mm, 80 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20262E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD2D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ]
        )
    )
    story.append(table)
    document.build(story)

