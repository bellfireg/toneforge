"""Mandarin Tutor backend — FastAPI app."""
import json
import os
import re
import subprocess
import tempfile
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from faster_whisper import WhisperModel

# Load backend/.env (next to this file) so config works for both `uvicorn app:app`
# and the systemd unit. Optional: app runs fine with no .env (chat tab aside).
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

import tone as tone_engine
import curriculum as curr
import srs as srs_mod
import gamification as gami

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")

# ---------------------------------------------------------------------------
# Whisper model — loaded once at startup, shared across requests
# ---------------------------------------------------------------------------
whisper_model: WhisperModel | None = None

# Chat LLM endpoint — OpenAI-compatible. Configurable via env so anyone can
# point it at their own provider. Default = local Ollama ($0, no API key).
#   CHAT_BASE_URL : base URL of an OpenAI-compatible API (no trailing /v1)
#   CHAT_MODEL    : model name to request
#   CHAT_API_KEY  : optional bearer token (leave empty for local Ollama)
CHAT_BASE_URL = os.environ.get("CHAT_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
ROUTER_URL = CHAT_BASE_URL + "/v1/chat/completions"
ROUTER_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:7b")
CHAT_API_KEY = os.environ.get("CHAT_API_KEY", "").strip()
# edge-tts binary: env-overridable so it works in Docker (PATH) and host (~/.local/bin)
EDGE_TTS_BIN = os.environ.get("EDGE_TTS_BIN") or (
    os.path.expanduser("~/.local/bin/edge-tts")
    if os.path.exists(os.path.expanduser("~/.local/bin/edge-tts"))
    else "edge-tts"
)

SYSTEM_PROMPT = (
    "You are a friendly Mandarin Chinese tutor for absolute beginners. "
    "The student will speak or type in Mandarin (or attempt to). "
    "Reply naturally in simple Mandarin, keep it SHORT (1-2 sentences). "
    "Gently correct errors. "
    "Respond with ONLY a JSON object — no markdown, no extra text:\n"
    '{"reply_zh": "<Mandarin reply>", "pinyin": "<pinyin for reply_zh>", '
    '"reply_en": "<English translation>", "correction": "<brief correction or empty string>"}'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load Whisper once on startup; release on shutdown."""
    global whisper_model
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    curr.init_db()
    srs_mod.init_db()
    gami.init_db()
    yield


app = FastAPI(title="Mandarin Tutor API", version="0.1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    history: list[dict]
    user_text: str


class TTSRequest(BaseModel):
    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"


class AssessResponse(BaseModel):
    """Result of a single-syllable pronunciation drill."""
    transcript: str
    target_tone: int
    detected_tone: int | None
    score: int
    feedback: str
    ok: bool
    reason: str = ""
    new_badges: list[dict] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_json(raw: str) -> dict:
    """Strip markdown fences and return the first {...} JSON block."""
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in LLM response: {raw[:300]}")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness probe."""
    return {"ok": True}


@app.post("/stt")
async def speech_to_text(file: UploadFile):
    """Transcribe an uploaded audio file with faster-whisper (Chinese)."""
    if whisper_model is None:
        raise HTTPException(503, "Whisper model not ready")

    audio_bytes = await file.read()
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments, _ = whisper_model.transcribe(tmp_path, language="zh")
        text = "".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)

    return {"text": text}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Send a student turn to 9router/Claude; return structured tutor reply."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.user_text})

    payload = {"model": ROUTER_MODEL, "messages": messages, "stream": False}
    headers = {"Authorization": f"Bearer {CHAT_API_KEY}"} if CHAT_API_KEY else {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(ROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                503,
                "Chat LLM is not reachable. The tutor chat needs an OpenAI-compatible "
                "endpoint. Set CHAT_BASE_URL / CHAT_MODEL / CHAT_API_KEY in backend/.env "
                "(default expects a local Ollama at http://127.0.0.1:11434). "
                "All other features (tone drill, writing, curriculum, progress) work without it. "
                f"[{type(exc).__name__}]",
            ) from exc

    raw_content = resp.json()["choices"][0]["message"]["content"]

    try:
        parsed = extract_json(raw_content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f"Could not parse tutor JSON: {exc}") from exc

    updated_history = list(req.history)
    updated_history.append({"role": "user", "content": req.user_text})
    updated_history.append({"role": "assistant", "content": raw_content})

    return {**parsed, "history": updated_history}


@app.post("/tts")
async def text_to_speech(req: TTSRequest):
    """Synthesize Mandarin speech via edge-tts; return mp3."""
    tmp_path = tempfile.mktemp(suffix=".mp3")

    try:
        result = subprocess.run(
            [EDGE_TTS_BIN, "--voice", req.voice, "--text", req.text,
             "--write-media", tmp_path],
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "edge-tts timed out") from exc
    except FileNotFoundError as exc:
        raise HTTPException(500, f"edge-tts not found at {EDGE_TTS_BIN}") from exc

    if result.returncode != 0:
        raise HTTPException(500, f"edge-tts failed: {result.stderr.decode()}")

    # FileResponse streams the file; the temp file is cleaned up after send
    return FileResponse(tmp_path, media_type="audio/mpeg", filename="reply.mp3")


@app.post("/assess", response_model=AssessResponse)
async def assess(file: UploadFile, target_pinyin: str = "", target_tone: int = 0,
                 hanzi: str = "", lesson_id: str = ""):
    """Pronunciation drill: score a learner's tone on a single target syllable.

    The caller supplies the expected syllable as `target_pinyin` (e.g. "nǐ" or
    "ni3") OR an explicit `target_tone` (1-4). We transcribe with Whisper for a
    sanity check, then score the pitch contour against the target tone profile.
    """
    if whisper_model is None:
        raise HTTPException(503, "Whisper model not ready")

    tone_num = target_tone or tone_engine.pinyin_tone(target_pinyin)
    if not 1 <= tone_num <= 4:
        raise HTTPException(400, "Provide target_tone (1-4) or a marked target_pinyin")

    audio_bytes = await file.read()
    suffix = os.path.splitext(file.filename or "a.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        src_path = tmp.name

    wav_path = None
    try:
        segments, _ = whisper_model.transcribe(src_path, language="zh")
        transcript = "".join(seg.text for seg in segments).strip()

        wav_path = tone_engine.to_wav(src_path)
        result = tone_engine.score_tone(wav_path, tone_num)
    finally:
        for p in (src_path, wav_path):
            if p and os.path.exists(p):
                os.unlink(p)

    # Persist the attempt (best-effort; never break scoring if DB hiccups).
    new_badges = []
    try:
        rec = curr.record_attempt(
            hanzi=hanzi or target_pinyin, target_tone=tone_num,
            score=result["score"], lesson_id=lesson_id or None)
        new_badges = rec.get("new_badges", [])
    except Exception:
        pass

    return AssessResponse(
        transcript=transcript,
        target_tone=tone_num,
        detected_tone=result.get("detected_tone"),
        score=result["score"],
        feedback=tone_engine.tone_feedback(result["score"]),
        ok=result["ok"],
        reason=result.get("reason", ""),
        new_badges=new_badges,
    )


@app.get("/progress")
async def get_progress():
    """Streak, totals, completed lessons, and earned badges for the UI."""
    return curr.progress_summary()


class LessonCompleteRequest(BaseModel):
    lesson_id: str
    best_avg: int = 0


@app.post("/lesson-complete")
async def lesson_complete(req: LessonCompleteRequest):
    """Mark a lesson complete and award the lesson badge on first completion."""
    return curr.complete_lesson(req.lesson_id, req.best_avg)


@app.get("/curriculum")
async def curriculum():
    """Units + lessons outline annotated with progress + unlock state."""
    return {"units": curr.curriculum_status()}


@app.get("/lesson-scores/{lesson_id}")
async def lesson_scores(lesson_id: str):
    """Best score per syllable + completion stats for a single lesson."""
    return curr.lesson_item_scores(lesson_id)


class WriteAttemptRequest(BaseModel):
    hanzi: str
    mode: str = "trace"          # 'trace' | 'recall'
    score: int = 0              # 0..100 stroke accuracy from Hanzi Writer quiz
    mistakes: int = 0
    lesson_id: str = ""


class SrsReviewRequest(BaseModel):
    item_key: str
    rating: int              # 1=Again 2=Hard 3=Good 4=Easy


class ChallengeCompleteRequest(BaseModel):
    item_key: str


class RecallAssessRequest(BaseModel):
    lesson_id: str
    prompt_id: str           # numeric index "0","1".. or prompt_en text
    mode: str = "writing"   # 'writing' | 'voice'
    payload: str = ""       # hanzi text attempt (client does STT for voice)


@app.post("/write-assess")
async def write_assess(req: WriteAttemptRequest):
    """Record a handwriting (stroke) attempt scored client-side by Hanzi Writer."""
    score = max(0, min(100, int(req.score)))
    return curr.record_writing_attempt(
        hanzi=req.hanzi, mode=req.mode, score=score,
        mistakes=max(0, int(req.mistakes)), lesson_id=req.lesson_id or None)


@app.get("/writing-scores/{lesson_id}")
async def writing_scores(lesson_id: str):
    """Best WRITING score per syllable + completion stats for one lesson."""
    return curr.lesson_writing_scores(lesson_id)


@app.get("/lesson/{lesson_id}")
async def lesson(lesson_id: str):
    """Full lesson content (items with hanzi/pinyin/gloss/tone)."""
    data = curr.get_lesson(lesson_id)
    if data is None:
        raise HTTPException(404, f"lesson '{lesson_id}' not found")
    return data


# ---------------------------------------------------------------------------
# SRS endpoints
# ---------------------------------------------------------------------------

@app.get("/srs/due")
async def srs_due(limit: int = 20, user_id: str = "default"):
    """Return SRS cards due for review today."""
    items = srs_mod.due_items(user_id, limit)
    return {"due": items, "count": len(items)}


@app.post("/srs/review")
async def srs_review(req: SrsReviewRequest, user_id: str = "default"):
    """Submit a review rating (1-4) for an SRS card; update schedule."""
    result = srs_mod.review(req.item_key, req.rating, user_id)
    xp_result = gami.award_xp("srs_review", gami.XP_TONE_PASS, user_id)
    return {**result, "xp": xp_result}


# ---------------------------------------------------------------------------
# Daily challenge endpoints
# ---------------------------------------------------------------------------

@app.get("/challenge/today")
async def challenge_today(user_id: str = "default"):
    """Return today's challenge (generates on first call each day)."""
    return gami.get_or_create_challenge(user_id)


@app.post("/challenge/complete")
async def challenge_complete(req: ChallengeCompleteRequest,
                              user_id: str = "default"):
    """Mark one challenge item done, award XP."""
    return gami.complete_challenge_item(req.item_key, user_id)


# ---------------------------------------------------------------------------
# Gamification state
# ---------------------------------------------------------------------------

@app.get("/gamification/state")
async def gamification_state(user_id: str = "default"):
    """XP, level, hearts, streak, badges."""
    return gami.get_state(user_id)


# ---------------------------------------------------------------------------
# Recall-assess: sentence-recall grading (writing or voice)
# ---------------------------------------------------------------------------

@app.post("/recall-assess")
async def recall_assess(req: RecallAssessRequest, user_id: str = "default"):
    """Grade a sentence-recall attempt against the expected hanzi answer."""
    if curr.get_lesson(req.lesson_id) is None:
        raise HTTPException(404, f"lesson '{req.lesson_id}' not found")

    recall_prompts: list = []
    for unit in curr.CURRICULUM:
        for l in unit["lessons"]:
            if l["id"] == req.lesson_id:
                recall_prompts = l.get("recall_prompts", [])
                break

    if not recall_prompts:
        raise HTTPException(404, f"no recall prompts for lesson '{req.lesson_id}'")

    # resolve by numeric index or by exact prompt_en text
    prompt = None
    if req.prompt_id.isdigit():
        idx = int(req.prompt_id)
        if 0 <= idx < len(recall_prompts):
            prompt = recall_prompts[idx]
    else:
        for p in recall_prompts:
            if p.get("prompt_en") == req.prompt_id:
                prompt = p
                break

    if prompt is None:
        raise HTTPException(404, f"prompt_id '{req.prompt_id}' not found")

    answer = prompt["answer_hanzi"].strip()
    attempt = req.payload.strip()

    if attempt == answer:
        score = 100
    else:
        # character-overlap ratio — partial credit for near-misses
        matched = sum(1 for ch in attempt if ch in answer)
        score = round(matched / max(len(answer), 1) * 100)

    passed = score >= 70
    xp_result = gami.award_xp("recall_pass", gami.XP_RECALL_PASS, user_id) if passed else None

    return {
        "prompt_en": prompt["prompt_en"],
        "attempt": attempt,
        "answer_hanzi": answer,
        "answer_pinyin": prompt["answer_pinyin"],
        "score": score,
        "passed": passed,
        "xp": xp_result,
    }


# ---------------------------------------------------------------------------
# Stats — rich progress summary
# ---------------------------------------------------------------------------

@app.get("/stats")
async def stats_endpoint(user_id: str = "default"):
    """Rich progress: per-level %, per-unit, tone vs writing, weak items,
    daily activity series (last 7 days)."""
    import sqlite3 as _sq
    from curriculum import DB_PATH as _DB

    with _sq.connect(_DB) as _c:
        _c.row_factory = _sq.Row
        tone_row = _c.execute(
            "SELECT COUNT(*) c, AVG(score) a FROM attempts WHERE user_id=?",
            (user_id,)).fetchone()
        write_row = _c.execute(
            "SELECT COUNT(*) c, AVG(score) a FROM writing_attempts WHERE user_id=?",
            (user_id,)).fetchone()
        done_set = {r["lesson_id"] for r in _c.execute(
            "SELECT lesson_id FROM lesson_progress "
            "WHERE user_id=? AND completed=1", (user_id,)).fetchall()}
        weak_rows = _c.execute(
            "SELECT hanzi, MAX(score) best FROM attempts WHERE user_id=? "
            "GROUP BY hanzi HAVING MAX(score)<70 ORDER BY MAX(score) ASC LIMIT 10",
            (user_id,)).fetchall()
        act_rows = _c.execute(
            "SELECT substr(created_at,1,10) day, COUNT(*) cnt FROM attempts "
            "WHERE user_id=? GROUP BY day ORDER BY day DESC LIMIT 7",
            (user_id,)).fetchall()

    outline = curr.curriculum_outline()
    per_level: dict = {}
    per_unit = []
    for unit in outline:
        lvl = unit["level"]
        total = len(unit["lessons"])
        done = sum(1 for l in unit["lessons"] if l["id"] in done_set)
        per_unit.append({"unit_id": unit["id"], "title": unit["title"],
                         "level": lvl, "total_lessons": total,
                         "done_lessons": done,
                         "pct": round(done / max(total, 1) * 100)})
        bl = per_level.setdefault(lvl, {"total": 0, "done": 0})
        bl["total"] += total
        bl["done"] += done
    for v in per_level.values():
        v["pct"] = round(v["done"] / max(v["total"], 1) * 100)

    return {
        "tone":    {"attempts": tone_row["c"] or 0,
                    "avg_score": round(tone_row["a"]) if tone_row["a"] else 0},
        "writing": {"attempts": write_row["c"] or 0,
                    "avg_score": round(write_row["a"]) if write_row["a"] else 0},
        "per_level": per_level,
        "per_unit": per_unit,
        "weak_items": [{"hanzi": r["hanzi"], "best_score": r["best"]}
                       for r in weak_rows],
        "daily_activity": [{"date": r["day"], "attempts": r["cnt"]}
                           for r in act_rows],
    }


# Path to the built APK (project root, one level up from backend/).
APK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "MandarinTutor.apk")


@app.get("/download")
async def download_apk():
    """Serve the Android APK so a phone browser saves it to Downloads.

    The android package-archive MIME type + attachment disposition makes
    Android treat it as a downloadable install file rather than rendering it.
    """
    if not os.path.isfile(APK_PATH):
        raise HTTPException(404, "APK belum di-build")
    return FileResponse(
        APK_PATH,
        media_type="application/vnd.android.package-archive",
        filename="MandarinTutor.apk",
    )


# ---------------------------------------------------------------------------
# Static PWA — mounted LAST so /chat /stt /tts /health win route matching.
# Serves the app at "/" (index.html). Same-origin => no CORS needed.
# ---------------------------------------------------------------------------
if os.path.isdir(APP_DIR):
    app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
