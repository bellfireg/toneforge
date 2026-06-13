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
    const done = getDone();
    for (const u of units) {
      const title = document.createElement("div");
      title.className = "learn-unit-title";
      title.textContent = u.title;
      listEl.appendChild(title);

      const desc = document.createElement("div");
      desc.className = "learn-unit-desc";
      desc.textContent = u.desc;
      listEl.appendChild(desc);

      for (const l of u.lessons) {
        listEl.appendChild(lessonCard(l, done.includes(l.id)));
      }
    }
  }

  function lessonCard(l, isDone) {
    const card = document.createElement("div");
    card.className = "lesson-card" + (isDone ? " done" : "");
    card.innerHTML =
      `<div class="lesson-title">${l.title}` +
      (isDone ? `<span class="lesson-check">✓ done</span>` : "") +
      `</div>` +
      `<div class="lesson-goal">${l.goal}</div>` +
      `<div class="lesson-meta">${l.count} words · tap to practice</div>`;
    card.addEventListener("click", () => openLesson(l.id));
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
