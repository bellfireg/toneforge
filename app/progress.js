// ToneForge — Rich Progress dashboard (tab "🏆 Progress").
// Fetches /gamification/state + /stats and renders:
//   XP+level bar, streak calendar, per-level %, tone-vs-writing split,
//   weak-items list, daily activity SVG, achievements/badges.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const tabProgress = document.getElementById("tabProgress");
  const panel       = document.getElementById("progress");
  if (!tabProgress || !panel) return;

  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("progress", panel, tabProgress);
  }

  tabProgress.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("progress");
    load();
  });

  // ── Load both endpoints in parallel ───────────────────────────────────────
  async function load() {
    panel.innerHTML = `<div class="prog-loading">⏳ Loading progress…</div>`;
    try {
      const [gRes, sRes] = await Promise.all([
        fetch(API + "/gamification/state"),
        fetch(API + "/stats"),
      ]);
      if (!gRes.ok) throw new Error("gamification/state " + gRes.status);
      if (!sRes.ok) throw new Error("stats " + sRes.status);
      const [g, s] = await Promise.all([gRes.json(), sRes.json()]);
      render(g, s);
    } catch (e) {
      panel.innerHTML = `<div class="prog-error tone-wrong">Failed to load: ${e.message}</div>`;
    }
  }

  // ── Main render ───────────────────────────────────────────────────────────
  function render(g, s) {
    panel.innerHTML = "";
    panel.appendChild(buildXpSection(g));
    panel.appendChild(buildStreakSection(g, s));
    panel.appendChild(buildLevelSection(s));
    panel.appendChild(buildSplitSection(s));
    panel.appendChild(buildWeakSection(s));
    panel.appendChild(buildActivitySection(s));
    panel.appendChild(buildBadgesSection(g));
  }

  // ── XP + Level bar ────────────────────────────────────────────────────────
  function buildXpSection(g) {
    const sec = el("div", "prog-section prog-xp-section");
    const pct = Math.min(100, g.level_progress_pct || 0);
    sec.innerHTML =
      `<div class="prog-section-title">⚡ Level ${g.level || 1}</div>` +
      `<div class="prog-xp-row">` +
        `<div class="prog-xp-bar-wrap">` +
          `<div class="prog-xp-bar" style="width:${pct}%"></div>` +
        `</div>` +
        `<span class="prog-xp-label">${g.xp || 0} XP · ${g.xp_to_next || 0} to next</span>` +
      `</div>` +
      `<div class="prog-hearts">` +
        `${"❤️".repeat(Math.max(0, g.hearts || 0))}` +
        (g.hearts === 0 ? `<span class="prog-hearts-empty">No hearts — practice to refill</span>` : "") +
      `</div>`;
    return sec;
  }

  // ── Streak + calendar ─────────────────────────────────────────────────────
  function buildStreakSection(g, s) {
    const sec = el("div", "prog-section prog-streak-section");
    const streak = g.streak || 0;
    sec.innerHTML =
      `<div class="prog-section-title">🔥 ${streak} day streak</div>`;
    sec.appendChild(buildStreakCalendar(s.daily_activity || []));
    return sec;
  }

  function buildStreakCalendar(activity) {
    // Show last 14 days as small squares
    const wrap = el("div", "prog-calendar");
    const map  = {};
    for (const d of activity) map[d.date] = d.attempts;
    const today = new Date();
    for (let i = 13; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      const n   = map[key] || 0;
      const sq  = el("div", "cal-day" + (n > 0 ? " cal-active" : ""));
      sq.title  = key + (n ? ": " + n + " drills" : ": no activity");
      if (n >= 20) sq.classList.add("cal-hot");
      wrap.appendChild(sq);
    }
    return wrap;
  }

  // ── Per-level completion % ────────────────────────────────────────────────
  function buildLevelSection(s) {
    const sec = el("div", "prog-section");
    sec.innerHTML = `<div class="prog-section-title">📊 Level Progress</div>`;
    const pl = s.per_level || {};
    for (const [lvl, data] of Object.entries(pl)) {
      const pct   = data.pct || 0;
      const color = lvl === "basic" ? "#22c55e" : lvl === "intermediate" ? "#eab308" : "#f97316";
      const row   = el("div", "prog-level-row");
      row.innerHTML =
        `<span class="prog-level-lbl">${lvlLabel(lvl)}</span>` +
        `<div class="prog-bar-wrap">` +
          `<div class="prog-bar" style="width:${pct}%;background:${color}"></div>` +
        `</div>` +
        `<span class="prog-pct">${pct}%</span>` +
        `<span class="prog-count">${data.done}/${data.total}</span>`;
      sec.appendChild(row);
    }
    // per-unit detail collapsed list
    if ((s.per_unit || []).length) {
      const detail = el("details", "prog-unit-details");
      detail.innerHTML = `<summary>Unit breakdown</summary>`;
      for (const u of s.per_unit) {
        const urow = el("div", "prog-unit-row");
        urow.innerHTML =
          `<span class="prog-unit-name">${u.title}</span>` +
          `<span class="prog-unit-pct">${u.pct}%</span>`;
        detail.appendChild(urow);
      }
      sec.appendChild(detail);
    }
    return sec;
  }

  // ── Tone vs Writing split ─────────────────────────────────────────────────
  function buildSplitSection(s) {
    const sec  = el("div", "prog-section prog-split-section");
    const tone = s.tone    || { attempts: 0, avg_score: 0 };
    const writ = s.writing || { attempts: 0, avg_score: 0 };
    sec.innerHTML =
      `<div class="prog-section-title">🎯 Tone vs ✍️ Writing</div>` +
      `<div class="prog-split-grid">` +
        splitCard("🎯 Tone Drill", tone.attempts, tone.avg_score) +
        splitCard("✍️ Writing",    writ.attempts, writ.avg_score) +
      `</div>`;
    return sec;
  }

  function splitCard(label, attempts, avg) {
    const color = avg >= 85 ? "#22c55e" : avg >= 60 ? "#eab308" : avg >= 35 ? "#f97316" : "#94a3b8";
    return `<div class="prog-split-card">` +
      `<div class="prog-split-ring" style="border-color:${color}">${avg}</div>` +
      `<div class="prog-split-label">${label}</div>` +
      `<div class="prog-split-meta">${attempts} attempts</div>` +
    `</div>`;
  }

  // -- Weak items
  function buildWeakSection(s) {
    const sec  = el("div", "prog-section");
    const weak = s.weak_items || [];
    sec.innerHTML = '<div class="prog-section-title">\u26a0\ufe0f Review These</div>';
    if (!weak.length) {
      sec.innerHTML += '<div class="prog-empty-hint">No weak items -- great work!</div>';
      return sec;
    }
    const list = el("div", "prog-weak-list");
    for (const w of weak) {
      const row = el("div", "prog-weak-row");
      const color = w.best_score >= 60 ? "#eab308" : "#ef4444";
      row.innerHTML =
        '<span class="prog-weak-hanzi">' + w.hanzi + '</span>' +
        '<span class="prog-weak-score" style="color:' + color + '">' + w.best_score + '</span>';
      list.appendChild(row);
    }
    sec.appendChild(list);
    return sec;
  }

  // -- Daily activity inline SVG
  function buildActivitySection(s) {
    const sec = el("div", "prog-section");
    sec.innerHTML = '<div class="prog-section-title">\ud83d\udcc8 Daily Activity</div>';
    sec.appendChild(buildActivitySVG(s.daily_activity || []));
    return sec;
  }

  function buildActivitySVG(activity) {
    const W = 300, H = 60, PAD = 4;
    if (!activity.length) {
      const d = el("div", "prog-empty-hint");
      d.textContent = "No activity yet.";
      return d;
    }
    const today = new Date();
    const days  = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      days.push(d.toISOString().slice(0, 10));
    }
    const map = {};
    for (const d of activity) map[d.date] = d.attempts;
    const vals = days.map((d) => map[d] || 0);
    const maxV = Math.max(1, ...vals);
    const bW   = (W - PAD * 2) / vals.length - 2;
    let bars   = "";
    vals.forEach((v, i) => {
      const bH  = Math.max(2, Math.round(((H - PAD * 2) * v) / maxV));
      const x   = PAD + i * ((W - PAD * 2) / vals.length);
      const y   = H - PAD - bH;
      const col = v >= 20 ? "#22c55e" : v > 0 ? "#4ade80" : "#1f2937";
      bars +=
        '<rect x="' + x.toFixed(1) + '" y="' + y +
        '" width="' + bW.toFixed(1) + '" height="' + bH +
        '" rx="2" fill="' + col + '">' +
        '<title>' + days[i] + ': ' + v + ' drills</title></rect>';
    });
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Daily activity chart");
    svg.className = "prog-activity-svg";
    svg.innerHTML = bars;
    return svg;
  }

  // -- Badges / achievements
  function buildBadgesSection(g) {
    const sec = el("div", "prog-section");
    sec.innerHTML = '<div class="prog-section-title">\ud83c\udfc6 Achievements</div>';
    const badges = g.badges || [];
    if (!badges.length) {
      sec.innerHTML += '<div class="prog-empty-hint">No badges yet -- keep practicing!</div>';
      return sec;
    }
    const grid = el("div", "prog-badges");
    for (const b of badges) {
      const card = el("div", "badge-card earned");
      card.innerHTML =
        '<div class="badge-label">' + b.label + '</div>' +
        '<div class="badge-desc">'  + b.desc  + '</div>';
      grid.appendChild(card);
    }
    sec.appendChild(grid);
    return sec;
  }

  // -- Helpers
  function el(tag, cls) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    return e;
  }

  function lvlLabel(lvl) {
    return lvl === "basic" ? "\ud83d\udfe2 Basic"
         : lvl === "intermediate" ? "\ud83d\udfe1 Intermediate"
         : "\ud83d\udd34 Hard";
  }

  window.MTProgress = { refresh: load };
})();
