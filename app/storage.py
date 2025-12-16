from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    voiceprint BLOB
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    folder TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    question_id INTEGER,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER,
    label TEXT,
    notes TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS labels_over_time (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp_ms INTEGER NOT NULL,
    score REAL,
    label TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
"""


@dataclass
class User:
    id: int
    full_name: str
    voiceprint: bytes | None = None


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(DB_SCHEMA)

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            cur = conn.execute("SELECT id, full_name, voiceprint FROM users ORDER BY full_name")
            return [User(*row) for row in cur.fetchall()]

    def create_user(self, full_name: str, voiceprint: bytes | None = None) -> User:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users(full_name, voiceprint) VALUES (?, ?)",
                (full_name, voiceprint),
            )
            conn.commit()
            return User(cur.lastrowid, full_name, voiceprint)

    def update_voiceprint(self, user_id: int, voiceprint: bytes) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET voiceprint=? WHERE id=?",
                (voiceprint, user_id),
            )
            conn.commit()

    def create_session(self, user_id: int, folder: Path, started_at: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sessions(user_id, folder, started_at) VALUES (?, ?, ?)",
                (user_id, str(folder), started_at),
            )
            conn.commit()
            return cur.lastrowid

    def finish_session(self, session_id: int, finished_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET finished_at=? WHERE id=?",
                (finished_at, session_id),
            )
            conn.commit()

    def add_question(self, session_id: int, text: str, source: str = "manual") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO questions(session_id, text, source) VALUES (?, ?, ?)",
                (session_id, text, source),
            )
            conn.commit()
            return cur.lastrowid

    def add_segment(
        self,
        session_id: int,
        type_: str,
        start_ms: int,
        end_ms: int | None,
        label: str | None = None,
        question_id: int | None = None,
        notes: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO segments(session_id, type, question_id, start_ms, end_ms, label, notes)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, type_, question_id, start_ms, end_ms, label, notes),
            )
            conn.commit()
            return cur.lastrowid

    def close_segment(self, segment_id: int, end_ms: int):
        with self._connect() as conn:
            conn.execute(
                "UPDATE segments SET end_ms=? WHERE id=?",
                (end_ms, segment_id),
            )
            conn.commit()

    def log_label(self, session_id: int, timestamp_ms: int, score: float, label: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO labels_over_time(session_id, timestamp_ms, score, label) VALUES (?, ?, ?, ?)",
                (session_id, timestamp_ms, score, label),
            )
            conn.commit()
