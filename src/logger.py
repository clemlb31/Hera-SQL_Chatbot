import json
import sqlite3
from datetime import datetime, timezone
from src.config import DATA_DIR


class EventLogger:
    """Logs events (LLM calls, SQL execution, errors) to a SQLite table."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(DATA_DIR / "conversations.db")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_table()

    def _init_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                conversation_id TEXT,
                model TEXT,
                latency_ms INTEGER,
                sql_query TEXT,
                error TEXT,
                metadata TEXT
            )
        """)
        self._conn.commit()

    def log(
        self,
        event_type: str,
        conversation_id: str | None = None,
        model: str | None = None,
        latency_ms: int | None = None,
        sql: str | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._conn.execute(
            """INSERT INTO logs (timestamp, event_type, conversation_id, model, latency_ms, sql_query, error, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                event_type,
                conversation_id,
                model,
                latency_ms,
                sql,
                error,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self._conn.commit()

    def get_recent(self, limit: int = 50) -> list[dict]:
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        self._conn.row_factory = None
        return [dict(r) for r in rows]

    def close(self):
        self._conn.close()
