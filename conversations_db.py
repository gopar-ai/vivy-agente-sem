import sqlite3
from datetime import datetime, timezone

DB_PATH = 'conversations.db'


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                pinned INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS current_session (
                id INTEGER PRIMARY KEY,
                session_id TEXT
            )
        """)


def create_conversation(conversation_id, title="Nueva conversacion"):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, pinned, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
            (conversation_id, title, now, now),
        )


def exists(conversation_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    return row is not None


def get_all():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, pinned FROM conversations ORDER BY pinned DESC, created_at DESC"
        ).fetchall()
    return [{"id": row[0], "title": row[1], "pinned": bool(row[2])} for row in rows]


def get_title(conversation_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    return row[0] if row else None


def update_title(conversation_id, title):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conversation_id),
        )


def toggle_pinned(conversation_id):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT pinned FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        new_value = 0 if row[0] else 1
        conn.execute(
            "UPDATE conversations SET pinned = ?, updated_at = ? WHERE id = ?",
            (new_value, now, conversation_id),
        )
    return bool(new_value)


def delete_conversation(conversation_id):
    with _connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


def get_current_session():
    with _connect() as conn:
        row = conn.execute("SELECT session_id FROM current_session WHERE id = 1").fetchone()
    return row[0] if row else None


def set_current_session(session_id):
    with _connect() as conn:
        conn.execute("""
            INSERT INTO current_session (id, session_id) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET session_id = excluded.session_id
        """, (session_id,))
