// Mandarin Tutor — Progress & achievements (tab "Progress").
// Fetches /progress and renders streak, stats, and badge grid. Delegates tab
// switching to the central controller (window.MTTabs) like learn.js does.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const tabProgress = document.getElementById("tabProgress");
  const panel = document.getElementById("progress");
  const streakEl = document.getElementById("progStreak");
  const attemptsEl = document.getElementById("progAttempts");
  const avgEl = document.getElementById("progAvg");
  const doneEl = document.getElementById("progDone");
  const badgesEl = document.getElementById("progBadges");

  if (!tabProgress) return;

  // Register this panel with the central tab controller so it hides/shows
  // alongside the others (chat/learn/drill).
  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("progress", panel, tabProgress);
  }

  tabProgress.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("progress");
    load();
  });

  async function load() {
    badgesEl.innerHTML = `<div class="badge-desc">⏳ Loading…</div>`;
    try {
      const res = await fetch(API + "/progress");
      if (!res.ok) throw new Error("progress " + res.status);
      const p = await res.json();
      render(p);
    } catch (e) {
      badgesEl.innerHTML = `<div class="badge-desc tone-wrong">Failed to load: ${e.message}</div>`;
    }
  }

  function render(p) {
    streakEl.textContent = (p.streak && p.streak.current) || 0;
    attemptsEl.textContent = p.total_attempts || 0;
    avgEl.textContent = p.avg_score || 0;
    doneEl.textContent = (p.done_lessons && p.done_lessons.length) || 0;

    const earned = new Set((p.badges || []).map((b) => b.id));
    const all = p.all_badges || [];
    badgesEl.innerHTML = "";
    for (const b of all) {
      const got = earned.has(b.id);
      const card = document.createElement("div");
      card.className = "badge-card " + (got ? "earned" : "locked");
      card.innerHTML =
        `<div class="badge-label">${got ? b.label : "🔒 " + b.label.replace(/^\S+\s/, "")}</div>` +
        `<div class="badge-desc">${b.desc}</div>`;
      badgesEl.appendChild(card);
    }
  }

  // Expose a refresh hook so the drill can update progress after an attempt.
  window.MTProgress = { refresh: load };
})();
