// ToneForge — Writing practice (tab "✍️ Write").
// Uses Hanzi Writer (client-side, offline, no Google services — works on
// Huawei tablets without GMS). Three modes per character:
//   learn  — watch the stroke-order animation
//   trace  — draw over a faint outline, hints after misses (guided)
//   recall — blank canvas, NO outline (memory test, the "tulis 'aku bisa'" ask)
// Stroke accuracy is scored from Hanzi Writer's mistake count and POSTed to
// /write-assess so writing progress tracks alongside tone progress.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";
  const CDN_DATA = "https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1";

  // DOM (added to index.html)
  const tabWrite = document.getElementById("tabWrite");
  const panel = document.getElementById("write");
  const targetEl = document.getElementById("writeTarget");
  const pinyinEl = document.getElementById("writePinyin");
  const enEl = document.getElementById("writeEn");
  const stage = document.getElementById("writeStage");
  const resultEl = document.getElementById("writeResult");
  const modeLabel = document.getElementById("writeModeLabel");
  const btnAnim = document.getElementById("writeAnimate");
  const btnTrace = document.getElementById("writeTrace");
  const btnRecall = document.getElementById("writeRecall");
  const btnNext = document.getElementById("writeNext");

  if (!tabWrite || !panel) return;

  // Register with the central tab controller (defined in drill.js).
  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("write", panel, tabWrite);
  }

  // Default practice set until a lesson is loaded from Learn.
  let items = [
    { hz: "你", py: "nǐ", en: "you" },
    { hz: "好", py: "hǎo", en: "good" },
    { hz: "我", py: "wǒ", en: "I / me" },
  ];
  let idx = 0;
  let lessonId = "";
  let mode = "trace";
  let writers = [];     // one HanziWriter per character in the current item
  let curMistakes = 0;
  let curStrokes = 0;
  let doneChars = 0;

  function cur() { return items[idx]; }

  // Split a word ("你好") into its individual hanzi, ignoring spaces/latin.
  function chars(hz) {
    return Array.from(hz).filter((c) => /[\u3400-\u9fff]/.test(c));
  }

  function setMode(m) {
    mode = m;
    [["learn", btnAnim], ["trace", btnTrace], ["recall", btnRecall]].forEach(
      ([name, btn]) => btn && btn.classList.toggle("active", name === mode));
    modeLabel.textContent =
      mode === "learn" ? "Watch the stroke order" :
      mode === "trace" ? "Trace over the outline" :
      "✍️ Write from memory — no guide";
    render();
  }

  function render() {
    const w = cur();
    targetEl.textContent = mode === "recall" ? "?" : w.hz;
    pinyinEl.textContent = w.py;
    enEl.textContent = mode === "recall" ? `Write: "${w.en}"` : w.en;
    resultEl.hidden = true;
    resultEl.innerHTML = "";
    buildStage(w.hz);
  }

  // Tear down old writers, lay out one canvas box per character, then start.
  function buildStage(hz) {
    stage.innerHTML = "";
    writers = [];
    curMistakes = 0;
    curStrokes = 0;
    doneChars = 0;
    const list = chars(hz);
    if (!list.length) {
      stage.innerHTML = `<div class="write-msg">No character to write.</div>`;
      return;
    }
    list.forEach((ch, i) => {
      const box = document.createElement("div");
      box.className = "write-box";
      box.id = "wbox" + i;
      stage.appendChild(box);
      const writer = HanziWriter.create(box, ch, {
        width: 150,
        height: 150,
        padding: 8,
        showCharacter: mode === "learn",
        showOutline: mode !== "recall",
        strokeColor: "#5e"+"ead4",
        outlineColor: "#374151",
        drawingColor: "#22c55e",
        drawingWidth: 28,
        showHintAfterMisses: mode === "trace" ? 3 : false,
        charDataLoader: (c, onComplete) => {
          fetch(`${CDN_DATA}/${encodeURIComponent(c)}.json`)
            .then((r) => r.json()).then(onComplete)
            .catch(() => onComplete(null));
        },
      });
      writers.push(writer);
    });

    if (mode === "learn") {
      animateAll(0);
    } else {
      startQuiz(0);   // quiz characters one at a time, left to right
    }
  }

  function animateAll(i) {
    if (i >= writers.length) return;
    writers[i].animateCharacter({ onComplete: () => {
      setTimeout(() => animateAll(i + 1), 250);
    }});
  }

  function startQuiz(i) {
    if (i >= writers.length) { finish(); return; }
    writers[i].quiz({
      onMistake: () => { curMistakes += 1; },
      onCorrectStroke: () => { curStrokes += 1; },
      onComplete: () => { doneChars += 1; startQuiz(i + 1); },
    });
  }

  // Convert stroke mistakes into a 0..100 score, then report it.
  function finish() {
    const totalStrokes = Math.max(1, curStrokes + curMistakes);
    // Tolerance scales with character complexity (more strokes => more grace).
    const tolerance = curStrokes * 1.5 || 1.5;
    let score = Math.round(100 * (1 - curMistakes / (tolerance + curMistakes)));
    score = Math.max(0, Math.min(100, score));

    const stars = score >= 90 ? "🌟🌟🌟" : score >= 70 ? "⭐⭐" : score >= 50 ? "⭐" : "";
    const msg =
      score >= 90 ? "Perfect strokes!" :
      score >= 70 ? "Great — clean writing." :
      score >= 50 ? "Getting there, watch the stroke order." :
      "Keep practicing the stroke order.";

    resultEl.hidden = false;
    resultEl.innerHTML =
      `<div class="write-score" style="background:${ringColor(score)}">${score}</div>` +
      `<div class="write-line">${stars} ${msg}</div>` +
      `<div class="write-detail">${curMistakes} mistake${curMistakes === 1 ? "" : "s"} · mode: ${mode}</div>`;

    report(score, curMistakes);
  }

  function ringColor(s) {
    if (s >= 85) return "#22c55e";
    if (s >= 60) return "#eab308";
    if (s >= 35) return "#f97316";
    return "#ef4444";
  }

  async function report(score, mistakes) {
    const w = cur();
    try {
      await fetch(API + "/write-assess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hanzi: w.hz, mode, score, mistakes,
          lesson_id: window.__MT_CURRENT_LESSON || lessonId || "",
        }),
      });
    } catch (e) { /* non-fatal: scoring still shown */ }
    // Refresh Learn + Progress so writing progress updates live.
    if (window.MTLearn && typeof window.MTLearn.refresh === "function") window.MTLearn.refresh();
    if (window.MTProgress && typeof window.MTProgress.refresh === "function") window.MTProgress.refresh();
  }

  // ---- buttons ----
  if (btnAnim) btnAnim.addEventListener("click", () => setMode("learn"));
  if (btnTrace) btnTrace.addEventListener("click", () => setMode("trace"));
  if (btnRecall) btnRecall.addEventListener("click", () => setMode("recall"));
  if (btnNext) btnNext.addEventListener("click", () => {
    idx = (idx + 1) % items.length;
    render();
  });

  tabWrite.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("write");
    if (!writers.length) render();
  });

  // ---- public API: Learn loads a lesson's items into Writing too ----
  window.MTWrite = {
    loadItems(lessonItems, id) {
      if (!Array.isArray(lessonItems) || !lessonItems.length) return;
      items = lessonItems.map((it) => ({ hz: it.hanzi, py: it.pinyin, en: it.gloss }));
      lessonId = id || "";
      idx = 0;
      setMode("trace");
    },
    open() { if (window.MTTabs) window.MTTabs.show("write"); render(); },
  };
})();
