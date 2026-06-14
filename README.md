# 🔊 ToneForge — Mandarin Learning Tutor

> Voice-first Mandarin pronunciation tutor with a **custom tone-scoring engine built from scratch** — pitch-contour analysis, zero paid speech APIs, fully self-hosted.

A voice-first language-learning app inspired by Pingo AI, built to fix the gaps in existing tools: loose pronunciation scoring, shallow content, and no real progress tracking. The headline feature is a **custom Mandarin tone-scoring engine** built from scratch with pitch-contour analysis — no paid speech APIs.

Built as a personal tool (for me + my partner learning Mandarin), now open-sourced as a portfolio piece.

> 🌐 **Live demo:** [mandarin.bellfire.site](https://mandarin.bellfire.site) — try it in the browser, no install.
> 🚀 **Run it yourself:** one command — [`./setup.sh`](#run-it-locally). Most features need **no API key**.

---

## Why this exists

Most "AI language tutors" give you a green checkmark no matter what you say. Mandarin is a **tonal language** — 妈 (mā, flat) and 马 (mǎ, dipping) are different words. If the tutor can't tell your tones apart, it can't teach you. So I built a scorer that actually discriminates tones, validated against minimal pairs.

It's also a deliberate **$0-cost** build: no Azure Pronunciation Assessment, no Gemini Live API, no metered cloud STT. Everything runs locally or on flat-rate infrastructure, so it can be demoed publicly without a quota blowing up.

---

## Features

| Feature | What it does |
|---------|--------------|
| 💬 **Voice chat** | Talk to an AI tutor in Mandarin; get replies with pinyin, translation, and correction |
| 🎯 **Tone drill** | Speak a target word → get a 0-100 tone score + "you said tone X, should be tone Y" + native example playback |
| 📚 **Curriculum** | Structured 0→conversational path: 3 units, greetings → numbers → self-intro |
| 🏆 **Progress** | Streak tracking, attempt stats, average score, and achievement badges |
| 🎙️ **Near-live VAD** | Auto-detects when you stop speaking — no hold-to-talk button |
| 📦 **Native Android** | Capacitor-wrapped APK so non-technical users just install and go |

---

## Architecture

```
┌─────────────────┐    HTTPS     ┌──────────────────────────────┐
│  Android app /  │ ───────────► │  HTTPS entrypoint             │
│  PWA (browser)  │              │  (Cloudflare Tunnel for public │
└─────────────────┘              │   PWA, or Tailscale for private│
                                 │   personal/native use)         │
                                 └──────────────┬───────────────┘
                                                │
                                ┌───────────────▼───────────────┐
                                │  FastAPI backend (port 8900)   │
                                │  ──────────────────────────    │
                                │  /chat   → LLM (OpenAI-compat   │
                                │            chat endpoint)       │
                                │  /stt    → faster-whisper       │
                                │  /tts    → edge-tts (zh-CN)      │
                                │  /assess → tone-scoring engine   │
                                │  /curriculum, /progress → SQLite │
                                └────────────────────────────────┘
```

**Stack:** FastAPI · faster-whisper (STT) · edge-tts (TTS) · parselmouth/Praat (pitch extraction) · SQLite · vanilla JS PWA · Capacitor (APK) · HTTPS entrypoint (Cloudflare Tunnel or Tailscale).

---

## The hard part: building a tone scorer that actually works

This was the real engineering challenge, and it took two failed approaches before landing on the right one.

**Attempt 1 — DTW contour matching (failed).** The first design recorded a native reference, extracted both pitch contours, and compared them with Dynamic Time Warping. It scored a *wrong* tone (mǎ vs mā) *higher* than a correct one — worse than guessing. Root cause: DTW warps the time axis freely, so it can stretch a dipping tone-3 contour to match a flat tone-1 at low cost. Free time-warping is exactly what destroys tone discrimination.

**Attempt 2 — raw feature matching (failed).** Comparing raw pitch slope/RMSE against a TTS reference also failed: single-character TTS has erratic prosody, and no single metric separated correct from wrong tones.

**Attempt 3 — tone classification against the target (works).** The insight: the app *always knows the target tone* (from the lesson's pinyin), so I don't need a reference recording at all. I extract speaker-independent shape features from the pitch contour (overall slope, end-minus-start direction, position of the pitch minimum) and score the production against the *known target tone profile*.

Validated on the classic minimal quartet 妈/麻/马/骂 (mā/má/mǎ/mà — same syllable, four tones), cross-speaker (male + female TTS):

```
Correct target:  88/100 average
Wrong target:    48/100 average
→ 40-point separation. Usable discrimination, not noise.
```

Tones 2 (rising) and 4 (falling) separate cleanly by pitch direction. Tones 1↔3 still bleed slightly — a known linguistic problem (isolated tone-3 renders as a "half-third" with no dip), where even humans rely on context — but the correct target still wins.

**Takeaway:** the winning move wasn't a better matching algorithm, it was reframing the problem — classify against a known target instead of matching against a reference.

---

## Run it locally

**One command** (creates a venv, installs deps, seeds `backend/.env`):

```bash
./setup.sh
cd backend && source venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8900
```

Open `http://localhost:8900`. Mic needs HTTPS or `localhost` (browser secure-context rule).

### What needs a key, and what doesn't

**Most of the app runs with zero config and no API key** — tone drill, handwriting,
STT, TTS, curriculum, SRS, and progress are all local/offline:

| Feature | Needs a key? |
|---|---|
| 🎯 Tone drill · ✍️ Writing · 🎙️ STT · 🔊 TTS · 📚 Curriculum · 🏆 Progress | ❌ No |
| 💬 AI chat tutor | ⚠️ Needs an LLM endpoint |

Only the **💬 Chat** tab talks to a language model. The easiest **$0** path is a local
[Ollama](https://ollama.com):

```bash
ollama pull qwen2.5:7b      # backend/.env already points here by default
```

Prefer a hosted model? Edit `backend/.env` to use any OpenAI-compatible API:

```ini
CHAT_BASE_URL=https://api.openai.com
CHAT_MODEL=gpt-4o-mini
CHAT_API_KEY=sk-...
```

If chat isn't configured, that one tab shows a friendly "configure your LLM" notice —
the rest of the app keeps working.

```bash
# android APK (needs JDK 17 + Android SDK)
cd android-app
NODE_ENV=development npm install --include=dev
npx cap add android
bash ../build-apk.sh                    # → MandarinTutor.apk
```

The APK is a thin Capacitor shell pointing at the live HTTPS URL, so the app updates itself whenever the web frontend is redeployed — no rebuild needed.

---

## Engineering notes & gotchas

- **Cloudflare edge caching** silently served stale JS for 4h (`cf-cache-status: HIT, max-age=14400`). Fixed with versioned asset URLs (`app.js?v=N`) + a network-first service worker.
- **Single tab controller**: splitting tab logic across modules caused a UI limbo state. Centralized into one registry-based controller (`MTTabs`).
- **WebView mic**: Android WebView blocks `getUserMedia` by default — needs `RECORD_AUDIO` permission + an `onPermissionRequest` grant in `MainActivity`.
- **`NODE_ENV=production`** on the host made npm skip devDependencies (Capacitor CLI). Override per-command with `NODE_ENV=development`.

---

## Status

Built as a personal-use tool (for me + my partner) and an open-source portfolio piece. Tone engine, curriculum, drill UI, progress tracking, and near-live VAD are all live and verified end-to-end.

Built $0-cost: no Azure Pronunciation Assessment, no Gemini Live API, no metered cloud STT. Everything runs locally or on flat-rate infrastructure.

*Not affiliated with Pingo AI — independently built, inspired by the category.*
