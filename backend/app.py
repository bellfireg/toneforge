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

import tone as tone_engine
import curriculum as curr

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")

# ---------------------------------------------------------------------------
# Whisper model — loaded once at startup, shared across requests
# ---------------------------------------------------------------------------
whisper_model: WhisperModel | None = None

ROUTER_URL = "http://127.0.0.1:20128/v1/chat/completions"
ROUTER_MODEL = "kr/claude-sonnet-4.6"
EDGE_TTS_BIN = os.path.expanduser("~/.local/bin/edge-tts")

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

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(ROUTER_URL, json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"9router error: {exc}") from exc

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
    """Units + lessons outline for the lesson-list screen."""
    return {"units": curr.curriculum_outline()}


@app.get("/lesson/{lesson_id}")
async def lesson(lesson_id: str):
    """Full lesson content (items with hanzi/pinyin/gloss/tone)."""
    data = curr.get_lesson(lesson_id)
    if data is None:
        raise HTTPException(404, f"lesson '{lesson_id}' not found")
    return data


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
