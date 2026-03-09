import pytest
from src.database import execute_query, validate_sql


def test_tables_exist(db):
    """Both tables should be created."""
    tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    assert "generic_anomaly" in table_names
    assert "configuration" in table_names


def test_anomaly_row_count(db):
    """Should have ~167K anomaly rows."""
    count = db.execute("SELECT COUNT(*) FROM generic_anomaly").fetchone()[0]
    assert count > 100_000


def test_configuration_row_count(db):
    """Configuration table should have 264 rows."""
    count = db.execute("SELECT COUNT(*) FROM configuration").fetchone()[0]
    assert count == 264


def test_columns_cleaned(db):
    """Trailing underscores should be removed from column names."""
    cursor = db.execute("PRAGMA table_info(generic_anomaly)")
    col_names = [row[1] for row in cursor.fetchall()]
    assert "object_identification_fields" in col_names
    assert "error_fields" in col_names
    assert "other_fields" in col_names
    assert "object_identification_fields_" not in col_names


def test_join_works(db):
    """LEFT JOIN on typology_id should return enriched rows."""
    result = db.execute("""
        SELECT a.anomaly_kuid, c.typology_en_lbl
        FROM generic_anomaly a
        LEFT JOIN configuration c ON a.typology_id = c.typology_id
        LIMIT 5
    """).fetchall()
    assert len(result) == 5


def test_execute_query(db):
    """execute_query should return proper structure."""
    result = execute_query(db, "SELECT anomaly_kuid FROM generic_anomaly LIMIT 3")
    assert result["columns"] == ["anomaly_kuid"]
    assert len(result["rows"]) == 3
    assert result["total_count"] == 3
    assert result["truncated"] is False


def test_select_only():
    """Non-SELECT queries should be rejected."""
    with pytest.raises(ValueError, match="SELECT"):
        validate_sql("DELETE FROM generic_anomaly")

    with pytest.raises(ValueError, match="interdit"):
        validate_sql("SELECT * FROM generic_anomaly; DROP TABLE generic_anomaly")


def test_forbidden_keywords():
    """Dangerous keywords should be blocked."""
    for kw in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]:
        with pytest.raises(ValueError):
            validate_sql(f"SELECT 1; {kw} TABLE x")
