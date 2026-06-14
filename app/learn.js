// Mandarin Tutor — Curriculum browser (tab "Learn").
// Fetches /curriculum, renders units + lessons, and on tap loads a lesson's
// items into the drill via window.MTDrill.loadItems().
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const tabChat = document.getElementById("tabChat");
  const tabLearn = document.getElementById("tabLearn");
  const tabDrill = document.getElementById("tabDrill");
  const chatEl = document.getElementById("chat");
  const learnEl = document.getElementById("learn");
  const drillEl = document.getElementById("drill");
  const composer = document.querySelector(".composer");
  const listEl = document.getElementById("learnList");

  const LEVEL_LABELS = {
    basic: "🟢 Basic",
    intermediate: "🟡 Intermediate",
    hard: "🔴 Hard",
  };

  let loaded = false;

  // ---- tab switching delegates to the single controller in drill.js ----
  function showLearn() {
    if (window.MTTabs) window.MTTabs.show("learn");
    if (!loaded) loadCurriculum();
  }
  tabLearn.addEventListener("click", showLearn);

  async function loadCurriculum() {
    listEl.innerHTML = `<div class="lesson-goal">⏳ Loading curriculum…</div>`;
    try {
      const res = await fetch(API + "/curriculum");
      if (!res.ok) throw new Error("curriculum " + res.status);
      const data = await res.json();
      renderUnits(data.units || []);
      loaded = true;
    } catch (e) {
      listEl.innerHTML = `<div class="lesson-goal tone-wrong">Failed to load: ${e.message}</div>`;
    }
  }

  function renderUnits(units) {
    listEl.innerHTML = "";
    let lastLevel = null;
    for (const u of units) {
        const level = u.level || "basic";
        if (level !== lastLevel) {
          const lh = document.createElement("div");
          lh.className = "learn-level-title level-" + level;
          lh.textContent = LEVEL_LABELS[level] || level;
          listEl.appendChild(lh);
          lastLevel = level;
        }

        const title = document.createElement("div");
        title.className = "learn-unit-title" + (u.locked ? " locked" : "");
        title.textContent = (u.locked ? "🔒 " : "") + u.title;
        listEl.appendChild(title);

        const desc = document.createElement("div");
        desc.className = "learn-unit-desc";
        desc.textContent = u.locked
          ? u.desc + "  —  unlock by passing the previous level's capstone."
          : u.desc;
        listEl.appendChild(desc);

        for (const l of u.lessons) {
          listEl.appendChild(lessonCard(l, u.locked));
        }
    }
  }

  function lessonCard(l, unitLocked) {
    const card = document.createElement("div");
    const done = l.all_passed === true;
    const started = (l.items_passed || 0) > 0 || (l.best_avg || 0) > 0;
    card.className = "lesson-card" +
      (done ? " done" : "") + (unitLocked ? " locked" : "");

    const passed = l.items_passed || 0;
    const totalItems = l.items_total || l.count || 0;
    let progressLine;
    if (done) {
      progressLine = `<span class="lesson-check">✓ ${l.best_avg} avg</span>`;
    } else if (started) {
      progressLine = `<span class="lesson-progress">${passed}/${totalItems} passed · ${l.best_avg} avg</span>`;
    } else {
      progressLine = "";
    }

    card.innerHTML =
      `<div class="lesson-title">${l.capstone ? "⭐ " : ""}${l.title}${progressLine}</div>` +
      `<div class="lesson-goal">${l.goal}</div>` +
      `<div class="lesson-meta">${totalItems} words · ${
        unitLocked ? "locked" : (started && !done ? "tap to re-learn" : "tap to practice")
      }</div>`;
    if (!unitLocked) card.addEventListener("click", () => openLesson(l.id));
    return card;
  }

  async function openLesson(lessonId) {
    try {
      const res = await fetch(API + "/lesson/" + encodeURIComponent(lessonId));
      if (!res.ok) throw new Error("lesson " + res.status);
      const lesson = await res.json();
      // Hand the lesson's items to the drill engine (shared renderer).
      // loadItems() itself switches to the drill tab via the central controller.
      if (window.MTDrill && typeof window.MTDrill.loadItems === "function") {
        window.MTDrill.loadItems(lesson.items, lesson.title);
        window.__MT_CURRENT_LESSON = lessonId; // used by progress phase
      }
      // Also feed the same items into the Writing module (silently, no tab
      // switch) so the learner can practice writing the same lesson's chars.
      if (window.MTWrite && typeof window.MTWrite.loadItems === "function") {
        window.MTWrite.loadItems(lesson.items, lessonId);
      }
    } catch (e) {
      listEl.innerHTML =
        `<div class="lesson-goal tone-wrong">Failed to open lesson: ${e.message}</div>` +
        listEl.innerHTML;
    }
  }

  // Completed lessons are tracked locally for now (server progress later).
  function getDone() {
    try { return JSON.parse(localStorage.getItem("mt_done") || "[]"); }
    catch (e) { return []; }
  }

  // Expose a tiny hook so the progress phase can refresh "done" badges.
  window.MTLearn = { refresh: () => { loaded = false; if (learnEl.classList.contains("show")) loadCurriculum(); } };
})();
