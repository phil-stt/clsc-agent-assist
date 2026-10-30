"""Call state and the event log, in SQLite.

One row per call session; the demo uses a single session. The event log is
append-only: every AI proposal, block and human decision lands here, so a later
call-scoring pass has the same record the agent saw.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "var" / "state.db"
SESSION = "demo"

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    beat INTEGER NOT NULL DEFAULT 0,
    playing INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL,
    at TEXT NOT NULL,
    beat INTEGER NOT NULL,
    actor TEXT NOT NULL,      -- ai | agent | system
    tone TEXT NOT NULL,       -- blue (AI proposes) | green (human decision) | amber (block or nudge) | plain
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}'
);
"""


def db_path() -> Path:
    return Path(os.environ.get("CLSC_DB", DEFAULT_DB))


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def empty() -> dict:
    return {"marks": {}, "decisions": {}, "detections": {}}


def load(session: str = SESSION) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM session WHERE id = ?", (session,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO session (id, data) VALUES (?, ?)", (session, json.dumps(empty())))
            return {"id": session, "beat": 0, "playing": False, **empty()}
        return {"id": session, "beat": row["beat"], "playing": bool(row["playing"]), **json.loads(row["data"])}


def save(state: dict) -> None:
    data = {k: state[k] for k in ("marks", "decisions", "detections")}
    with connect() as conn:
        conn.execute("UPDATE session SET beat = ?, playing = ?, data = ? WHERE id = ?",
                     (state["beat"], int(state["playing"]), json.dumps(data), state["id"]))


def reset(session: str = SESSION) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM session WHERE id = ?", (session,))
        conn.execute("DELETE FROM events WHERE session = ?", (session,))
    return load(session)


def log(state: dict, actor: str, tone: str, kind: str, text: str, **data) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO events (session, at, beat, actor, tone, kind, text, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (state["id"], datetime.now(timezone.utc).isoformat(timespec="seconds"), state["beat"],
             actor, tone, kind, text, json.dumps(data, default=str)))


def events(session: str = SESSION) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM events WHERE session = ? ORDER BY id", (session,)).fetchall()
    return [dict(r) | {"data": json.loads(r["data"])} for r in rows]
