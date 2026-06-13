// Mandarin Tutor — front-end logic (PWA).
const CFG = window.MT_CONFIG || { API_BASE: "", DEFAULT_VOICE: "zh-CN-XiaoxiaoNeural" };
const API = CFG.API_BASE || "";

const chatEl = document.getElementById("chat");
const hintEl = document.getElementById("hint");
const statusEl = document.getElementById("status");
const micBtn = document.getElementById("mic");
const micLabel = micBtn.querySelector(".mic-label");
const textInput = document.getElementById("textInput");
const sendBtn = document.getElementById("sendBtn");
const voiceSel = document.getElementById("voice");
const player = document.getElementById("player");

let history = [];          // [{role, content}] for the LLM
let recorder = null;
let chunks = [];
let recording = false;
let busy = false;

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------
function setStatus(msg, isErr = false) {
  if (!msg) { statusEl.hidden = true; statusEl.textContent = ""; return; }
  statusEl.hidden = false;
  statusEl.textContent = msg;
  statusEl.classList.toggle("err", isErr);
}

function scrollDown() { chatEl.scrollTop = chatEl.scrollHeight; }

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function addUserMsg(text) {
  if (hintEl) hintEl.remove();
  const wrap = document.createElement("div");
  wrap.className = "msg user";
  wrap.innerHTML = `<div class="bubble"></div>`;
  wrap.querySelector(".bubble").textContent = text;
  chatEl.appendChild(wrap);
  scrollDown();
}

function addTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg tutor";
  wrap.id = "typing-indicator";
  wrap.innerHTML = `<div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  chatEl.appendChild(wrap);
  scrollDown();
}
function removeTyping() {
  const t = document.getElementById("typing-indicator");
  if (t) t.remove();
}

function addTutorMsg(data, audioUrl) {
  const wrap = document.createElement("div");
  wrap.className = "msg tutor";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = data.reply_zh || "(no reply)";
  wrap.appendChild(bubble);

  if (data.pinyin) {
    const p = document.createElement("div");
    p.className = "pinyin"; p.textContent = data.pinyin;
    wrap.appendChild(p);
  }
  if (data.reply_en) {
    const e = document.createElement("div");
    e.className = "en"; e.textContent = data.reply_en;
    wrap.appendChild(e);
  }
  if (data.correction && data.correction.trim()) {
    const c = document.createElement("div");
    c.className = "correction"; c.textContent = "✏️ " + data.correction;
    wrap.appendChild(c);
  }
  if (audioUrl) {
    const btn = document.createElement("button");
    btn.className = "replay"; btn.textContent = "🔊 Play again";
    btn.onclick = () => { player.src = audioUrl; player.play(); };
    wrap.appendChild(btn);
  }
  chatEl.appendChild(wrap);
  scrollDown();
}

// ---------------------------------------------------------------------------
// Core pipeline: user text -> /chat -> /tts
// ---------------------------------------------------------------------------
async function handleUserText(text) {
  if (!text || busy) return;
  busy = true; sendBtn.disabled = true;
  addUserMsg(text);
  addTyping();
  setStatus("Tutor is thinking…");

  try {
    const res = await fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, user_text: text }),
    });
    if (!res.ok) throw new Error("chat " + res.status);
    const data = await res.json();
    history = data.history || history;
    removeTyping();

    let audioUrl = null;
    try {
      audioUrl = await synthesize(data.reply_zh);
    } catch (e) { /* TTS optional; show text anyway */ }

    addTutorMsg(data, audioUrl);
    setStatus("");
    if (audioUrl) { player.src = audioUrl; player.play().catch(() => {}); }
  } catch (err) {
    removeTyping();
    setStatus("Error: " + err.message, true);
  } finally {
    busy = false; sendBtn.disabled = false;
  }
}

async function synthesize(text) {
  if (!text) return null;
  const res = await fetch(API + "/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice: voiceSel.value || CFG.DEFAULT_VOICE }),
  });
  if (!res.ok) throw new Error("tts " + res.status);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// ---------------------------------------------------------------------------
// Voice input: MediaRecorder -> /stt -> handleUserText
// ---------------------------------------------------------------------------
async function startRecording() {
  if (recording || busy) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      sendAudio(blob);
    };
    recorder.start();
    recording = true;
    micBtn.classList.add("recording");
    micLabel.textContent = "Release to send";
    setStatus("🔴 Recording…");
  } catch (err) {
    setStatus("Mic denied / not available: " + err.message, true);
  }
}

function stopRecording() {
  if (!recording) return;
  recording = false;
  micBtn.classList.remove("recording");
  micLabel.textContent = "Tap to speak";
  try { recorder.stop(); } catch (e) {}
}

async function sendAudio(blob) {
  if (!blob || !blob.size) { setStatus("Empty recording", true); return; }
  busy = true;
  setStatus("Recognizing speech…");
  try {
    const fd = new FormData();
    fd.append("file", blob, "speech.webm");
    const res = await fetch(API + "/stt", { method: "POST", body: fd });
    if (!res.ok) throw new Error("stt " + res.status);
    const { text } = await res.json();
    busy = false;
    if (text && text.trim()) {
      handleUserText(text.trim());
    } else {
      setStatus("Nothing heard. Try again.", true);
    }
  } catch (err) {
    busy = false;
    setStatus("STT error: " + err.message, true);
  }
}

// ---------------------------------------------------------------------------
// Wiring (press-and-hold mic; tap also works via click fallback)
// ---------------------------------------------------------------------------
micBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener("pointerup", (e) => { e.preventDefault(); stopRecording(); });
micBtn.addEventListener("pointercancel", () => stopRecording());
micBtn.addEventListener("pointerleave", () => { if (recording) stopRecording(); });

sendBtn.addEventListener("click", () => {
  const t = textInput.value.trim();
  if (t) { textInput.value = ""; handleUserText(t); }
});
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { sendBtn.click(); }
});

voiceSel.value = CFG.DEFAULT_VOICE;
