"""Gamification layer — XP, levels, hearts, daily challenge, badges.

Tables:
  user_state(user_id, xp, level, hearts, last_active)
  xp_log(id, user_id, amount, reason, created_at)
  daily_challenge(user_id, date, items_json, completed_json)

Streak is read from curriculum.streak (single source of truth).
Badges extend curriculum.BADGES via EXTRA_BADGES dict here.
"""
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import curriculum as curr

DB_PATH = os.environ.get("DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tutor.db"
)

# XP awards
XP_TONE_PASS = 10
XP_WRITE_PASS = 8
XP_RECALL_PASS = 15
XP_CHALLENGE_ITEM = 20
XP_LESSON_DONE = 50

# XP needed to reach level N = LEVEL_BASE * N^2
LEVEL_BASE = 100

# Hearts (soft lives) — reset daily
MAX_HEARTS = 5

EXTRA_BADGES = {
    "level_5":       ("⭐ Level 5", "Reached level 5."),
    "level_10":      ("🌟 Level 10", "Reached level 10."),
    "challenge_3":   ("🏆 3-Day Challenger", "Completed daily challenge 3 days in a row."),
    "no_miss_week":  ("💎 Flawless Week", "7-day streak with no hearts lost."),
    "srs_10":        ("🔁 SRS Veteran", "Reviewed 10 SRS cards."),
}


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
    """Create gamification tables if missing. Safe to call every startup."""
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_state (
                user_id     TEXT PRIMARY KEY DEFAULT 'default',
                xp          INTEGER NOT NULL DEFAULT 0,
                level       INTEGER NOT NULL DEFAULT 1,
                hearts      INTEGER NOT NULL DEFAULT 5,
                last_active TEXT
            );

            CREATE TABLE IF NOT EXISTS xp_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL DEFAULT 'default',
                amount     INTEGER NOT NULL,
                reason     TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS daily_challenge (
                user_id    TEXT NOT NULL DEFAULT 'default',
                date       TEXT NOT NULL,
                items_json TEXT NOT NULL DEFAULT '[]',
                done_json  TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (user_id, date)
            );
        """)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _xp_for_level(level: int) -> int:
    """Total XP needed to reach `level`."""
    return LEVEL_BASE * (level ** 2)


def _level_for_xp(xp: int) -> int:
    """Current level given total XP."""
    level = 1
    while _xp_for_level(level + 1) <= xp:
        level += 1
    return level


def award_xp(reason: str, amount: int = XP_TONE_PASS,
             user_id: str = "default") -> dict:
    """Credit XP, recalculate level, persist. Returns updated state snippet."""
    with _db() as conn:
        row = conn.execute(
            "SELECT xp, level, hearts FROM user_state WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        old_xp = row["xp"] if row else 0
        old_level = row["level"] if row else 1
        hearts = row["hearts"] if row else MAX_HEARTS

        new_xp = old_xp + amount
        new_level = _level_for_xp(new_xp)

        conn.execute(
            "INSERT INTO user_state (user_id, xp, level, hearts, last_active) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET xp=?, level=?, last_active=?",
            (user_id, new_xp, new_level, hearts, _today(),
             new_xp, new_level, _today()),
        )
        conn.execute(
            "INSERT INTO xp_log (user_id, amount, reason) VALUES (?, ?, ?)",
            (user_id, amount, reason),
        )
        new_badges = _check_level_badges(conn, user_id, old_level, new_level)

    return {"xp": new_xp, "level": new_level, "xp_gained": amount,
            "leveled_up": new_level > old_level, "new_badges": new_badges}


def _check_level_badges(conn, user_id: str, old_level: int,
                         new_level: int) -> list[dict]:
    earned = {r["badge"] for r in conn.execute(
        "SELECT badge FROM achievements WHERE user_id = ?",
        (user_id,)).fetchall()}
    to_award = []
    if new_level >= 5 and "level_5" not in earned:
        to_award.append("level_5")
    if new_level >= 10 and "level_10" not in earned:
        to_award.append("level_10")

    new_badges = []
    for b in to_award:
        conn.execute(
            "INSERT OR IGNORE INTO achievements (user_id, badge) VALUES (?, ?)",
            (user_id, b))
        label, desc = EXTRA_BADGES[b]
        new_badges.append({"id": b, "label": label, "desc": desc})
    return new_badges


def get_state(user_id: str = "default") -> dict:
    """Return full gamification state for /gamification/state endpoint."""
    all_badges = {**curr.BADGES, **EXTRA_BADGES}
    with _db() as conn:
        state_row = conn.execute(
            "SELECT xp, level, hearts, last_active FROM user_state "
            "WHERE user_id = ?", (user_id,)
        ).fetchone()
        streak_row = conn.execute(
            "SELECT current, longest, last_day FROM streak "
            "WHERE user_id = ?", (user_id,)
        ).fetchone()
        badge_ids = [r["badge"] for r in conn.execute(
            "SELECT badge FROM achievements WHERE user_id = ? ORDER BY earned_at",
            (user_id,)).fetchall()]

    xp = state_row["xp"] if state_row else 0
    level = state_row["level"] if state_row else 1
    hearts = state_row["hearts"] if state_row else MAX_HEARTS
    streak = streak_row["current"] if streak_row else 0

    next_level_xp = _xp_for_level(level + 1)
    cur_level_xp = _xp_for_level(level - 1) if level > 1 else 0
    badges = [{"id": b, "label": all_badges[b][0], "desc": all_badges[b][1]}
              for b in badge_ids if b in all_badges]
    return {
        "xp": xp,
        "level": level,
        "xp_to_next": max(0, next_level_xp - xp),
        "level_progress_pct": min(100, round(
            (xp - cur_level_xp) / max(1, next_level_xp - cur_level_xp) * 100)),
        "hearts": hearts,
        "streak": streak,
        "badges": badges,
    }


def _pick_challenge_items(user_id: str, n: int = 5) -> list[str]:
    """Pick N item_keys for today's challenge: due SRS first, else random vocab."""
    import srs as srs_mod
    due = [c["item_key"] for c in srs_mod.due_items(user_id, limit=n)]
    if len(due) >= n:
        return due[:n]

    # Fill remainder from weak tone attempts
    needed = n - len(due)
    with _db() as conn:
        rows = conn.execute(
            "SELECT hanzi FROM attempts WHERE user_id = ? "
            "GROUP BY hanzi ORDER BY MAX(score) ASC LIMIT ?",
            (user_id, needed * 3),
        ).fetchall()
    weak = [r["hanzi"] for r in rows if r["hanzi"] not in due]

    result = due + weak[:needed]
    if len(result) < n:
        # Fall back: random curriculum items
        all_items = [
            item[0]
            for unit in curr.CURRICULUM
            for lesson in unit["lessons"]
            for item in lesson["items"]
        ]
        random.shuffle(all_items)
        for hz in all_items:
            if hz not in result:
                result.append(hz)
            if len(result) >= n:
                break
    return result[:n]


def get_or_create_challenge(user_id: str = "default") -> dict:
    """Return today's challenge, generating it on first call of the day."""
    today = _today()
    with _db() as conn:
        row = conn.execute(
            "SELECT items_json, done_json FROM daily_challenge "
            "WHERE user_id = ? AND date = ?", (user_id, today)
        ).fetchone()
        if row:
            items = json.loads(row["items_json"])
            done = json.loads(row["done_json"])
        else:
            items = _pick_challenge_items(user_id)
            done = []
            conn.execute(
                "INSERT INTO daily_challenge (user_id, date, items_json, done_json) "
                "VALUES (?, ?, ?, ?)",
                (user_id, today, json.dumps(items), json.dumps(done)),
            )
    return {
        "date": today,
        "items": items,
        "done": done,
        "total": len(items),
        "completed": len(done),
        "finished": len(done) >= len(items) and len(items) > 0,
    }


def complete_challenge_item(item_key: str,
                             user_id: str = "default") -> dict:
    """Mark one challenge item done; award XP. Returns updated challenge + xp."""
    today = _today()
    challenge = get_or_create_challenge(user_id)
    done = list(challenge["done"])

    if item_key not in challenge["items"]:
        return {**challenge, "error": "item_key not in today's challenge"}
    if item_key in done:
        return {**challenge, "already_done": True}

    done.append(item_key)
    with _db() as conn:
        conn.execute(
            "UPDATE daily_challenge SET done_json = ? "
            "WHERE user_id = ? AND date = ?",
            (json.dumps(done), user_id, today),
        )

    xp_result = award_xp("challenge_item", XP_CHALLENGE_ITEM, user_id)
    challenge["done"] = done
    challenge["completed"] = len(done)
    challenge["finished"] = len(done) >= len(challenge["items"])
    return {**challenge, "xp": xp_result}
