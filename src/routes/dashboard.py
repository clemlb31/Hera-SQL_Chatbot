from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/dashboard")
async def dashboard(request: Request):
    """Return KPI stats for the dashboard panel."""
    db = request.app.state.db

    total = db.execute("SELECT COUNT(*) FROM generic_anomaly").fetchone()[0]
    hotfix_count = db.execute("SELECT COUNT(*) FROM generic_anomaly WHERE hotfix_flg = 1").fetchone()[0]
    typology_count = db.execute("SELECT COUNT(*) FROM configuration").fetchone()[0]

    # Top 5 business object types
    top_objects = db.execute("""
        SELECT business_object_typ, COUNT(*) AS nb
        FROM generic_anomaly
        GROUP BY business_object_typ
        ORDER BY nb DESC
        LIMIT 5
    """).fetchall()

    # Top 5 typologies
    top_typologies = db.execute("""
        SELECT c.typology_fr_lbl, COUNT(*) AS nb
        FROM generic_anomaly a
        LEFT JOIN configuration c ON a.typology_id = c.typology_id
        WHERE c.typology_fr_lbl IS NOT NULL
        GROUP BY c.typology_fr_lbl
        ORDER BY nb DESC
        LIMIT 5
    """).fetchall()

    # Event type breakdown
    events = db.execute("""
        SELECT source_event_typ, COUNT(*) AS nb
        FROM generic_anomaly
        WHERE source_event_typ IS NOT NULL
        GROUP BY source_event_typ
        ORDER BY nb DESC
    """).fetchall()

    return {
        "total_anomalies": total,
        "hotfix_count": hotfix_count,
        "typology_count": typology_count,
        "top_business_objects": [{"label": r[0], "count": r[1]} for r in top_objects],
        "top_typologies": [{"label": r[0], "count": r[1]} for r in top_typologies],
        "events": [{"label": r[0], "count": r[1]} for r in events],
    }
