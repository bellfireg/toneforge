// ToneForge — Writing practice (free scratchpad recognition).
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";
  const DATASET = "mmah";
  const DATA_URL = "vendor/hanzilookup/mmah.json";
  const MIN_DIST = 3.5;

  const tabWrite = document.getElementById("tabWrite");
  const panel = document.getElementById("write");
  const targetEl = document.getElementById("writeTarget");
  const pinyinEl = document.getElementById("writePinyin");
  const enEl = document.getElementById("writeEn");
  const countEl = document.getElementById("writeCharCount");
  const canvas = document.getElementById("writeCanvas");
  const resultEl = document.getElementById("writeResult");
  const candidatesEl = document.getElementById("writeCandidates");
  const btnUndo = document.getElementById("writeUndo");
  const btnClear = document.getElementById("writeClear");
  const btnCheck = document.getElementById("writeCheck");
  const btnNext = document.getElementById("writeNext");
  if (!tabWrite || !panel || !canvas) return;
  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("write", panel, tabWrite);
  }
  let items = [
    { hz: "你", py: "nǐ", en: "you" },
    { hz: "好", py: "hǎo", en: "good" },
    { hz: "我", py: "wǒ", en: "I / me" },
  ];
  let idx = 0;
  let lessonId = "";
  let charIndex = 0;
  let charScores = [];
  let strokes = [];
  let activeStroke = null;
  let activePointer = null;
  let matcher = null;
  let engineReady = false;
  let engineLoading = false;
  const ctx = canvas.getContext("2d");
  function cur() { return items[idx] || items[0]; }
  function hanziChars(hz) {
    return Array.from(hz || "").filter((c) => /[\u3400-\u9fff]/.test(c));
  }
  function currentChars() {
    const list = hanziChars(cur().hz); return list.length ? list : ["你"];
  }
  function currentChar() {
    const list = currentChars(); return list[Math.min(charIndex, list.length - 1)];
  }
  function initEngine() {
    if (engineReady || engineLoading) return;
    engineLoading = true;
    if (!window.HanziLookup || !HanziLookup.init) {
      showStatus("Handwriting engine is not loaded.", true);
      return;
    }
    HanziLookup.init(DATASET, DATA_URL, function (ok) {
      engineLoading = false;
      engineReady = !!ok;
      if (ok) {
        matcher = new HanziLookup.Matcher(DATASET);
        showStatus("Ready when you are.", false, true);
      } else {
        showStatus("Could not load handwriting data.", true);
      }
    });
  }
  function render() {
    const item = cur();
    const list = currentChars();
    if (charIndex >= list.length) charIndex = 0;
    targetEl.textContent = "target: " + currentChar();
    pinyinEl.textContent = item.py || "";
    enEl.textContent = item.en || "";
    countEl.textContent = `character ${charIndex + 1} of ${list.length}`;
    clearCanvas(false);
    resultEl.hidden = true;
    resultEl.innerHTML = "";
    candidatesEl.hidden = true;
    candidatesEl.innerHTML = "";
    resizeCanvas();
    initEngine();
  }
  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const size = Math.max(260, Math.round(Math.min(rect.width || 320, 460)));
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== size * dpr || canvas.height !== size * dpr) {
      canvas.width = size * dpr;
      canvas.height = size * dpr;
      canvas.style.height = size + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      redraw();
    }
  }
  function pointFromEvent(ev) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(256, ((ev.clientX - rect.left) / rect.width) * 256));
    const y = Math.max(0, Math.min(256, ((ev.clientY - rect.top) / rect.height) * 256));
    return [x, y];
  }
  function drawPointLine(a, b, pressure) {
    const rect = canvas.getBoundingClientRect();
    const scale = rect.width / 256;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = Math.max(8, 12 * (pressure || 0.7));
    ctx.beginPath();
    ctx.moveTo(a[0] * scale, a[1] * scale);
    ctx.lineTo(b[0] * scale, b[1] * scale);
    ctx.stroke();
  }
  function redraw() {
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    strokes.forEach((stroke) => {
      if (!stroke.length) return;
      if (stroke.length === 1) drawPointLine(stroke[0], stroke[0], 0.7);
      for (let i = 1; i < stroke.length; i += 1) {
        drawPointLine(stroke[i - 1], stroke[i], 0.7);
      }
    });
  }
  function distance(a, b) {
    const dx = a[0] - b[0], dy = a[1] - b[1];
    return Math.sqrt(dx * dx + dy * dy);
  }
  function onPointerDown(ev) {
    ev.preventDefault();
    resizeCanvas();
    activePointer = ev.pointerId;
    canvas.setPointerCapture(activePointer);
    activeStroke = [pointFromEvent(ev)];
    strokes.push(activeStroke);
    resultEl.hidden = true;
  }
  function onPointerMove(ev) {
    if (activePointer !== ev.pointerId || !activeStroke) return;
    ev.preventDefault();
    const pt = pointFromEvent(ev);
    const prev = activeStroke[activeStroke.length - 1];
    if (distance(prev, pt) < MIN_DIST) return;
    activeStroke.push(pt);
    drawPointLine(prev, pt, ev.pressure || 0.7);
  }
  function onPointerUp(ev) {
    if (activePointer !== ev.pointerId || !activeStroke) return;
    ev.preventDefault();
    const pt = pointFromEvent(ev);
    const prev = activeStroke[activeStroke.length - 1];
    if (distance(prev, pt) >= 1) {
      activeStroke.push(pt);
      drawPointLine(prev, pt, ev.pressure || 0.7);
    }
    activeStroke = null;
    activePointer = null;
  }
  function clearCanvas(hideResult) {
    strokes = [];
    activeStroke = null;
    activePointer = null;
    redraw();
    if (hideResult !== false) {
      resultEl.hidden = true;
      candidatesEl.hidden = true;
    }
  }
  function undoStroke() {
    strokes.pop();
    redraw();
    resultEl.hidden = true;
    candidatesEl.hidden = true;
  }
  function scoreFromRank(rank, match) {
    let base;
    if (rank === 0) base = 98;
    else if (rank === 1) base = 88;
    else if (rank === 2) base = 80;
    else if (rank === 3) base = 72;
    else if (rank >= 4 && rank <= 7) base = 60 - (rank - 4) * 3;
    else base = 30;
    if (match && typeof match.score === "number" && Number.isFinite(match.score)) {
      const adjustment = Math.max(-4, Math.min(4, match.score));
      base = Math.round(base + adjustment);
    }
    return Math.max(0, Math.min(100, base));
  }
  function scoreTone(score) {
    if (score >= 90) return ["Excellent — looks just like " + currentChar() + "!", "excellent"];
    if (score >= 70) return ["Close", "close"];
    return ["Keep practicing", "practice"];
  }
  function showStatus(text, isError, quiet) {
    if (quiet && !resultEl.hidden) return;
    resultEl.hidden = false;
    resultEl.innerHTML = `<div class="write-status${isError ? " error" : ""}">${text}</div>`;
  }
  function checkWriting() {
    if (!strokes.length) {
      showStatus("Write the character first.", true);
      return;
    }
    if (!engineReady || !matcher) {
      showStatus("Loading handwriting engine...", false);
      initEngine();
      return;
    }
    let analyzed;
    try {
      analyzed = new HanziLookup.AnalyzedCharacter(strokes);
    } catch (err) {
      showStatus("Could not analyze those strokes. Try clearing and writing again.", true);
      return;
    }
    btnCheck.disabled = true;
    matcher.match(analyzed, 8, function (matches) {
      btnCheck.disabled = false;
      const target = currentChar();
      const rank = matches.findIndex((m) => m.character === target);
      const score = scoreFromRank(rank, rank >= 0 ? matches[rank] : null);
      charScores[charIndex] = score;
      showResult(score, matches, rank);
      report(score);
    });
  }
  function showResult(score, matches, rank) {
    const tone = scoreTone(score);
    resultEl.hidden = false;
    resultEl.innerHTML =
      `<div class="write-percent ${tone[1]}">${score}%</div>` +
      `<div class="write-line">${tone[0]}</div>` +
      `<div class="write-detail">rank: ${rank >= 0 ? rank + 1 : "not found"}</div>`;
    candidatesEl.hidden = false;
    candidatesEl.innerHTML = matches.length
      ? matches.map((m, i) => `<span class="${m.character === currentChar() ? "hit" : ""}">${i + 1}. ${m.character}</span>`).join("")
      : "<span>No candidates recognized</span>";
  }
  async function report(score) {
    const all = charScores.filter((s) => typeof s === "number");
    const average = Math.round(all.reduce((sum, s) => sum + s, 0) / Math.max(1, all.length));
    try {
      await fetch(API + "/write-assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hanzi: cur().hz,
          mode: "scratch",
          score: currentChars().length > 1 ? average : score,
          mistakes: 0,
          lesson_id: window.__MT_CURRENT_LESSON || lessonId || "",
        }),
      });
    } catch (e) { /* score is still useful if the network is unavailable */ }
    if (window.MTLearn && typeof window.MTLearn.refresh === "function") window.MTLearn.refresh();
    if (window.MTProgress && typeof window.MTProgress.refresh === "function") window.MTProgress.refresh();
  }
  function nextCharacterOrItem() {
    const list = currentChars();
    if (charIndex < list.length - 1) {
      charIndex += 1;
    } else {
      idx = (idx + 1) % items.length;
      charIndex = 0;
      charScores = [];
    }
    render();
  }
  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerUp);
  window.addEventListener("resize", resizeCanvas);
  if (btnUndo) btnUndo.addEventListener("click", undoStroke);
  if (btnClear) btnClear.addEventListener("click", () => clearCanvas(true));
  if (btnCheck) btnCheck.addEventListener("click", checkWriting);
  if (btnNext) btnNext.addEventListener("click", nextCharacterOrItem);
  tabWrite.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("write");
    render();
  });

  window.MTWrite = {
    loadItems(lessonItems, id) {
      if (!Array.isArray(lessonItems) || !lessonItems.length) return;
      items = lessonItems.map((it) => ({ hz: it.hanzi, py: it.pinyin, en: it.gloss }));
      lessonId = id || "";
      idx = 0;
      charIndex = 0;
      charScores = [];
      render();
    },
    open() {
      if (window.MTTabs) window.MTTabs.show("write");
      render();
    },
  };
  render();
})();
