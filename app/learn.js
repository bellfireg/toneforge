// Mandarin Tutor — Curriculum browser (tab "Learn").
// Fetches /curriculum + /lesson-scores per lesson, renders a sequential
// level-path UI (lock / checkmark / score per item). Gating logic:
//   item[i] locked  unless item[i-1] score green (tone>=70 OR write>=65)
// Boss lessons (is_boss=true) shown with a BOSS crown badge.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const tabLearn = document.getElementById("tabLearn");
  const learnEl  = document.getElementById("learn");
  const listEl   = document.getElementById("learnList");

  const LEVEL_LABELS = {
    basic:        "🟢 Basic",
    intermediate: "🟡 Intermediate",
    hard:         "🔴 Hard",
  };

  // Pass thresholds (mirrors backend constants)
  const TONE_PASS  = 70;
  const WRITE_PASS = 65;

  let loaded = false;

  // ---- tab switching delegates to the single controller in drill.js ----
  function showLearn() {
    if (window.MTTabs) window.MTTabs.show("learn");
    if (!loaded) loadCurriculum();
  }
  tabLearn.addEventListener("click", showLearn);

  // ---- load curriculum outline ----
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

  // ---- render all units ----
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

  // ---- lesson card with expandable item-path ----
  function lessonCard(l, unitLocked) {
    const card = document.createElement("div");
    const done    = l.all_passed === true;
    const started = (l.items_passed || 0) > 0 || (l.best_avg || 0) > 0;
    const isBoss  = l.is_boss === true || l.capstone === true;
    const locked  = !!unitLocked;

    card.className = "lesson-card" +
      (done ? " done" : "") +
      (locked ? " locked" : "") +
      (isBoss ? " boss-lesson" : "");

    const passed     = l.items_passed || 0;
    const totalItems = l.items_total || l.count || 0;

    let progressLine = "";
    if (done) {
      progressLine = `<span class="lesson-check">✓ ${l.best_avg} avg</span>`;
    } else if (started) {
      progressLine = `<span class="lesson-progress">${passed}/${totalItems} passed · ${l.best_avg} avg</span>`;
    }

    const bossBadge = isBoss
      ? `<span class="lesson-boss-badge">👑 BOSS</span>`
      : "";

    card.innerHTML =
      `<div class="lesson-title">${bossBadge}${l.title}${progressLine}</div>` +
      `<div class="lesson-goal">${l.goal}</div>` +
      `<div class="lesson-meta">${totalItems} words · ${
        locked ? "locked" :
        isBoss ? "boss fight — no guide!" :
        started && !done ? "tap to re-learn" : "tap to practice"
      }</div>` +
      `<div class="item-path" id="path-${l.id}"></div>`;

    if (!locked) {
      card.addEventListener("click", (e) => {
        // Don't re-trigger if clicking inside the path area itself
        if (e.target.closest(".item-path-node")) return;
        openLesson(l.id, card);
      });
      // Eagerly load item scores to render the path
      loadItemPath(l.id, card, locked);
    }
    return card;
  }

  // ---- fetch per-item scores and render the level path ----
  async function loadItemPath(lessonId, card, unitLocked) {
    const pathEl = card.querySelector(".item-path");
    if (!pathEl) return;
    try {
      const res = await fetch(API + "/lesson-scores/" + encodeURIComponent(lessonId));
      if (!res.ok) return; // silently skip if endpoint unavailable
      const data = await res.json();
      const items = data.ordered_items || [];
      if (!items.length) return;
      renderItemPath(pathEl, items, lessonId, unitLocked);
    } catch (_) { /* non-fatal */ }
  }

  // ---- render the sequential level-path nodes ----
  function renderItemPath(pathEl, items, lessonId, unitLocked) {
    pathEl.innerHTML = "";

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      // Lock logic: item 0 always unlocked (if unit not locked);
      // item[i] locked if item[i-1] not green
      const prevGreen = i === 0 ? true : isGreen(items[i - 1]);
      const itemLocked = unitLocked || !prevGreen;

      const node = document.createElement("div");
      node.className = "item-path-node" + (itemLocked ? " item-locked" : "");

      const stateIcon = itemLocked
        ? "🔒"
        : isGreen(item)
          ? "✅"
          : item.score > 0
            ? "🟡"
            : "⬜";

      const scoreLabel = item.score > 0
        ? `<span class="item-score">${item.score}</span>`
        : "";

      node.innerHTML =
        `<span class="item-state">${stateIcon}</span>` +
        `<span class="item-hanzi">${item.hanzi || ""}</span>` +
        scoreLabel;

      node.setAttribute("aria-label",
        `${item.hanzi} — ${itemLocked ? "locked" : isGreen(item) ? "passed" : "practice"}`);

      if (!itemLocked) {
        node.setAttribute("role", "button");
        node.setAttribute("tabindex", "0");
        node.addEventListener("click", (e) => {
          e.stopPropagation();
          openLessonAtItem(lessonId, i);
        });
        node.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openLessonAtItem(lessonId, i);
          }
        });
      }

      pathEl.appendChild(node);

      // connector arrow between nodes (not after last)
      if (i < items.length - 1) {
        const sep = document.createElement("span");
        sep.className = "item-path-sep";
        sep.setAttribute("aria-hidden", "true");
        sep.textContent = "→";
        pathEl.appendChild(sep);
      }
    }
  }

  // item is green if tone score >= TONE_PASS OR write score >= WRITE_PASS
  function isGreen(item) {
    if (!item) return false;
    if (item.green === true) return true;
    const s = item.score || 0;
    return s >= TONE_PASS;
  }

  // ---- open full lesson (loads all items into drill, switches tab) ----
  async function openLesson(lessonId, card) {
    try {
      const res = await fetch(API + "/lesson/" + encodeURIComponent(lessonId));
      if (!res.ok) throw new Error("lesson " + res.status);
      const lesson = await res.json();

      if (window.MTDrill && typeof window.MTDrill.loadItems === "function") {
        window.MTDrill.loadItems(lesson.items, lesson.title);
        window.__MT_CURRENT_LESSON = lessonId;
      }
      if (window.MTWrite && typeof window.MTWrite.loadItems === "function") {
        window.MTWrite.loadItems(lesson.items, lessonId);
      }
    } catch (e) {
      if (card) {
        const errEl = document.createElement("div");
        errEl.className = "lesson-goal tone-wrong";
        errEl.textContent = "Failed to open: " + e.message;
        card.appendChild(errEl);
      }
    }
  }

  // ---- open lesson starting at a specific item index ----
  async function openLessonAtItem(lessonId, startIdx) {
    try {
      const res = await fetch(API + "/lesson/" + encodeURIComponent(lessonId));
      if (!res.ok) throw new Error("lesson " + res.status);
      const lesson = await res.json();

      // Rotate items so chosen item is first
      const items = lesson.items || [];
      const rotated = [...items.slice(startIdx), ...items.slice(0, startIdx)];

      if (window.MTDrill && typeof window.MTDrill.loadItems === "function") {
        window.MTDrill.loadItems(rotated, lesson.title);
        window.__MT_CURRENT_LESSON = lessonId;
      }
      if (window.MTWrite && typeof window.MTWrite.loadItems === "function") {
        window.MTWrite.loadItems(rotated, lessonId);
      }
    } catch (e) { /* silently ignore */ }
  }

  // ---- public API: refresh "done" badges after drill/write scores in ----
  window.MTLearn = {
    refresh() {
      loaded = false;
      if (learnEl.classList.contains("show")) loadCurriculum();
    },
  };
})();
