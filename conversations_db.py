import os
from datetime import datetime, timezone

import psycopg2

DATABASE_URL = os.environ.get('DATABASE_URL')


def _connect():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    pinned INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS current_session (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TEXT
                )
            """)
        conn.commit()


def create_conversation(conversation_id, title="Nueva conversacion"):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, title, pinned, created_at, updated_at) VALUES (%s, %s, 0, %s, %s)",
                (conversation_id, title, now, now),
            )
        conn.commit()


def exists(conversation_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
    return row is not None


def get_all():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, pinned FROM conversations ORDER BY pinned DESC, created_at DESC"
            )
            rows = cur.fetchall()
    return [{"id": row[0], "title": row[1], "pinned": bool(row[2])} for row in rows]


def get_title(conversation_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
    return row[0] if row else None


def update_title(conversation_id, title):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
                (title, now, conversation_id),
            )
        conn.commit()


def toggle_pinned(conversation_id):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pinned FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
            new_value = 0 if row[0] else 1
            cur.execute(
                "UPDATE conversations SET pinned = %s, updated_at = %s WHERE id = %s",
                (new_value, now, conversation_id),
            )
        conn.commit()
    return bool(new_value)


def delete_conversation(conversation_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
        conn.commit()


def get_current_session():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT session_id FROM current_session WHERE id = 1")
            row = cur.fetchone()
    return row[0] if row else None


def set_current_session(session_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO current_session (id, session_id) VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET session_id = excluded.session_id
            """, (session_id,))
        conn.commit()


def save_message(message_id, session_id, role, content):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s)",
                (message_id, session_id, role, content, now),
            )
        conn.commit()


def get_messages(session_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,),
            )
            rows = cur.fetchall()
    return [{"role": row[0], "text": row[1]} for row in rows]


def delete_messages(session_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
        conn.commit()
