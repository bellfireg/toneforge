// ToneForge — SRS Review tab (spaced-repetition due cards).
// Fetches /srs/due, shows each card, rates Again/Hard/Good/Easy -> /srs/review.
(function () {
  const API = (window.MT_CONFIG && window.MT_CONFIG.API_BASE) || "";

  // ── Panel is injected into <body>, tab registered with MTTabs ─────────────
  const tabBtn = document.getElementById("tabSRS");
  const panel  = document.getElementById("srsPanel");
  if (!tabBtn || !panel) return;

  if (window.MTTabs && typeof window.MTTabs.register === "function") {
    window.MTTabs.register("srs", panel, tabBtn);
  }

  tabBtn.addEventListener("click", () => {
    if (window.MTTabs) window.MTTabs.show("srs");
    load();
  });

  // ── State ─────────────────────────────────────────────────────────────────
  let cards  = [];   // due items from /srs/due
  let idx    = 0;
  let flipped = false;
  let busy   = false;
  let doneCount = 0;

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const counterEl  = document.getElementById("srsCounter");
  const cardArea   = document.getElementById("srsCardArea");
  const frontEl    = document.getElementById("srsFront");
  const backEl     = document.getElementById("srsBack");
  const flipBtn    = document.getElementById("srsFlip");
  const ratingRow  = document.getElementById("srsRatingRow");
  const emptyEl    = document.getElementById("srsEmpty");
  const loadingEl  = document.getElementById("srsLoading");

  // ── Load due cards ────────────────────────────────────────────────────────
  async function load() {
    setLoading(true);
    doneCount = 0; idx = 0; cards = [];
    try {
      const res = await fetch(API + "/srs/due?limit=20");
      if (!res.ok) throw new Error("srs/due " + res.status);
      const d = await res.json();
      cards = d.due || [];
      render();
    } catch (e) {
      showEmpty("Failed to load: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  function setLoading(on) {
    if (loadingEl) loadingEl.hidden = !on;
    if (on) {
      if (cardArea) cardArea.hidden = true;
      if (emptyEl)  emptyEl.hidden  = true;
    }
    // when turning off, render() decides what to show
  }

  // ── Render current card ───────────────────────────────────────────────────
  function render() {
    if (!cards.length) { showEmpty("No cards due — come back later! 🎉"); return; }
    if (idx >= cards.length) { showDone(); return; }

    const c = cards[idx];
    flipped = false;
    counterEl.textContent = `${idx + 1} / ${cards.length}`;

    // Front: hanzi + tone badge
    frontEl.innerHTML =
      `<div class="srs-hanzi">${c.item_key || "?"}</div>` +
      (c.pinyin ? `<div class="srs-pinyin">${c.pinyin}</div>` : "") +
      `<div class="srs-tap-hint">Tap to reveal</div>`;

    // Back: english + SRS metadata
    backEl.innerHTML =
      `<div class="srs-hanzi">${c.item_key || "?"}</div>` +
      (c.pinyin  ? `<div class="srs-pinyin">${c.pinyin}</div>`   : "") +
      (c.english ? `<div class="srs-english">${c.english}</div>` : "") +
      `<div class="srs-meta">Ease: ${(c.ease || 2.5).toFixed(1)} · Reps: ${c.reps || 0} · Lapses: ${c.lapses || 0}</div>`;

    cardArea.hidden   = false;
    emptyEl.hidden    = true;
    flipBtn.hidden    = false;
    ratingRow.hidden  = true;
    backEl.hidden     = true;
    frontEl.hidden    = false;
  }

  // ── Flip card ─────────────────────────────────────────────────────────────
  flipBtn.addEventListener("click", () => {
    if (flipped) return;
    flipped = true;
    frontEl.hidden   = true;
    backEl.hidden    = false;
    flipBtn.hidden   = true;
    ratingRow.hidden = false;
  });

  // tap front also flips
  frontEl && frontEl.addEventListener("click", () => flipBtn.click());

  // ── Rating buttons ────────────────────────────────────────────────────────
  // ratings: 1=Again 2=Hard 3=Good 4=Easy
  ratingRow.addEventListener("click", async (e) => {
    const btn = e.target.closest(".srs-rate-btn");
    if (!btn || busy) return;
    const rating = parseInt(btn.dataset.rating, 10);
    if (!rating) return;
    await submitRating(cards[idx].item_key, rating);
    idx++;
    doneCount++;
    render();
  });

  async function submitRating(itemKey, rating) {
    busy = true;
    try {
      const res = await fetch(API + "/srs/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_key: itemKey, rating }),
      });
      if (!res.ok) console.warn("srs/review", res.status);
      // refresh XP/progress after review
      if (window.MTProgress && window.MTProgress.refresh) window.MTProgress.refresh();
    } catch (e) {
      console.warn("srs review error", e);
    } finally {
      busy = false;
    }
  }

  // ── Empty / done states ───────────────────────────────────────────────────
  function showEmpty(msg) {
    if (cardArea) cardArea.hidden = true;
    emptyEl.hidden  = false;
    emptyEl.innerHTML = `<div class="srs-empty-msg">${msg}</div>`;
  }

  function showDone() {
    if (cardArea) cardArea.hidden = true;
    emptyEl.hidden  = false;
    emptyEl.innerHTML =
      `<div class="srs-done-icon">🎉</div>` +
      `<div class="srs-empty-msg">Session complete! Reviewed ${doneCount} card${doneCount === 1 ? "" : "s"}.</div>` +
      `<button class="recall-submit-btn" id="srsReload" type="button">Check for more</button>`;
    document.getElementById("srsReload") &&
      document.getElementById("srsReload").addEventListener("click", load);
  }

  // ── Expose refresh ────────────────────────────────────────────────────────
  window.MTSRS = { refresh: load };
})();
