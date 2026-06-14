#!/usr/bin/env bash
# ToneForge — one-command setup for the backend.
# Creates a venv, installs deps, seeds .env, and prints how to run.
set -euo pipefail

cd "$(dirname "$0")"
echo "🔊 ToneForge setup"
echo "──────────────────"

# 1. Python venv ------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi

cd backend
if [ ! -d venv ]; then
  echo "→ creating virtualenv (backend/venv)…"
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "→ installing dependencies (this can take a few minutes the first time)…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
cd ..

# 2. .env -------------------------------------------------------------------
if [ ! -f backend/.env ]; then
  cp .env.example backend/.env
  echo "→ created backend/.env from .env.example (defaults to local Ollama)"
else
  echo "→ backend/.env already exists, leaving it untouched"
fi

# 3. Done -------------------------------------------------------------------
cat <<'EOF'

✓ Setup complete.

Run the backend:
    cd backend && source venv/bin/activate
    uvicorn app:app --host 0.0.0.0 --port 8900

Then open  http://localhost:8900  in your browser.

What works with ZERO extra config:
    🎯 Tone Drill · ✍️ Writing · 🎙️ STT · 🔊 TTS · 📚 Curriculum · 🏆 Progress

The 💬 Chat tab needs an LLM. Easiest $0 path:
    1) install Ollama        → https://ollama.com
    2) ollama pull qwen2.5:7b
    3) (defaults in backend/.env already point at it)
Or edit backend/.env to use any OpenAI-compatible API (e.g. OpenAI, Groq).
EOF
