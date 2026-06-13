"""Mandarin tone-scoring engine.

Compares a learner's pitch (F0) contour against a native reference (TTS) using
Praat (parselmouth) for pitch extraction and DTW for contour alignment.

This is the portfolio differentiator: a from-scratch Mandarin tone scorer, not a
paid cloud API. Mandarin is tonal (妈/麻/马/骂 differ only by pitch contour), so
F0-contour similarity is a meaningful proxy for "did you say it with the right
tones".

Pipeline:
  raw audio (any format) --ffmpeg--> mono 16k wav
    --parselmouth--> F0 contour (Hz, voiced frames only)
    --semitone-normalize--> speaker-independent contour
    --DTW vs reference--> normalized distance -> 0..100 score
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
import parselmouth


# ---------------------------------------------------------------------------
# Audio loading
# ---------------------------------------------------------------------------

def to_wav(src_path: str) -> str:
    """Convert any audio file to mono 16kHz WAV via ffmpeg. Returns new path."""
    out = tempfile.mktemp(suffix=".wav")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", "16000", out],
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode()[:300]}")
    return out


# ---------------------------------------------------------------------------
# Pitch extraction + normalization
# ---------------------------------------------------------------------------

def extract_f0(wav_path: str, fmin: float = 75.0, fmax: float = 500.0) -> np.ndarray:
    """Extract the voiced F0 contour (Hz) from a WAV file.

    Returns a 1-D array of pitch values for voiced frames only (unvoiced/zero
    frames dropped). Empty array if no voiced speech detected.
    """
    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch(pitch_floor=fmin, pitch_ceiling=fmax)
    f0 = pitch.selected_array["frequency"]  # 0 where unvoiced
    voiced = f0[f0 > 0]
    return voiced


def to_semitones(f0: np.ndarray) -> np.ndarray:
    """Convert Hz contour to semitones relative to its own median.

    This removes absolute pitch differences (male vs female, high vs low voice)
    so we score the SHAPE of the contour, not the speaker's base frequency.
    """
    if f0.size == 0:
        return f0
    ref = np.median(f0)
    if ref <= 0:
        return np.zeros_like(f0)
    return 12.0 * np.log2(f0 / ref)


def smooth(contour: np.ndarray, win: int = 5) -> np.ndarray:
    """Light moving-average smoothing to reduce pitch-tracker jitter."""
    if contour.size < win:
        return contour
    kernel = np.ones(win) / win
    return np.convolve(contour, kernel, mode="same")


def resample_to(contour: np.ndarray, n: int = 100) -> np.ndarray:
    """Resample a contour to a fixed length so DTW inputs are comparable."""
    if contour.size == 0:
        return contour
    if contour.size == n:
        return contour
    xp = np.linspace(0.0, 1.0, contour.size)
    x = np.linspace(0.0, 1.0, n)
    return np.interp(x, xp, contour)


def prep_contour(wav_path: str) -> np.ndarray:
    """Full prep: extract F0 -> semitones -> smooth -> resample(100)."""
    f0 = extract_f0(wav_path)
    if f0.size == 0:
        return f0
    st = to_semitones(f0)
    st = smooth(st)
    return resample_to(st, 100)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

TONE_NAMES = {1: "datar tinggi (—)", 2: "naik (ˊ)", 3: "turun-naik (ˇ)", 4: "jatuh (ˋ)"}


def shape_features(contour: np.ndarray) -> dict | None:
    """Extract speaker-independent shape features from a semitone contour.

    Trims ~12% off each edge (syllable onset/offset are noisy), then measures:
      slope     — linear trend over the syllable
      end_start — net pitch change (last - first); the most robust rise/fall cue
      mean      — average level vs the speaker's own median
      dip       — how far the contour drops below its mean (tone-3 V depth)
      minpos    — where the lowest point sits (0=start, 1=end)
    """
    n = contour.size
    if n < 6:
        return None
    lo, hi = int(n * 0.12), int(n * 0.88)
    c = contour[lo:hi]
    if c.size < 5:
        return None
    x = np.linspace(0.0, 1.0, c.size)
    return {
        "slope": float(np.polyfit(x, c, 1)[0]),
        "end_start": float(c[-1] - c[0]),
        "mean": float(c.mean()),
        "dip": float(c.mean() - c.min()),
        "minpos": float(np.argmin(c) / c.size),
    }


def detect_tone(f: dict) -> int:
    """Best-guess which Mandarin tone the learner actually produced.

    Primary axis = end_start (net rise/fall), which is robust and
    speaker-independent. Rising => tone 2, falling => tone 4. For the flat-ish
    cases we separate tone 1 (flat, higher) from tone 3 (low / slight dip) using
    level + dip — a deliberately weak signal, since isolated tone-3 collapses to
    a 'half-third' that is genuinely hard to tell from tone 1.
    """
    e = f["end_start"]
    if e > 2.5:
        return 2
    if e < -2.5:
        return 4
    if f["mean"] < -0.25 or f["dip"] > 1.1:
        return 3
    return 1


def score_tone(learner_wav: str, target_tone: int) -> dict:
    """Score how well a learner produced a KNOWN target tone (1-4).

    The app always knows the target tone (it comes from the curriculum's pinyin),
    so we score the learner's contour against that tone's expected rise/fall
    profile rather than matching a noisy TTS reference. Returns:
      { score: 0..100, detected_tone, target_tone, features, ok, reason }
    """
    contour = prep_contour(learner_wav)
    if contour.size == 0:
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "reason": "no_voiced_speech"}

    f = shape_features(contour)
    if f is None:
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "reason": "too_short"}

    e = f["end_start"]
    if target_tone == 1:        # flat: net change near zero
        raw = np.exp(-(e ** 2) / (2 * 2.0 ** 2))
    elif target_tone == 2:      # rising: e strongly positive
        raw = 1.0 / (1.0 + np.exp(-(e - 2.0)))
    elif target_tone == 4:      # falling: e strongly negative
        raw = 1.0 / (1.0 + np.exp(e + 2.0))
    elif target_tone == 3:      # low half-third: near-flat / slight, low level
        raw = np.exp(-((e - 0.5) ** 2) / (2 * 2.0 ** 2))
    else:
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "reason": "invalid_target_tone"}

    score = max(0, min(100, int(round(100.0 * float(raw)))))
    return {
        "score": score,
        "detected_tone": detect_tone(f),
        "target_tone": target_tone,
        "features": {k: round(v, 2) for k, v in f.items()},
        "ok": True,
        "reason": "",
    }


def tone_feedback(score: int) -> str:
    """Human, encouraging feedback string keyed to the tone score."""
    if score >= 85:
        return "Nada kamu hampir sempurna! 👏"
    if score >= 70:
        return "Nadanya udah bagus, tinggal dihalusin dikit."
    if score >= 50:
        return "Arah nadanya betul tapi belum pas — dengerin contoh & tiru naik-turunnya."
    if score >= 30:
        return "Nadanya masih meleset. Fokus ke naik/turun pitch tiap suku kata."
    return "Coba lagi pelan-pelan, tiru persis nada di contoh."


# ---------------------------------------------------------------------------
# Pinyin tone parsing
# ---------------------------------------------------------------------------

# Tone-marked vowel -> (base vowel, tone number). Covers a/e/i/o/u/ü.
_TONE_VOWELS = {
    "ā": ("a", 1), "á": ("a", 2), "ǎ": ("a", 3), "à": ("a", 4),
    "ē": ("e", 1), "é": ("e", 2), "ě": ("e", 3), "è": ("e", 4),
    "ī": ("i", 1), "í": ("i", 2), "ǐ": ("i", 3), "ì": ("i", 4),
    "ō": ("o", 1), "ó": ("o", 2), "ǒ": ("o", 3), "ò": ("o", 4),
    "ū": ("u", 1), "ú": ("u", 2), "ǔ": ("u", 3), "ù": ("u", 4),
    "ǖ": ("v", 1), "ǘ": ("v", 2), "ǚ": ("v", 3), "ǜ": ("v", 4),
}


def pinyin_tone(syllable: str) -> int:
    """Return the tone number (1-4) of a single marked pinyin syllable.

    Neutral tone (no mark) returns 5. Accepts either tone marks (nǐ) or a
    trailing digit (ni3).
    """
    s = syllable.strip()
    if not s:
        return 5
    if s[-1].isdigit():           # numeric form e.g. "ni3"
        d = int(s[-1])
        return d if 1 <= d <= 5 else 5
    for ch in s:                  # diacritic form e.g. "nǐ"
        if ch in _TONE_VOWELS:
            return _TONE_VOWELS[ch][1]
    return 5  # no mark = neutral tone
