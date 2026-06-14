// ToneForge — Free-canvas scratchpad (tab "✍️ Write" → Scratchpad sub-mode).
// Pointer Events API: works with Huawei M-Pencil pressure, touch, and mouse.
// No guide overlay — blank canvas for free practice.
(function () {
  const tabWrite = document.getElementById("tabWrite");
  const writePanel = document.getElementById("write");
  if (!tabWrite || !writePanel) return;

  // ── Build sub-tab bar inside the write panel ──────────────────────────────
  // Insert before existing write-card so guided modes stay intact.
  const subNav = document.createElement("div");
  subNav.className = "write-subnav";
  subNav.innerHTML =
    `<button class="write-subtab active" data-sub="guided" type="button">✏️ Guided</button>` +
    `<button class="write-subtab" data-sub="scratchpad" type="button">🖊️ Scratchpad</button>` +
    `<button class="write-subtab" data-sub="recall-sent" type="button">📝 Sentence Recall</button>`;
  writePanel.insertBefore(subNav, writePanel.firstChild);

  const guidedCard = writePanel.querySelector(".write-card");
  // recall panel is injected by recall.js — look it up lazily

  // ── Build scratchpad panel ────────────────────────────────────────────────
  const spPanel = document.createElement("div");
  spPanel.id = "scratchpadPanel";
  spPanel.className = "scratchpad-panel";
  spPanel.hidden = true;
  spPanel.innerHTML =
    `<div class="sp-toolbar">` +
      `<button class="sp-btn" id="spClear" type="button" title="Clear canvas">🗑️ Clear</button>` +
      `<button class="sp-btn" id="spUndo"  type="button" title="Undo last stroke">↩️ Undo</button>` +
      `<label class="sp-color-wrap" title="Ink color">` +
        `<input type="color" id="spColor" value="#22c55e" />` +
        `<span>Color</span>` +
      `</label>` +
      `<label class="sp-size-wrap" title="Brush size">` +
        `<input type="range" id="spSize" min="2" max="40" value="14" />` +
        `<span id="spSizeLabel">14</span>` +
      `</label>` +
    `</div>` +
    `<canvas id="spCanvas" class="sp-canvas" aria-label="Free drawing canvas"></canvas>` +
    `<div class="sp-hint">Draw freely — no guide. Huawei M-Pencil pressure supported.</div>`;
  writePanel.appendChild(spPanel);

  // ── Sub-tab switching ─────────────────────────────────────────────────────
  function showSub(which) {
    subNav.querySelectorAll(".write-subtab").forEach((b) => {
      b.classList.toggle("active", b.dataset.sub === which);
    });
    if (guidedCard) guidedCard.hidden = (which !== "guided");
    spPanel.hidden = (which !== "scratchpad");

    // recall panel injected by recall.js
    const recPanel = document.getElementById("recallPanel");
    if (recPanel) recPanel.hidden = (which !== "recall-sent");

    if (which === "scratchpad") initCanvas();
  }

  subNav.addEventListener("click", (e) => {
    const btn = e.target.closest(".write-subtab");
    if (btn) showSub(btn.dataset.sub);
  });

  // Expose so recall.js can trigger its own sub-tab
  window.MTWriteSubNav = { show: showSub };

  // ── Canvas setup ──────────────────────────────────────────────────────────
  let canvas, ctx;
  let painting = false;
  let currentPath = [];   // points of the stroke in progress
  let strokes = [];       // committed strokes (for undo)
  let canvasReady = false;

  function initCanvas() {
    if (canvasReady) return;
    canvas = document.getElementById("spCanvas");
    if (!canvas) return;
    resizeCanvas();
    ctx = canvas.getContext("2d");
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    bindEvents();
    canvasReady = true;
  }

  function resizeCanvas() {
    // Preserve existing pixel content during resize
    const tmp = document.createElement("canvas");
    if (canvas.width && canvas.height) {
      tmp.width = canvas.width; tmp.height = canvas.height;
      tmp.getContext("2d").drawImage(canvas, 0, 0);
    }
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width  = Math.floor(rect.width)  || 360;
    canvas.height = Math.floor(rect.width * 0.85) || 300; // square-ish
    if (tmp.width) canvas.getContext("2d").drawImage(tmp, 0, 0);
    redraw();
  }

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width  / rect.width;
    const scaleY = canvas.height / rect.height;
    const src = e.touches ? e.touches[0] : e;
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top)  * scaleY,
      pressure: e.pressure != null ? e.pressure : (e.touches ? 0.5 : 1.0),
    };
  }

  function colorVal()    { return document.getElementById("spColor").value || "#22c55e"; }
  function baseSizeVal() { return parseFloat(document.getElementById("spSize").value) || 14; }

  function beginStroke(e) {
    e.preventDefault();
    painting = true;
    currentPath = [];
    const p = getPos(e);
    currentPath.push(p);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  }

  function continueStroke(e) {
    if (!painting) return;
    e.preventDefault();
    const p = getPos(e);
    currentPath.push(p);
    // Draw incremental segment
    const prev = currentPath[currentPath.length - 2] || p;
    const lineW = baseSizeVal() * (0.4 + p.pressure * 0.6);
    ctx.strokeStyle = colorVal();
    ctx.lineWidth   = lineW;
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }

  function endStroke(e) {
    if (!painting) return;
    e.preventDefault();
    painting = false;
    if (currentPath.length) {
      strokes.push({ path: currentPath.slice(), color: colorVal(), base: baseSizeVal() });
    }
    currentPath = [];
  }

  function bindEvents() {
    // Pointer Events (stylus pressure + touch + mouse unified)
    canvas.addEventListener("pointerdown",  beginStroke,    { passive: false });
    canvas.addEventListener("pointermove",  continueStroke, { passive: false });
    canvas.addEventListener("pointerup",    endStroke,      { passive: false });
    canvas.addEventListener("pointercancel", endStroke,     { passive: false });
    canvas.addEventListener("pointerleave", endStroke,      { passive: false });
    canvas.setPointerCapture && canvas.addEventListener("pointerdown", (e) => {
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    });
  }

  function redraw() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of strokes) {
      if (!s.path.length) continue;
      for (let i = 1; i < s.path.length; i++) {
        const prev = s.path[i - 1], cur = s.path[i];
        ctx.strokeStyle = s.color;
        ctx.lineWidth   = s.base * (0.4 + cur.pressure * 0.6);
        ctx.lineCap     = "round";
        ctx.lineJoin    = "round";
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(cur.x,  cur.y);
        ctx.stroke();
      }
    }
  }

  // ── Toolbar actions ───────────────────────────────────────────────────────
  document.addEventListener("click", (e) => {
    if (e.target.id === "spClear") {
      strokes = []; currentPath = [];
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    if (e.target.id === "spUndo") {
      strokes.pop();
      redraw();
    }
  });

  document.getElementById("spSize") && document.getElementById("spSize").addEventListener("input", (e) => {
    const lbl = document.getElementById("spSizeLabel");
    if (lbl) lbl.textContent = e.target.value;
  });

  // Re-size canvas when window resizes (orientation change on tablet)
  window.addEventListener("resize", () => {
    if (!canvasReady || spPanel.hidden) return;
    resizeCanvas();
  });
})();
