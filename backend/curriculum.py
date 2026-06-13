"""Mandarin Tutor — curriculum (0 -> conversational) + SQLite persistence.

A structured learning path: Units -> Lessons -> Items. Each item is a word or
short phrase with hanzi, pinyin, English gloss, and the target tone
of its FIRST syllable (used by the /assess pronunciation drill).

The SQLite DB also holds progress + achievements (wired in a later phase), but
the schema is created here so everything lives in one place.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tutor.db")


# ---------------------------------------------------------------------------
# Curriculum content
# ---------------------------------------------------------------------------
# Each item: (hanzi, pinyin, gloss, tone)  -- tone = target tone of 1st syllable
# Lessons are ordered; a learner unlocks the next lesson by completing the
# current one (completion logic lives in the progress phase).

CURRICULUM = [
    {
        "id": "u1",
        "title": "Unit 1 — Greetings & the 4 Tones",
        "desc": "Start from zero: learn the 4 Mandarin tones through greeting words.",
        "lessons": [
            {
                "id": "u1l1",
                "title": "你好 — Hello",
                "goal": "Most basic greeting + feel tones 3 & 2.",
                "items": [
                    ("你", "nǐ", "you (tone 3)", 3),
                    ("好", "hǎo", "good (tone 3)", 3),
                    ("你好", "nǐ hǎo", "hello (tone 3)", 3),
                    ("您", "nín", "you (polite) (tone 2)", 2),
                ],
            },
            {
                "id": "u1l2",
                "title": "谢谢 — Thank you",
                "goal": "Polite expressions + tone 4.",
                "items": [
                    ("谢", "xiè", "thanks (tone 4)", 4),
                    ("谢谢", "xiè xie", "thank you (tone 4)", 4),
                    ("不", "bù", "not (tone 4)", 4),
                    ("对不起", "duì bu qǐ", "sorry (tone 4)", 4),
                ],
            },
            {
                "id": "u1l3",
                "title": "妈麻马骂 — 4 Tones",
                "goal": "Classic quartet: 1 syllable 'ma', 4 different tones.",
                "items": [
                    ("妈", "mā", "mother (tone 1)", 1),
                    ("麻", "má", "hemp (tone 2)", 2),
                    ("马", "mǎ", "horse (tone 3)", 3),
                    ("骂", "mà", "scold (tone 4)", 4),
                ],
            },
        ],
    },
    {
        "id": "u2",
        "title": "Unit 2 — Numbers 1-10",
        "desc": "Basic counting — foundation for prices, time, and age.",
        "lessons": [
            {
                "id": "u2l1",
                "title": "一二三四五 — 1 to 5",
                "goal": "The first five numbers.",
                "items": [
                    ("一", "yī", "one (tone 1)", 1),
                    ("二", "èr", "two (tone 4)", 4),
                    ("三", "sān", "three (tone 1)", 1),
                    ("四", "sì", "four (tone 4)", 4),
                    ("五", "wǔ", "five (tone 3)", 3),
                ],
            },
            {
                "id": "u2l2",
                "title": "六七八九十 — 6 to 10",
                "goal": "The next five numbers.",
                "items": [
                    ("六", "liù", "six (tone 4)", 4),
                    ("七", "qī", "seven (tone 1)", 1),
                    ("八", "bā", "eight (tone 1)", 1),
                    ("九", "jiǔ", "nine (tone 3)", 3),
                    ("十", "shí", "ten (tone 2)", 2),
                ],
            },
        ],
    },
    {
        "id": "u3",
        "title": "Unit 3 — Introducing Yourself",
        "desc": "Talk about your name and origin — your first real conversation.",
        "lessons": [
            {
                "id": "u3l1",
                "title": "我叫… — My name is…",
                "goal": "Say your own name.",
                "items": [
                    ("我", "wǒ", "I (tone 3)", 3),
                    ("叫", "jiào", "called (tone 4)", 4),
                    ("名字", "míng zi", "name (tone 2)", 2),
                    ("我叫", "wǒ jiào", "my name is (tone 3)", 3),
                ],
            },
            {
                "id": "u3l2",
                "title": "你是哪国人 — Where are you from",
                "goal": "Ask and answer where someone is from.",
                "items": [
                    ("是", "shì", "to be (tone 4)", 4),
                    ("人", "rén", "person (tone 2)", 2),
                    ("中国", "zhōng guó", "China (tone 1)", 1),
                    ("印尼", "yìn ní", "Indonesia (tone 4)", 4),
                ],
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Curriculum access helpers
# ---------------------------------------------------------------------------

def curriculum_outline() -> list[dict]:
    """Units + lessons without item bodies (for the lesson-list screen)."""
    out = []
    for unit in CURRICULUM:
        out.append({
            "id": unit["id"],
            "title": unit["title"],
            "desc": unit["desc"],
            "lessons": [
                {"id": l["id"], "title": l["title"], "goal": l["goal"],
                 "count": len(l["items"])}
                for l in unit["lessons"]
            ],
        })
    return out


def get_lesson(lesson_id: str) -> dict | None:
    """Full lesson with items expanded to dicts."""
    for unit in CURRICULUM:
        for l in unit["lessons"]:
            if l["id"] == lesson_id:
                return {
                    "id": l["id"],
                    "title": l["title"],
                    "goal": l["goal"],
                    "unit_id": unit["id"],
                    "unit_title": unit["title"],
                    "items": [
                        {"hanzi": hz, "pinyin": py, "gloss": gl, "tone": tn}
                        for (hz, py, gl, tn) in l["items"]
                    ],
                }
    return None


def all_lesson_ids() -> list[str]:
    """Flat ordered list of every lesson id (used for unlock ordering)."""
    ids = []
    for unit in CURRICULUM:
        for l in unit["lessons"]:
            ids.append(l["id"])
    return ids


# ---------------------------------------------------------------------------
# SQLite persistence (progress + achievements)
# ---------------------------------------------------------------------------

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if missing. Safe to call on every startup."""
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lesson_progress (
                user_id    TEXT NOT NULL DEFAULT 'default',
                lesson_id  TEXT NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                best_avg   INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT NOT NULL DEFAULT 'default',
                lesson_id TEXT,
                hanzi     TEXT,
                target_tone INTEGER,
                score     INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS achievements (
                user_id   TEXT NOT NULL DEFAULT 'default',
                badge     TEXT NOT NULL,
                earned_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, badge)
            );

            CREATE TABLE IF NOT EXISTS streak (
                user_id   TEXT PRIMARY KEY DEFAULT 'default',
                current   INTEGER NOT NULL DEFAULT 0,
                longest   INTEGER NOT NULL DEFAULT 0,
                last_day  TEXT
            );
            """
        )


# ---------------------------------------------------------------------------
# Progress / streak / achievements
# ---------------------------------------------------------------------------

# Badges: id -> (label, description). Earned when the predicate in award logic holds.
BADGES = {
    "first_word":   ("🎤 First Word", "Scored your first pronunciation."),
    "perfect_tone": ("🎯 Perfect Tone", "Got 90+ on a single word."),
    "lesson_done":  ("📘 Lesson Complete", "Finished a full lesson."),
    "ten_attempts": ("🔥 Dedicated", "Practiced 10 times."),
    "streak_3":     ("📅 3-Day Streak", "Practiced 3 days in a row."),
}


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def record_attempt(hanzi: str, target_tone: int, score: int,
                   lesson_id: str | None = None, user_id: str = "default") -> dict:
    """Persist one drill attempt, bump streak, award badges. Returns new badges."""
    with db() as conn:
        conn.execute(
            "INSERT INTO attempts (user_id, lesson_id, hanzi, target_tone, score) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, lesson_id, hanzi, target_tone, score),
        )
        new_badges = _update_streak_and_badges(conn, user_id, score)
    return {"new_badges": new_badges}


def _update_streak_and_badges(conn, user_id: str, score: int) -> list[dict]:
    today = _today()
    row = conn.execute(
        "SELECT current, longest, last_day FROM streak WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        cur, longest, last = 1, 1, today
    else:
        last = row["last_day"]
        if last == today:
            cur, longest = row["current"], row["longest"]
        else:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            cur = row["current"] + 1 if last == yesterday else 1
            longest = max(row["longest"], cur)
            last = today
    conn.execute(
        "INSERT INTO streak (user_id, current, longest, last_day) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET current=?, longest=?, last_day=?",
        (user_id, cur, longest, last, cur, longest, last),
    )

    earned = {r["badge"] for r in conn.execute(
        "SELECT badge FROM achievements WHERE user_id = ?", (user_id,)).fetchall()}
    total = conn.execute(
        "SELECT COUNT(*) c FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["c"]

    to_award = []
    if "first_word" not in earned and total >= 1:
        to_award.append("first_word")
    if "perfect_tone" not in earned and score >= 90:
        to_award.append("perfect_tone")
    if "ten_attempts" not in earned and total >= 10:
        to_award.append("ten_attempts")
    if "streak_3" not in earned and cur >= 3:
        to_award.append("streak_3")

    new_badges = []
    for b in to_award:
        conn.execute(
            "INSERT OR IGNORE INTO achievements (user_id, badge) VALUES (?, ?)",
            (user_id, b))
        label, desc = BADGES[b]
        new_badges.append({"id": b, "label": label, "desc": desc})
    return new_badges


def complete_lesson(lesson_id: str, best_avg: int, user_id: str = "default") -> dict:
    """Mark a lesson complete; award lesson_done badge on first completion."""
    with db() as conn:
        conn.execute(
            "INSERT INTO lesson_progress (user_id, lesson_id, completed, best_avg, updated_at) "
            "VALUES (?, ?, 1, ?, datetime('now')) "
            "ON CONFLICT(user_id, lesson_id) DO UPDATE SET completed=1, "
            "best_avg=MAX(best_avg, ?), updated_at=datetime('now')",
            (user_id, lesson_id, best_avg, best_avg),
        )
        earned = {r["badge"] for r in conn.execute(
            "SELECT badge FROM achievements WHERE user_id = ?", (user_id,)).fetchall()}
        new_badges = []
        if "lesson_done" not in earned:
            conn.execute(
                "INSERT OR IGNORE INTO achievements (user_id, badge) VALUES (?, 'lesson_done')",
                (user_id,))
            label, desc = BADGES["lesson_done"]
            new_badges.append({"id": "lesson_done", "label": label, "desc": desc})
    return {"new_badges": new_badges}


def progress_summary(user_id: str = "default") -> dict:
    """Everything the UI needs: streak, totals, done lessons, badges."""
    with db() as conn:
        srow = conn.execute(
            "SELECT current, longest, last_day FROM streak WHERE user_id = ?",
            (user_id,)).fetchone()
        total = conn.execute(
            "SELECT COUNT(*) c FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["c"]
        avg = conn.execute(
            "SELECT AVG(score) a FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["a"]
        done = [r["lesson_id"] for r in conn.execute(
            "SELECT lesson_id FROM lesson_progress WHERE user_id = ? AND completed = 1",
            (user_id,)).fetchall()]
        badge_ids = [r["badge"] for r in conn.execute(
            "SELECT badge FROM achievements WHERE user_id = ? ORDER BY earned_at",
            (user_id,)).fetchall()]
    badges = [{"id": b, "label": BADGES[b][0], "desc": BADGES[b][1]}
              for b in badge_ids if b in BADGES]
    return {
        "streak": {"current": srow["current"] if srow else 0,
                   "longest": srow["longest"] if srow else 0,
                   "last_day": srow["last_day"] if srow else None},
        "total_attempts": total,
        "avg_score": round(avg) if avg is not None else 0,
        "done_lessons": done,
        "badges": badges,
        "all_badges": [{"id": k, "label": v[0], "desc": v[1]} for k, v in BADGES.items()],
    }
