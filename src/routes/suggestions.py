from fastapi import APIRouter, Request, Query

router = APIRouter()


@router.get("/api/suggestions")
async def suggestions(request: Request, q: str = Query(..., min_length=2)):
    """Return column names, table names, and distinct values matching the query."""
    value_index = request.app.state.value_index
    query_lower = q.lower()

    results = []

    # Table names
    for table in ["generic_anomaly", "configuration"]:
        if query_lower in table:
            results.append({"text": table, "category": "table"})

    # Column names from the value index
    all_columns = value_index.ANOMALY_COLUMNS + value_index.CONFIG_COLUMNS
    for col in all_columns:
        if query_lower in col.lower():
            results.append({"text": col, "category": "colonne"})

    # Distinct values
    for col, values in value_index._values.items():
        for val in values:
            if query_lower in str(val).lower():
                results.append({"text": str(val), "category": col})
                if len(results) >= 10:
                    return results

    return results[:10]
