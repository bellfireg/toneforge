// ToneForge — Sentence-recall UI (sub-tab "📝 Sentence Recall" inside Write).
// Shows English prompt only (no hanzi hint). User writes on canvas or speaks.
// Submits to /recall-assess -> shows score + pass/fail.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const writePanel = document.getElementById("write");
  if (!writePanel) return;

  // ── Build recall panel ────────────────────────────────────────────────────
  const panel = document.createElement("div");
  panel.id = "recallPanel";
  panel.className = "recall-panel";
  panel.hidden = true;
  panel.innerHTML =
    `<div class="recall-prompt-box">
       <div class="recall-prompt-label">Write this sentence in Hanzi:</div>
       <div class="recall-prompt-en" id="recallPromptEn">—</div>
       <div class="recall-prompt-meta" id="recallPromptMeta"></div>
     </div>
     <div class="recall-input-row">
       <button class="recall-mode-btn active" id="recModeCanvas" type="button">✏️ Write</button>
       <button class="recall-mode-btn" id="recModeMic"    type="button">🎤 Speak</button>
     </div>
     <canvas id="recallCanvas" class="recall-canvas" aria-label="Write the sentence here"></canvas>
     <div class="recall-canvas-toolbar" id="recallCanvasToolbar">
       <button class="sp-btn" id="recClear" type="button">🗑️ Clear</button>
       <button class="sp-btn" id="recUndo"  type="button">↩️ Undo</button>
     </div>
     <div class="recall-mic-area" id="recallMicArea" hidden>
       <button class="drill-btn rec" id="recMicBtn" type="button">🎤 Record</button>
       <div class="recall-mic-hint">Speak the sentence in Mandarin</div>
     </div>
     <button class="recall-submit-btn" id="recallSubmit" type="button">✅ Submit</button>
     <div class="recall-result" id="recallResult" hidden></div>
     <div class="recall-nav">
       <button class="write-btn" id="recPrev" type="button">◀ Prev</button>
       <span class="recall-counter" id="recallCounter">1 / 1</span>
       <button class="write-btn" id="recNext" type="button">Next ▶</button>
     </div>`;
  writePanel.appendChild(panel);

  // ── State ─────────────────────────────────────────────────────────────────
  let prompts    = [];   // [{prompt_en, answer_hanzi, answer_pinyin, prompt_id}]
  let lessonId   = "";
  let idx        = 0;
  let inputMode  = "canvas"; // "canvas" | "mic"
  let recStrokes = [];
  let recCurrentPath = [];
  let recPainting    = false;
  let recCtx         = null;
  let recCanvasReady = false;

  // mic state
  let recorder   = null;
  let chunks     = [];
  let recording  = false;
  let busy       = false;

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const promptEnEl   = document.getElementById("recallPromptEn");
  const promptMetaEl = document.getElementById("recallPromptMeta");
  const counterEl    = document.getElementById("recallCounter");
  const resultEl     = document.getElementById("recallResult");
  const canvas       = document.getElementById("recallCanvas");
  const canvasToolbar= document.getElementById("recallCanvasToolbar");
  const micArea      = document.getElementById("recallMicArea");
  const micBtn       = document.getElementById("recMicBtn");
  const submitBtn    = document.getElementById("recallSubmit");
  const modeCanvas   = document.getElementById("recModeCanvas");
  const modeMic      = document.getElementById("recModeMic");
  const prevBtn      = document.getElementById("recPrev");
  const nextBtn      = document.getElementById("recNext");

  // ── Render current prompt ─────────────────────────────────────────────────
  function renderPrompt() {
    if (!prompts.length) {
      promptEnEl.textContent  = "No recall prompts for this lesson yet.";
      promptMetaEl.textContent = "";
      counterEl.textContent   = "0 / 0";
      submitBtn.disabled      = true;
      return;
    }
    submitBtn.disabled = false;
    const p = prompts[idx];
    promptEnEl.textContent   = p.prompt_en || "—";
    promptMetaEl.textContent = p.answer_pinyin ? `Pinyin: ${p.answer_pinyin}` : "";
    counterEl.textContent    = `${idx + 1} / ${prompts.length}`;
    clearCanvas();
    resultEl.hidden = true;
    resultEl.innerHTML = "";
  }

  // ── Canvas ────────────────────────────────────────────────────────────────
  function initRecallCanvas() {
    if (recCanvasReady) return;
    resizeRecallCanvas();
    recCtx = canvas.getContext("2d");
    recCtx.lineCap = "round"; recCtx.lineJoin = "round";
    canvas.addEventListener("pointerdown",  recBegin,    { passive: false });
    canvas.addEventListener("pointermove",  recMove,     { passive: false });
    canvas.addEventListener("pointerup",    recEnd,      { passive: false });
    canvas.addEventListener("pointercancel", recEnd,     { passive: false });
    canvas.addEventListener("pointerleave", recEnd,      { passive: false });
    canvas.addEventListener("pointerdown", (e) => {
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    });
    recCanvasReady = true;
  }

  function resizeRecallCanvas() {
    const w = Math.floor(canvas.parentElement.getBoundingClientRect().width) || 360;
    canvas.width  = w;
    canvas.height = Math.min(Math.floor(w * 0.5), 220);
  }

  function clearCanvas() {
    recStrokes = []; recCurrentPath = [];
    if (recCtx) recCtx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function getRecPos(e) {
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width  / rect.width;
    const sy = canvas.height / rect.height;
    const src = e.touches ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * sx,
      y: (src.clientY - rect.top)  * sy,
      pressure: e.pressure != null && e.pressure > 0 ? e.pressure : 0.6,
    };
  }

  function recBegin(e) {
    e.preventDefault(); recPainting = true;
    recCurrentPath = [getRecPos(e)];
  }

  function recMove(e) {
    if (!recPainting) return; e.preventDefault();
    const p = getRecPos(e);
    recCurrentPath.push(p);
    const prev = recCurrentPath[recCurrentPath.length - 2] || p;
    recCtx.strokeStyle = "#22c55e";
    recCtx.lineWidth   = 14 * (0.4 + p.pressure * 0.6);
    recCtx.beginPath(); recCtx.moveTo(prev.x, prev.y); recCtx.lineTo(p.x, p.y);
    recCtx.stroke();
  }

  function recEnd(e) {
    if (!recPainting) return; e.preventDefault();
    recPainting = false;
    if (recCurrentPath.length) recStrokes.push(recCurrentPath.slice());
    recCurrentPath = [];
  }

  // ── Input mode switching ──────────────────────────────────────────────────
  function setInputMode(m) {
    inputMode = m;
    modeCanvas.classList.toggle("active", m === "canvas");
    modeMic.classList.toggle("active",    m === "mic");
    canvas.hidden          = (m !== "canvas");
    canvasToolbar.hidden   = (m !== "canvas");
    micArea.hidden         = (m !== "mic");
  }

  modeCanvas.addEventListener("click", () => { setInputMode("canvas"); initRecallCanvas(); });
  modeMic.addEventListener("click",    () => setInputMode("mic"));

  // ── Canvas toolbar ────────────────────────────────────────────────────────
  document.getElementById("recClear").addEventListener("click", clearCanvas);
  document.getElementById("recUndo").addEventListener("click", () => {
    recStrokes.pop();
    if (!recCtx) return;
    recCtx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of recStrokes) {
      for (let i = 1; i < s.length; i++) {
        const prev = s[i-1], cur = s[i];
        recCtx.strokeStyle = "#22c55e";
        recCtx.lineWidth   = 14 * (0.4 + cur.pressure * 0.6);
        recCtx.beginPath(); recCtx.moveTo(prev.x, prev.y); recCtx.lineTo(cur.x, cur.y);
        recCtx.stroke();
      }
    }
  });

  // ── Mic recording ─────────────────────────────────────────────────────────
  micBtn.addEventListener("click", () => { recording ? stopMic() : startMic(); });

  async function startMic() {
    if (busy) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        submitMicBlob(new Blob(chunks, { type: chunks[0]?.type || "audio/webm" }));
      };
      recorder.start();
      recording = true;
      micBtn.classList.add("recording");
      micBtn.textContent = "🔴 Stop";
    } catch (err) {
      showResult(false, "Mic denied: " + err.message);
    }
  }

  function stopMic() {
    if (!recording) return;
    recording = false;
    micBtn.classList.remove("recording");
    micBtn.textContent = "🎤 Record";
    try { recorder.stop(); } catch (e) {}
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  submitBtn.addEventListener("click", () => {
    if (inputMode === "canvas") submitCanvas();
    else if (inputMode === "mic" && recording) stopMic();
    else if (inputMode === "mic") startMic();
  });

  async function submitCanvas() {
    if (!prompts.length) return;
    const p = prompts[idx];
    // Export canvas as PNG blob
    canvas.toBlob(async (blob) => {
      await postRecallAssess("writing", blob, null, p);
    }, "image/png");
  }

  async function submitMicBlob(blob) {
    if (!prompts.length) return;
    const p = prompts[idx];
    await postRecallAssess("speaking", blob, null, p);
  }

  async function postRecallAssess(mode, fileBlob, textPayload, p) {
    if (busy) return;
    busy = true;
    resultEl.hidden = false;
    resultEl.innerHTML = `<div class="score-line">⏳ Assessing…</div>`;
    try {
      const fd = new FormData();
      fd.append("lesson_id", lessonId);
      fd.append("prompt_id", p.prompt_id || String(idx));
      fd.append("mode", mode);
      if (fileBlob) fd.append("file", fileBlob, mode === "speaking" ? "recall.webm" : "recall.png");
      if (textPayload) fd.append("payload", textPayload);
      const res = await fetch(API + "/recall-assess", { method: "POST", body: fd });
      if (!res.ok) throw new Error("recall-assess " + res.status);
      const d = await res.json();
      renderResult(d);
    } catch (err) {
      showResult(false, "Error: " + err.message);
    } finally {
      busy = false;
    }
  }

  function renderResult(d) {
    const score = d.score ?? 0;
    const pass  = d.pass === true;
    const color = score >= 85 ? "#22c55e" : score >= 60 ? "#eab308" : score >= 35 ? "#f97316" : "#ef4444";
    resultEl.hidden = false;
    resultEl.innerHTML =
      `<div class="score-ring" style="background:${color}">${score}</div>` +
      `<div class="score-line ${pass ? "tone-right" : "tone-wrong"}">${pass ? "✓ Correct!" : "✗ Not quite"}</div>` +
      (d.feedback ? `<div class="score-detail">${d.feedback}</div>` : "") +
      `<div class="score-detail">Answer: <b>${prompts[idx].answer_hanzi || "—"}</b></div>`;
    if (window.MTProgress && window.MTProgress.refresh) window.MTProgress.refresh();
  }

  function showResult(pass, msg) {
    resultEl.hidden = false;
    resultEl.innerHTML = `<div class="score-line ${pass ? "tone-right" : "tone-wrong"}">${msg}</div>`;
  }

  // ── Nav ───────────────────────────────────────────────────────────────────
  prevBtn.addEventListener("click", () => { if (idx > 0) { idx--; renderPrompt(); } });
  nextBtn.addEventListener("click", () => { if (idx < prompts.length - 1) { idx++; renderPrompt(); } });

  // ── Public API: Learn feeds recall prompts ────────────────────────────────
  window.MTRecall = {
    loadPrompts(list, id) {
      prompts  = Array.isArray(list) ? list : [];
      lessonId = id || "";
      idx      = 0;
      renderPrompt();
    },
    open() {
      if (window.MTWriteSubNav) window.MTWriteSubNav.show("recall-sent");
      if (window.MTTabs) window.MTTabs.show("write");
      initRecallCanvas();
    },
  };

  // Init canvas on first reveal
  panel.addEventListener("transitionend", () => {
    if (!panel.hidden && inputMode === "canvas") initRecallCanvas();
  });

  renderPrompt();
})();
