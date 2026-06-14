// ToneForge — Daily Challenges tab.
// GET /challenge/today -> show items, POST /challenge/complete per item -> XP anim.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  const tabBtn = document.getElementById("tabChallenge");
  const panel  = document.getElementById("challengePanel");
  if (!tabBtn || !panel) return;

  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("challenge", panel, tabBtn);
  }

  tabBtn.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("challenge");
    load();
  });

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const dateEl    = document.getElementById("challDate");
  const listEl    = document.getElementById("challList");
  const statusEl  = document.getElementById("challStatus");
  const doneEl    = document.getElementById("challDone");

  let challenge   = null;
  let busy        = false;

  // ── Load today's challenge ────────────────────────────────────────────────
  async function load() {
    listEl.innerHTML = `<div class="chall-loading">⏳ Loading challenge…</div>`;
    doneEl.hidden    = true;
    try {
      const res = await fetch(API + "/challenge/today");
      if (!res.ok) throw new Error("challenge/today " + res.status);
      challenge = await res.json();
      render();
    } catch (e) {
      listEl.innerHTML = `<div class="chall-error tone-wrong">Failed: ${e.message}</div>`;
    }
  }

  // ── Render challenge ──────────────────────────────────────────────────────
  function render() {
    if (!challenge) return;
    dateEl.textContent = challenge.date || "";
    const items    = challenge.items  || [];
    const done     = new Set(challenge.done || []);
    const finished = challenge.finished === true;

    listEl.innerHTML = "";

    if (!items.length) {
      listEl.innerHTML = `<div class="chall-empty">No challenge items for today.</div>`;
      return;
    }

    for (const item of items) {
      const isDone = done.has(item);
      const row = document.createElement("div");
      row.className = "chall-item" + (isDone ? " chall-done" : "");
      row.dataset.item = item;
      row.innerHTML =
        `<span class="chall-item-text">${item}</span>` +
        (isDone
          ? `<span class="chall-check">✓</span>`
          : `<button class="chall-btn" type="button" data-item="${item}">Mark done</button>`);
      listEl.appendChild(row);
    }

    const total     = items.length;
    const doneCount = done.size;
    statusEl.textContent = `${doneCount} / ${total} complete`;

    if (finished) showFinished();
  }

  // ── Complete an item ──────────────────────────────────────────────────────
  listEl.addEventListener("click", async (e) => {
    const btn = e.target.closest(".chall-btn");
    if (!btn || busy) return;
    const item = btn.dataset.item;
    if (!item) return;
    busy = true;
    btn.disabled = true;
    try {
      const res = await fetch(API + "/challenge/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item }),
      });
      if (!res.ok) throw new Error("challenge/complete " + res.status);
      const d = await res.json();

      // Animate XP gain
      if (d.xp_awarded) showXpPop("+" + d.xp_awarded + " XP", btn);

      // Update local state
      if (!challenge.done) challenge.done = [];
      if (!challenge.done.includes(item)) challenge.done.push(item);
      if (d.finished) challenge.finished = true;

      render();
      if (window.MTProgress && window.MTProgress.refresh) window.MTProgress.refresh();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "Error — retry";
    } finally {
      busy = false;
    }
  });

  // ── XP pop animation (CSS only) ───────────────────────────────────────────
  function showXpPop(text, anchor) {
    const pop = document.createElement("div");
    pop.className = "xp-pop";
    pop.textContent = text;
    const rect = anchor.getBoundingClientRect();
    pop.style.left = rect.left + "px";
    pop.style.top  = (rect.top + window.scrollY - 32) + "px";
    document.body.appendChild(pop);
    pop.addEventListener("animationend", () => pop.remove());
  }

  function showFinished() {
    doneEl.hidden = false;
    doneEl.innerHTML =
      `<div class="chall-finished">🎉 Challenge complete! Come back tomorrow.</div>`;
  }

  window.MTChallenge = { refresh: load };
})();
