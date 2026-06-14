"""SRS (Spaced Repetition System) — pure-Python SM-2 implementation.

Table: srs_cards(user_id, item_key, ease, interval, due, reps, lapses, last_review)
item_key: hanzi character or lesson item id

Rating scale (Anki-compatible):
  1 = Again  — complete blackout, reset interval
  2 = Hard   — significant difficulty
  3 = Good   — correct with effort
  4 = Easy   — perfect recall

No AGPL deps — algorithm derived from published SM-2 spec.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tutor.db")

DEFAULT_EASE = 2.5
MIN_EASE = 1.3


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create srs_cards table if missing. Safe to call on every startup."""
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS srs_cards (
                user_id     TEXT NOT NULL DEFAULT 'default',
                item_key    TEXT NOT NULL,
                ease        REAL NOT NULL DEFAULT 2.5,
                interval    INTEGER NOT NULL DEFAULT 1,
                due         TEXT NOT NULL DEFAULT (date('now')),
                reps        INTEGER NOT NULL DEFAULT 0,
                lapses      INTEGER NOT NULL DEFAULT 0,
                last_review TEXT,
                PRIMARY KEY (user_id, item_key)
            );
        """)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def review(item_key: str, rating: int, user_id: str = "default") -> dict:
    """Apply one SM-2 review and persist updated schedule.

    Returns the updated card state dict with next due date.
    """
    rating = max(1, min(4, int(rating)))
    today = _today()

    with _db() as conn:
        row = conn.execute(
            "SELECT ease, interval, reps, lapses FROM srs_cards "
            "WHERE user_id = ? AND item_key = ?",
            (user_id, item_key),
        ).fetchone()

        if row is None:
            ease, interval, reps, lapses = DEFAULT_EASE, 1, 0, 0
        else:
            ease = float(row["ease"])
            interval = int(row["interval"])
            reps = int(row["reps"])
            lapses = int(row["lapses"])

        # SM-2 core update
        if rating == 1:  # Again — reset
            reps = 0
            lapses += 1
            new_interval = 1
            new_ease = max(MIN_EASE, ease - 0.20)
        else:
            # Interval progression: 1 → 6 → ease*prev
            if reps == 0:
                new_interval = 1
            elif reps == 1:
                new_interval = 6
            else:
                new_interval = max(1, round(interval * ease))
            # Ease adjustment per SM-2: hard lowers, easy raises
            delta = 0.1 - (4 - rating) * (0.08 + (4 - rating) * 0.02)
            new_ease = max(MIN_EASE, ease + delta)
            reps += 1

        due_date = (
            datetime.now(timezone.utc) + timedelta(days=new_interval)
        ).strftime("%Y-%m-%d")

        conn.execute(
            """INSERT INTO srs_cards
               (user_id, item_key, ease, interval, due, reps, lapses, last_review)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, item_key) DO UPDATE SET
                 ease=excluded.ease, interval=excluded.interval, due=excluded.due,
                 reps=excluded.reps, lapses=excluded.lapses,
                 last_review=excluded.last_review""",
            (user_id, item_key, new_ease, new_interval, due_date, reps, lapses, today),
        )

    return {
        "item_key": item_key,
        "ease": round(new_ease, 3),
        "interval": new_interval,
        "due": due_date,
        "reps": reps,
        "lapses": lapses,
    }


def due_items(user_id: str = "default", limit: int = 20) -> list[dict]:
    """Return cards due today or overdue, ordered by due date (oldest first)."""
    today = _today()
    with _db() as conn:
        rows = conn.execute(
            "SELECT item_key, ease, interval, due, reps, lapses, last_review "
            "FROM srs_cards WHERE user_id = ? AND due <= ? "
            "ORDER BY due ASC LIMIT ?",
            (user_id, today, limit),
        ).fetchall()
    return [dict(r) for r in rows]
