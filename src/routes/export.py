import io
from datetime import datetime
import pandas as pd
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.database import validate_sql
from src.config import MAX_ROWS_EXPORT

router = APIRouter()


def generate_pdf(question: str | None, sql: str, df: pd.DataFrame, summary: str | None) -> io.BytesIO:
    """Generate a PDF report with question, SQL, results table, and summary."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    elements.append(Paragraph("Prisme — Rapport d'export", title_style))
    elements.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 8 * mm))

    # Question
    if question:
        elements.append(Paragraph("<b>Question :</b>", styles["Heading3"]))
        elements.append(Paragraph(question, styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

    # SQL
    elements.append(Paragraph("<b>Requête SQL :</b>", styles["Heading3"]))
    code_style = ParagraphStyle("Code", parent=styles["Code"], fontSize=9, leading=12)
    elements.append(Preformatted(sql, code_style))
    elements.append(Spacer(1, 4 * mm))

    # Results table
    if not df.empty:
        elements.append(Paragraph(f"<b>Résultats ({len(df)} lignes) :</b>", styles["Heading3"]))

        # Truncate for PDF (max 100 rows)
        display_df = df.head(100)
        table_data = [list(display_df.columns)]
        for _, row in display_df.iterrows():
            table_data.append([str(v)[:50] if v is not None else "" for v in row])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.36, 0.10, 0.49)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.2, 0.2, 0.2)),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.Color(0.95, 0.95, 0.95), colors.white]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 4 * mm))

    # Summary
    if summary:
        elements.append(Paragraph("<b>Résumé :</b>", styles["Heading3"]))
        elements.append(Paragraph(summary, styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


@router.get("/api/export")
async def export(
    request: Request,
    sql: str = Query(...),
    format: str = Query("csv", pattern="^(csv|xlsx|pdf)$"),
    conversation_id: str = Query(None),
):
    """Export query results as CSV, Excel, or PDF file."""
    db = request.app.state.db

    try:
        validate_sql(sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        df = pd.read_sql_query(sql, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur SQL : {str(e)}")

    # Limit rows
    if len(df) > MAX_ROWS_EXPORT:
        df = df.head(MAX_ROWS_EXPORT)

    if format == "pdf":
        # Get question and summary from conversation if available
        question = None
        summary = None
        if conversation_id:
            store = request.app.state.conversations
            conv = store.get(conversation_id)
            if conv and conv["history"]:
                # Find last user message as question
                for msg in reversed(conv["history"]):
                    if msg["role"] == "user":
                        question = msg["content"]
                        break
                # Find last assistant message as summary
                for msg in reversed(conv["history"]):
                    if msg["role"] == "assistant" and msg["content"].startswith("Résultats :"):
                        summary = msg["content"].replace("Résultats : ", "", 1)
                        break

        buffer = generate_pdf(question, sql, df, summary)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=export.pdf"},
        )

    buffer = io.BytesIO()

    if format == "csv":
        df.to_csv(buffer, index=False, encoding="utf-8-sig")
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )
    else:
        df.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=export.xlsx"},
        )
