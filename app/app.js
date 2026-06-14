// Mandarin Tutor — front-end logic (PWA) v15
// Chat upgraded: Pingo-style bubbles, hanzi+pinyin+English toggle,
// typing indicator, TTS tap on tutor hanzi, quick-reply chips, auto-scroll.
const CFG = window.MT_CONFIG || { API_BASE: "", DEFAULT_VOICE: "zh-CN-XiaoxiaoNeural" };
const API = CFG.API_BASE || "";

const chatEl    = document.getElementById("chat");
const hintEl    = document.getElementById("hint");
const statusEl  = document.getElementById("status");
const micBtn    = document.getElementById("mic");
const micLabel  = micBtn.querySelector(".mic-label");
const textInput = document.getElementById("textInput");
const sendBtn   = document.getElementById("sendBtn");
const voiceSel  = document.getElementById("voice");
const player    = document.getElementById("player");

let history   = [];   // [{role, content}] for the LLM
let recorder  = null;
let chunks    = [];
let recording = false;
let busy      = false;

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------
function setStatus(msg, isErr = false) {
  if (!msg) { statusEl.hidden = true; statusEl.textContent = ""; return; }
  statusEl.hidden = false;
  statusEl.textContent = msg;
  statusEl.classList.toggle("err", isErr);
}

function scrollDown() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

// ---------------------------------------------------------------------------
// Quick-reply chip suggestions (rotate a few canned openers)
// ---------------------------------------------------------------------------
const CHIP_SETS = [
  ["你好！", "我叫贝尔。", "你好吗？"],
  ["谢谢你！", "我不明白。", "请再说一次。"],
  ["我来自印度尼西亚。", "我在学中文。", "帮我练习。"],
  ["今天天气怎么样？", "你叫什么名字？", "我很好。"],
];
let chipSetIdx = 0;

function renderChips() {
  const existing = chatEl.querySelector(".chat-chips");
  if (existing) existing.remove();

  const chips = CHIP_SETS[chipSetIdx % CHIP_SETS.length];
  chipSetIdx++;

  const row = document.createElement("div");
  row.className = "chat-chips";
  row.setAttribute("aria-label", "Quick reply suggestions");

  for (const text of chips) {
    const btn = document.createElement("button");
    btn.className = "chat-chip";
    btn.textContent = text;
    btn.type = "button";
    btn.addEventListener("click", () => {
      row.remove();
      handleUserText(text);
    });
    row.appendChild(btn);
  }
  chatEl.appendChild(row);
  scrollDown();
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function addUserMsg(text) {
  if (hintEl) hintEl.remove();
  // Remove chips when user sends a message
  const chips = chatEl.querySelector(".chat-chips");
  if (chips) chips.remove();

  const wrap = document.createElement("div");
  wrap.className = "msg user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);

  const ts = document.createElement("div");
  ts.className = "msg-ts";
  ts.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  wrap.appendChild(ts);

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

// Build a rich tutor bubble:
//  - Large hanzi bubble (tappable for TTS + send to Drill)
//  - Pinyin shown below, toggleable
//  - English shown below, toggleable
//  - Correction block if present
//  - Replay + "Send to Drill" buttons
function addTutorMsg(data, audioUrl) {
  if (hintEl) hintEl.remove();

  const wrap = document.createElement("div");
  wrap.className = "msg tutor";

  // ── hanzi bubble (tappable) ──
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble-tutor-hanzi";
  bubble.textContent = data.reply_zh || "(no reply)";
  bubble.setAttribute("role", "button");
  bubble.setAttribute("tabindex", "0");
  bubble.title = "Tap to hear";
  bubble.addEventListener("click", () => tapHanzi(data.reply_zh));
  bubble.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tapHanzi(data.reply_zh); }
  });
  wrap.appendChild(bubble);

  // ── pinyin row (toggle) ──
  if (data.pinyin) {
    const pRow = document.createElement("div");
    pRow.className = "tutor-meta-row";

    const pEl = document.createElement("span");
    pEl.className = "pinyin tutor-pinyin";
    pEl.textContent = data.pinyin;

    const togglePy = document.createElement("button");
    togglePy.className = "meta-toggle";
    togglePy.type = "button";
    togglePy.textContent = "拼音";
    togglePy.setAttribute("aria-pressed", "true");
    togglePy.addEventListener("click", () => {
      const hidden = pEl.style.display === "none";
      pEl.style.display = hidden ? "" : "none";
      togglePy.setAttribute("aria-pressed", String(hidden));
    });

    pRow.appendChild(togglePy);
    pRow.appendChild(pEl);
    wrap.appendChild(pRow);
  }

  // ── English row (toggle) ──
  if (data.reply_en) {
    const eRow = document.createElement("div");
    eRow.className = "tutor-meta-row";

    const eEl = document.createElement("span");
    eEl.className = "en tutor-en";
    eEl.textContent = data.reply_en;
    eEl.style.display = "none"; // hidden by default — tap to reveal

    const toggleEn = document.createElement("button");
    toggleEn.className = "meta-toggle";
    toggleEn.type = "button";
    toggleEn.textContent = "EN";
    toggleEn.setAttribute("aria-pressed", "false");
    toggleEn.addEventListener("click", () => {
      const hidden = eEl.style.display === "none";
      eEl.style.display = hidden ? "" : "none";
      toggleEn.setAttribute("aria-pressed", String(hidden));
    });

    eRow.appendChild(toggleEn);
    eRow.appendChild(eEl);
    wrap.appendChild(eRow);
  }

  // ── correction block ──
  if (data.correction && data.correction.trim()) {
    const c = document.createElement("div");
    c.className = "correction";
    c.textContent = "✏️ " + data.correction;
    wrap.appendChild(c);
  }

  // ── action row: replay + send to drill ──
  const actRow = document.createElement("div");
  actRow.className = "tutor-action-row";

  if (audioUrl) {
    const replayBtn = document.createElement("button");
    replayBtn.className = "tutor-action-btn";
    replayBtn.type = "button";
    replayBtn.textContent = "🔊 Play";
    replayBtn.addEventListener("click", () => { player.src = audioUrl; player.play(); });
    actRow.appendChild(replayBtn);
  }

  if (data.reply_zh) {
    const drillBtn = document.createElement("button");
    drillBtn.className = "tutor-action-btn";
    drillBtn.type = "button";
    drillBtn.textContent = "🎯 Drill";
    drillBtn.addEventListener("click", () => sendToDrill(data));
    actRow.appendChild(drillBtn);
  }

  if (actRow.children.length) wrap.appendChild(actRow);

  // ── timestamp ──
  const ts = document.createElement("div");
  ts.className = "msg-ts";
  ts.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  wrap.appendChild(ts);

  chatEl.appendChild(wrap);
  scrollDown();

  // Show fresh quick-reply chips after tutor responds
  renderChips();
}

// ---------------------------------------------------------------------------
// Tap hanzi: TTS play
// ---------------------------------------------------------------------------
async function tapHanzi(text) {
  if (!text) return;
  try {
    const url = await synthesize(text);
    if (url) { player.src = url; player.play().catch(() => {}); }
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Send tutor reply to Drill
// ---------------------------------------------------------------------------
function sendToDrill(data) {
  if (!data.reply_zh) return;
  const items = [{ hanzi: data.reply_zh, pinyin: data.pinyin || "", gloss: data.reply_en || "", tone: 0 }];
  if (window.MTDrill && typeof window.MTDrill.loadItems === "function") {
    window.MTDrill.loadItems(items, "From Chat");
  }
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
    try { audioUrl = await synthesize(data.reply_zh); } catch (_) {}

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
// Wiring
// ---------------------------------------------------------------------------
micBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); startRecording(); });
micBtn.addEventListener("pointerup",   (e) => { e.preventDefault(); stopRecording(); });
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

// Show initial chips so first-time users have something to tap
renderChips();
