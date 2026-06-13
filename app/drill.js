// Mandarin Tutor — Pronunciation Drill (tab "Tone Drill").
// Uses /assess (tone scoring) + /tts (native example). Own recorder state so it
// never collides with the chat recorder in app.js.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  // Starter word bank (tone-balanced single syllables + a few common words).
  // tone = the target tone number used by /assess scoring.
  const WORDS = [
    { hz: "妈", py: "mā", en: "mother", tone: 1 },
    { hz: "麻", py: "má", en: "hemp", tone: 2 },
    { hz: "马", py: "mǎ", en: "horse", tone: 3 },
    { hz: "骂", py: "mà", en: "to scold", tone: 4 },
    { hz: "高", py: "gāo", en: "tall", tone: 1 },
    { hz: "来", py: "lái", en: "to come", tone: 2 },
    { hz: "好", py: "hǎo", en: "good", tone: 3 },
    { hz: "是", py: "shì", en: "to be", tone: 4 },
    { hz: "猫", py: "māo", en: "cat", tone: 1 },
    { hz: "鱼", py: "yú", en: "fish", tone: 2 },
    { hz: "你", py: "nǐ", en: "you", tone: 3 },
    { hz: "谢", py: "xiè", en: "thanks", tone: 4 },
  ];

  const TONE_LABELS = {
    1: "Tone 1 — high flat (—)",
    2: "Tone 2 — rising (ˊ)",
    3: "Tone 3 — dip (ˇ)",
    4: "Tone 4 — falling (ˋ)",
  };

  // DOM
  const tabChat = document.getElementById("tabChat");
  const tabDrill = document.getElementById("tabDrill");
  const chatEl = document.getElementById("chat");
  const drillEl = document.getElementById("drill");
  const composer = document.querySelector(".composer");
  const hanziEl = document.getElementById("drillHanzi");
  const pinyinEl = document.getElementById("drillPinyin");
  const enEl = document.getElementById("drillEn");
  const badgeEl = document.getElementById("drillToneBadge");
  const listenBtn = document.getElementById("drillListen");
  const recBtn = document.getElementById("drillRec");
  const nextBtn = document.getElementById("drillNext");
  const resultEl = document.getElementById("drillResult");
  const player = document.getElementById("player");
  const voiceSel = document.getElementById("voice");

  let idx = 0;
  let recorder = null;
  let chunks = [];
  let recording = false;
  let busy = false;
  let vadDetach = null;

  function cur() { return WORDS[idx]; }

  function renderWord() {
    const w = cur();
    hanziEl.textContent = w.hz;
    pinyinEl.textContent = w.py;
    enEl.textContent = w.en;
    badgeEl.textContent = TONE_LABELS[w.tone] || "";
    resultEl.hidden = true;
    resultEl.innerHTML = "";
  }

  // ---- tab switching: SINGLE source of truth for ALL panels (registry) ----
  const tabLearn = document.getElementById("tabLearn");
  const learnEl = document.getElementById("learn");
  // registry: name -> { panel, tab }. chat is special (uses display, has composer).
  const panels = {
    chat:  { panel: null,    tab: tabChat },
    learn: { panel: learnEl, tab: tabLearn },
    drill: { panel: drillEl, tab: tabDrill },
  };
  function showTab(which) {
    for (const name in panels) {
      const p = panels[name];
      const on = name === which;
      if (p.tab) p.tab.classList.toggle("active", on);
      if (name === "chat") {
        chatEl.style.display = on ? "" : "none";
      } else if (p.panel) {
        p.panel.classList.toggle("show", on);
      }
    }
    // chat composer (mic + text) only makes sense on the chat tab
    if (composer) composer.style.display = which === "chat" ? "" : "none";
  }
  // Expose the one controller so other modules never touch tab classes directly.
  window.MTTabs = {
    show: showTab,
    register: (name, panel, tab) => { panels[name] = { panel, tab }; },
  };
  tabChat.addEventListener("click", () => showTab("chat"));
  tabDrill.addEventListener("click", () => { showTab("drill"); renderWord(); });

  // ---- listen to native example (reuses /tts) ----
  listenBtn.addEventListener("click", async () => {
    const w = cur();
    listenBtn.disabled = true;
    try {
      const res = await fetch(API + "/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: w.hz, voice: voiceSel.value || "zh-CN-XiaoxiaoNeural" }),
      });
      if (!res.ok) throw new Error("tts " + res.status);
      const blob = await res.blob();
      player.src = URL.createObjectURL(blob);
      await player.play().catch(() => {});
    } catch (e) {
      flashResult(`<div class="score-line tone-wrong">Failed to load example: ${e.message}</div>`);
    } finally {
      listenBtn.disabled = false;
    }
  });

  // ---- record + assess ----
  async function startRec() {
    if (recording || busy) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      flashResult(`<div class="score-line tone-wrong">Mic requires HTTPS. Open via https:// instead.</div>`);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks = [];
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
        assess(blob);
      };
      recorder.start();
      recording = true;
      recBtn.classList.add("recording");
      recBtn.textContent = "🔴 Speak… (auto-stop)";
      // Near-live: auto-stop after a pause so there's no hold-to-talk.
      if (window.MTVad) {
        vadDetach = window.MTVad.attach(stream, {
          onSilence: () => { if (recording) stopRec(); },
        });
      }
    } catch (err) {
      flashResult(`<div class="score-line tone-wrong">Mic denied: ${err.message}</div>`);
    }
  }

  function stopRec() {
    if (!recording) return;
    recording = false;
    if (vadDetach) { try { vadDetach(); } catch (e) {} vadDetach = null; }
    recBtn.classList.remove("recording");
    recBtn.textContent = "🎤 Record";
    try { recorder.stop(); } catch (e) {}
  }

  recBtn.addEventListener("click", () => { recording ? stopRec() : startRec(); });

  async function assess(blob) {
    if (!blob || !blob.size) {
      flashResult(`<div class="score-line tone-wrong">Empty recording, try again.</div>`);
      return;
    }
    const w = cur();
    busy = true;
    resultEl.hidden = false;
    resultEl.innerHTML = `<div class="score-line">⏳ Assessing pronunciation…</div>`;
    try {
      const fd = new FormData();
      fd.append("file", blob, "drill.webm");
      const url = API + "/assess?target_tone=" + w.tone +
                  "&target_pinyin=" + encodeURIComponent(w.py);
      const res = await fetch(url, { method: "POST", body: fd });
      if (!res.ok) throw new Error("assess " + res.status);
      const d = await res.json();
      renderScore(d, w);
    } catch (e) {
      flashResult(`<div class="score-line tone-wrong">Assessment failed: ${e.message}</div>`);
    } finally {
      busy = false;
    }
  }

  function ringColor(score) {
    if (score >= 85) return "#22c55e";
    if (score >= 60) return "#eab308";
    if (score >= 35) return "#f97316";
    return "#ef4444";
  }

  function renderScore(d, w) {
    if (!d.ok) {
      flashResult(`<div class="score-line tone-wrong">${d.reason === "no_voiced_speech"
        ? "Nothing heard. Try speaking louder." : "Could not assess, try again."}</div>`);
      return;
    }
    const heard = d.transcript ? `<div class="score-detail">Heard: <b>${d.transcript}</b></div>` : "";
    const toneOK = d.detected_tone === d.target_tone;
    const toneLine = toneOK
      ? `<div class="score-detail tone-right">✓ Your tone is correct (tone ${d.target_tone})</div>`
      : `<div class="score-detail tone-wrong">Your tone sounds like <b>tone ${d.detected_tone ?? "?"}</b>, should be <b>tone ${d.target_tone}</b>. Listen to the example and mimic the shape.</div>`;
    resultEl.hidden = false;
    resultEl.innerHTML =
      `<div class="score-ring" style="background:${ringColor(d.score)}">${d.score}</div>` +
      `<div class="score-line">${d.feedback}</div>` +
      heard + toneLine +
      `<div class="drill-actions"><button class="drill-btn listen" id="resListen">🔊 Listen to example</button></div>`;
    const rl = document.getElementById("resListen");
    if (rl) rl.addEventListener("click", () => listenBtn.click());
  }

  function flashResult(html) {
    resultEl.hidden = false;
    resultEl.innerHTML = html;
  }

  // ---- next word ----
  nextBtn.addEventListener("click", () => {
    idx = (idx + 1) % WORDS.length;
    renderWord();
  });

  // ---- public API: let curriculum load a lesson's items into the drill ----
  // Lesson items use {hanzi, pinyin, gloss, tone}; map to the drill's shape.
  window.MTDrill = {
    loadItems(items, label) {
      if (!Array.isArray(items) || !items.length) return;
      WORDS.length = 0;
      for (const it of items) {
        WORDS.push({ hz: it.hanzi, py: it.pinyin, en: it.gloss, tone: it.tone });
      }
      idx = 0;
      showTab("drill");
      renderWord();
      if (label) badgeEl.title = label;
    },
    open() { showTab("drill"); renderWord(); },
  };

  // init word (panel hidden until tab opened)
  renderWord();
})();
