"""Mandarin tone-scoring engine.

Compares a learner's pitch (F0) contour against canonical Mandarin tone shapes
using Praat (parselmouth) for pitch extraction and DTW for contour alignment.

This is the portfolio differentiator: a from-scratch Mandarin tone scorer, not a
paid cloud API. Mandarin is tonal (妈/麻/马/骂 differ only by pitch contour), so
F0-contour similarity is a meaningful proxy for "did you say it with the right
tones".

Pipeline:
  raw audio (any format) --ffmpeg--> mono 16k wav
    --parselmouth--> F0 contour (Hz, voiced frames only)
    --log/z-normalize--> speaker-independent contour
    --DTW vs canonical reference + tone calibration--> 0..100 score
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


def z_normalize(contour: np.ndarray) -> np.ndarray:
    """Center and scale a contour so only its shape remains."""
    if contour.size == 0:
        return contour
    c = contour.astype(float) - float(np.mean(contour))
    sd = float(np.std(c))
    if sd < 1e-6:
        return np.zeros_like(c)
    return c / sd


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


def normalize_f0_contour(f0: np.ndarray, n: int = 32) -> np.ndarray:
    """Drop unvoiced frames, log-scale, smooth, resample, then z-normalize."""
    f0 = np.asarray(f0, dtype=float)
    f0 = f0[np.isfinite(f0) & (f0 > 0)]
    if f0.size == 0:
        return f0
    log_pitch = 12.0 * np.log2(f0)
    log_pitch = smooth(log_pitch, win=3)
    return z_normalize(resample_to(log_pitch, n))


def prep_contour(wav_path: str) -> np.ndarray:
    """Full prep: extract F0 -> log pitch -> smooth -> resample(32) -> z-normalize."""
    return normalize_f0_contour(extract_f0(wav_path), n=32)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

TONE_NAMES = {1: "datar tinggi (—)", 2: "naik (ˊ)", 3: "turun-naik (ˇ)", 4: "jatuh (ˋ)"}

# A learner "passes" a syllable (tone counted as correct) at or above this score.
# This is the single source of truth for correctness — the UI must use the
# `pass` flag, not re-derive correctness from detected_tone.
PASS_SCORE = 70


def scoring_contours(f0: np.ndarray, n: int = 32) -> tuple[np.ndarray, np.ndarray]:
    """Return (z-normalized shape, semitone contour) for scoring.

    The normalized contour is used for reference-shape similarity. The semitone
    contour keeps the real movement size so a flat syllable does not become a
    fake rise after z-normalization.
    """
    f0 = np.asarray(f0, dtype=float)
    f0 = f0[np.isfinite(f0) & (f0 > 0)]
    if f0.size == 0:
        return f0, f0
    semitone = smooth(to_semitones(f0), win=3)
    semitone = resample_to(semitone, n)
    return z_normalize(semitone), semitone


def reference_contour(tone: int, n: int = 32) -> np.ndarray:
    """Canonical normalized Mandarin tone shape."""
    x = np.linspace(0.0, 1.0, n)
    if tone == 1:
        y = np.zeros(n)
    elif tone == 2:
        y = x
    elif tone == 3:
        # Full third tone: an early/mid low valley followed by a gentle rise.
        y = np.where(x <= 0.55, 0.45 - 1.45 * (x / 0.55),
                     -1.0 + 0.9 * ((x - 0.55) / 0.45))
    elif tone == 4:
        y = 1.0 - x
    else:
        raise ValueError("invalid tone")
    return z_normalize(y)


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Small DTW over absolute point distances, normalized by path length."""
    n, m = a.size, b.size
    dp = np.full((n + 1, m + 1), np.inf)
    steps = np.zeros((n + 1, m + 1), dtype=int)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            choices = (dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
            k = int(np.argmin(choices))
            if k == 0:
                pi, pj = i - 1, j
            elif k == 1:
                pi, pj = i, j - 1
            else:
                pi, pj = i - 1, j - 1
            dp[i, j] = abs(float(a[i - 1] - b[j - 1])) + dp[pi, pj]
            steps[i, j] = steps[pi, pj] + 1
    return float(dp[n, m] / max(1, steps[n, m]))


def shape_features(contour: np.ndarray, semitone: np.ndarray | None = None) -> dict | None:
    """Extract tone-shape features from normalized and semitone contours."""
    n = contour.size
    if n < 6:
        return None
    lo, hi = int(n * 0.10), int(n * 0.90)
    c = contour[lo:hi]
    st = semitone[lo:hi] if semitone is not None and semitone.size == n else c
    if c.size < 5:
        return None
    x = np.linspace(0.0, 1.0, c.size)
    min_i = int(np.argmin(st))
    return {
        "slope": float(np.polyfit(x, c, 1)[0]),
        "end_start": float(st[-1] - st[0]),
        "range": float(st.max() - st.min()),
        "dip": float(max(st[0], st[-1]) - st[min_i]),
        "minpos": float(min_i / max(1, st.size - 1)),
    }


def reference_similarity(contour: np.ndarray, tone: int) -> float:
    """Map normalized DTW distance to a lenient 0..100 shape score."""
    ref = reference_contour(tone, contour.size)
    dist = dtw_distance(contour, ref)
    scale = {1: 1.15, 2: 1.05, 3: 1.35, 4: 1.05}[tone]
    return 100.0 * np.exp(-((dist / scale) ** 2))


def calibrated_tone_score(contour: np.ndarray, semitone: np.ndarray, tone: int,
                          f: dict) -> float:
    """Blend contour similarity with tone-specific Mandarin pitch cues."""
    shape = reference_similarity(contour, tone)
    movement = abs(f["end_start"])
    if tone == 1:
        flat = 100.0 * np.exp(-((f["range"] / 2.2) ** 2))
        return 0.55 * shape + 0.45 * flat
    if tone == 2:
        rise = 100.0 / (1.0 + np.exp(-1.35 * (f["end_start"] - 1.0)))
        not_flat = min(100.0, 100.0 * movement / 2.2)
        return 0.58 * shape + 0.30 * rise + 0.12 * not_flat
    if tone == 4:
        fall = 100.0 / (1.0 + np.exp(-1.35 * (-f["end_start"] - 1.0)))
        not_flat = min(100.0, 100.0 * movement / 2.2)
        return 0.58 * shape + 0.30 * fall + 0.12 * not_flat
    if tone == 3:
        valley_pos = 100.0 * np.exp(-(((f["minpos"] - 0.55) / 0.32) ** 2))
        dip = 100.0 / (1.0 + np.exp(-1.6 * (f["dip"] - 0.8)))
        # Tone 3 often surfaces as a low or half-third contour; make the dip
        # cue decisive, and let a shallow but correctly placed valley pass.
        return 0.45 * shape + 0.35 * dip + 0.20 * valley_pos
    return 0.0


def detect_tone(f: dict) -> int:
    """Best-guess which Mandarin tone the learner actually produced.

    Primary axis = end_start (net rise/fall), which is robust and
    speaker-independent. Rising => tone 2, falling => tone 4. A clear valley
    in the middle is treated as tone 3 before the directional checks.
    """
    e = f["end_start"]
    if f["dip"] > 1.0 and 0.25 <= f["minpos"] <= 0.85:
        return 3
    if e > 1.8:
        return 2
    if e < -1.8:
        return 4
    return 1


def score_tone(learner_wav: str, target_tone: int) -> dict:
    """Score how well a learner produced a KNOWN target tone (1-4).

    The app always knows the target tone (it comes from the curriculum's pinyin),
    so we score the learner's contour against that tone's expected rise/fall
    profile rather than matching a noisy TTS reference. Returns:
      { score: 0..100, detected_tone, target_tone, features, ok, pass, reason }

    `pass` (score >= PASS_SCORE) is the authoritative "did they get the tone
    right" verdict — it is derived from the contour-vs-target similarity, NOT
    from the standalone detect_tone() classifier (which is deliberately weak for
    the flat/low tones and would otherwise contradict a perfectly good score).
    """
    if target_tone not in (1, 2, 3, 4):
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "pass": False, "reason": "invalid_target_tone"}

    contour, semitone = scoring_contours(extract_f0(learner_wav), n=32)
    if contour.size == 0:
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "pass": False, "reason": "no_voiced_speech"}

    f = shape_features(contour, semitone)
    if f is None:
        return {"score": 0, "detected_tone": None, "target_tone": target_tone,
                "ok": False, "pass": False, "reason": "too_short"}

    raw = calibrated_tone_score(contour, semitone, target_tone, f)
    score = max(0, min(100, int(round(float(raw)))))
    passed = score >= PASS_SCORE
    # When the contour clearly matches the target, report the target as the
    # detected tone so the UI never contradicts a good score with the weak
    # classifier. Only fall back to detect_tone() when they did NOT pass.
    detected = target_tone if passed else detect_tone(f)
    return {
        "score": score,
        "detected_tone": detected,
        "target_tone": target_tone,
        "features": {k: round(v, 2) for k, v in f.items()},
        "ok": True,
        "pass": passed,
        "reason": "",
    }


def tone_feedback(score: int) -> str:
    """Human, encouraging feedback string keyed to the tone score (English)."""
    if score >= 95:
        return "Perfect tone! 🎉 Native-level."
    if score >= 85:
        return "Almost perfect — really nicely done! 👏"
    if score >= 70:
        return "Good tone, just polish it a little."
    if score >= 50:
        return "Right direction but not quite there — listen to the example and copy the rise/fall."
    if score >= 30:
        return "Tone is off. Focus on the pitch going up/down on each syllable."
    return "Try again slowly and mimic the example tone exactly."


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
