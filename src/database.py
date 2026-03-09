import sqlite3
import pandas as pd
from pathlib import Path
from src.config import DATA_DIR, MAX_ROWS_DISPLAY, MAX_ROWS_EXPORT, FORBIDDEN_SQL_KEYWORDS


def init_database() -> sqlite3.Connection:
    """Load CSV data into an in-memory SQLite database."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)

    # Load anomaly chunks
    chunk_paths = sorted(DATA_DIR.glob("GenericAnomaly_dump_result_chunk_*.csv"))
    if not chunk_paths:
        raise FileNotFoundError(f"No anomaly CSV chunks found in {DATA_DIR}")

    frames = [pd.read_csv(p) for p in chunk_paths]
    anomalies = pd.concat(frames, ignore_index=True)

    # Clean column names
    rename_map = {
        "object_identification_fields_": "object_identification_fields",
        "error_fields_": "error_fields",
        "other_fields_": "other_fields",
    }
    anomalies.rename(columns=rename_map, inplace=True)
    anomalies.drop(columns=["other_fields_.1"], errors="ignore", inplace=True)

    # Type cleanup
    anomalies["hotfix_flg"] = anomalies["hotfix_flg"].fillna(0).astype(int)

    anomalies.to_sql("generic_anomaly", conn, index=False, if_exists="replace")

    # Load configuration
    config_path = DATA_DIR / "Configuration.csv"
    if config_path.exists():
        config = pd.read_csv(config_path)
        config.to_sql("configuration", conn, index=False, if_exists="replace")

    # Create indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_typology ON generic_anomaly(typology_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_control ON generic_anomaly(control_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_bizobj ON generic_anomaly(business_object_typ)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_anomaly_asof ON generic_anomaly(asof_dat)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_config_typology ON configuration(typology_id)")
    conn.commit()

    return conn


def validate_sql(sql: str) -> None:
    """Validate that the SQL is a safe SELECT query."""
    normalized = sql.strip().upper()

    if not normalized.startswith("SELECT"):
        raise ValueError("Seules les requêtes SELECT sont autorisées.")

    for kw in FORBIDDEN_SQL_KEYWORDS:
        # Check as whole word to avoid false positives
        if f" {kw} " in f" {normalized} ":
            raise ValueError(f"Mot-clé interdit détecté : {kw}")


def validate_with_explain(conn: sqlite3.Connection, sql: str) -> None:
    """Run EXPLAIN QUERY PLAN to catch syntax errors before execution."""
    try:
        conn.execute(f"EXPLAIN QUERY PLAN {sql}")
    except sqlite3.OperationalError as e:
        raise ValueError(f"Erreur de syntaxe SQL : {e}")


def check_expensive_query(sql: str) -> list[str]:
    """Detect potentially expensive query patterns and return warnings."""
    import re
    warnings = []
    normalized = sql.strip().upper()

    # SELECT * without LIMIT
    if re.search(r"SELECT\s+\*", normalized) and "LIMIT" not in normalized:
        warnings.append("SELECT * sans LIMIT peut retourner un très grand nombre de lignes.")

    # CROSS JOIN
    if "CROSS JOIN" in normalized:
        warnings.append("CROSS JOIN peut produire un produit cartésien très volumineux.")

    # Multiple tables without WHERE
    from_match = re.search(r"FROM\s+(\w+)\s*,\s*(\w+)", normalized)
    if from_match and "WHERE" not in normalized:
        warnings.append("Jointure implicite (virgule) sans clause WHERE détectée.")

    return warnings


def execute_query(conn: sqlite3.Connection, sql: str, max_rows: int = MAX_ROWS_DISPLAY, cache=None) -> dict:
    """Execute a validated SELECT query and return results."""
    validate_sql(sql)
    validate_with_explain(conn, sql)

    # Check cache
    if cache is not None:
        cached = cache.get(sql)
        if cached is not None:
            return cached

    cursor = conn.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchmany(max_rows + 1)

    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]

    # Get total count
    try:
        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        total_count = conn.execute(count_sql).fetchone()[0]
    except Exception:
        total_count = len(rows)

    result = {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "total_count": total_count,
        "truncated": truncated,
    }

    # Store in cache
    if cache is not None:
        cache.set(sql, result)

    return result


def get_schema_info(conn: sqlite3.Connection) -> dict:
    """Return schema metadata for all tables."""
    tables = {}
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        col_cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [{"name": row[1], "type": row[2]} for row in col_cursor.fetchall()]
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        tables[table_name] = {"columns": columns, "row_count": count}
    return tables
