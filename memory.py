import sqlite3
from datetime import datetime, timezone

DB_PATH = 'vivy.db'

# Acciones de Google Ads pendientes de confirmacion del usuario.
# action_id -> {"type": ..., ...payload}
PENDING_ACTIONS = {}


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions_log (
                action_id TEXT PRIMARY KEY,
                action_type TEXT,
                details TEXT,
                status TEXT,
                executed_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT,
                role TEXT,
                text TEXT,
                created_at TEXT
            )
        """)


def get_preference(key, default=None):
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM user_preferences WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row else default


def get_all_preferences():
    with _connect() as conn:
        rows = conn.execute("SELECT key, value FROM user_preferences").fetchall()
    return {key: value for key, value in rows}


def set_preference(key, value):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO user_preferences (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now))


def log_action(action_id, action_type, details, status):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO actions_log (action_id, action_type, details, status, executed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(action_id) DO UPDATE SET status = excluded.status, executed_at = excluded.executed_at
        """, (action_id, action_type, details, status, now))


def update_action_status(action_id, status):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE actions_log SET status = ?, executed_at = ? WHERE action_id = ?",
            (status, now, action_id),
        )


def delete_messages(conversation_id):
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))


def save_message(conversation_id, role, text):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, text, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, text, now),
        )


def get_messages(conversation_id):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, text FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    return [{"role": row[0], "text": row[1]} for row in rows]
