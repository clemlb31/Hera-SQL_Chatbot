import json
import sqlite3
from datetime import datetime, timezone
from src.config import DATA_DIR


class ConversationStore:
    """Persistent conversation storage backed by SQLite."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(DATA_DIR / "conversations.db")
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                model TEXT,
                pending_sql TEXT,
                last_results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );
        """)
        self._conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, conv_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
            (conv_id, self._now(), self._now()),
        )
        self._conn.commit()

    def __contains__(self, conv_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return row is not None

    def get(self, conv_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "model": row["model"],
            "pending_sql": row["pending_sql"],
            "last_results": json.loads(row["last_results"]) if row["last_results"] else None,
            "history": self.get_history(conv_id),
        }

    def get_history(self, conv_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def add_message(self, conv_id: str, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conv_id, role, content, self._now()),
        )
        self._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (self._now(), conv_id),
        )
        self._conn.commit()

    def set_pending_sql(self, conv_id: str, sql: str | None) -> None:
        self._conn.execute(
            "UPDATE conversations SET pending_sql = ?, updated_at = ? WHERE id = ?",
            (sql, self._now(), conv_id),
        )
        self._conn.commit()

    def set_model(self, conv_id: str, model: str) -> None:
        self._conn.execute(
            "UPDATE conversations SET model = ?, updated_at = ? WHERE id = ?",
            (model, self._now(), conv_id),
        )
        self._conn.commit()

    def set_last_results(self, conv_id: str, results: dict | None) -> None:
        self._conn.execute(
            "UPDATE conversations SET last_results = ?, updated_at = ? WHERE id = ?",
            (json.dumps(results, default=str) if results else None, self._now(), conv_id),
        )
        self._conn.commit()

    def get_model(self, conv_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT model FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return row["model"] if row else None

    def get_pending_sql(self, conv_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT pending_sql FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return row["pending_sql"] if row else None

    def get_last_results(self, conv_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT last_results FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if row and row["last_results"]:
            return json.loads(row["last_results"])
        return None

    def list_all(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute("""
            SELECT c.id, c.model, c.created_at, c.updated_at,
                   (SELECT content FROM messages WHERE conversation_id = c.id AND role = 'user' ORDER BY id LIMIT 1) as first_message
            FROM conversations c
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete(self, conv_id: str) -> None:
        self._conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        self._conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        self._conn.commit()

    def close(self):
        self._conn.close()
