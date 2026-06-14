# Build Spec v3 — Round 2 (Bell feedback 2026-06-15)

Owner: Kyo (orchestrator). HARD RULES from BUILD_SPEC_v2.md still apply
(chunked edits <=300 lines, systemd restart, venv python, English UI).

## 5 ASKS

### ASK 1+5 (SAME): Write = free scratchpad scored by recognition % (codex lane)
Replace the Hanzi Writer trace/outline approach with a FREE handwriting canvas
like https://www.purpleculture.net/chinese_handwriting_input/ :
- User draws the character FREELY on a blank canvas — NO outline, NO guide, NO trace.
- Engine: HanziLookup (vendored, offline, no-Google) at app/vendor/hanzilookup/
  (hanzilookup.min.js + mmah.json + orig.json — already downloaded & verified).
- Capture strokes via Pointer Events (pressure ok) as array of strokes; each stroke
  = array of [x,y] points. Build HanziLookup.AnalyzedCharacter(strokes).
- On "Check" button: run Matcher("mmah").match(analyzedChar, 8, cb). The callback
  returns candidates best-first, each with `.character`. Find the RANK of the target
  hanzi in the candidate list -> map to a similarity %:
    rank 0 (top match) => ~95-100, rank 1 => ~85, rank 2 => ~75, ... not found => low.
    Blend with match score if available. This is "how close your writing is to the real char".
- Show the % + the candidate list (so user sees what it recognized), like purpleculture.
- Keep Undo + Clear buttons. Keep a "Watch stroke order" helper available SEPARATELY
  (optional small button) but the DEFAULT write surface is the blank scratchpad.
- POST result to /write-assess (existing): {hanzi, mode:"scratch", score:<percent>,
  mistakes:0, lesson_id}. Refresh Learn + Progress after.
- jQuery: HanziLookup's built-in DrawingBoard needs jQuery, but we capture strokes
  OURSELVES via Pointer Events and only call AnalyzedCharacter + Matcher (NO jQuery needed).
  Verify the lib's AnalyzedCharacter/Matcher work without jQuery; if the min.js hard-requires
  jQuery globally, vendor a minimal jQuery shim or load jQuery from the same vendor dir.
- FILES (this lane owns): app/write.js (rewrite), Write <section id="write"> in
  app/index.html, .write CSS in app/style.css, app/sw.js (add vendor files to SHELL +
  bump CACHE version). Load order in index.html: hanzilookup.min.js BEFORE write.js.

### ASK 3: Drill Back button (frontend lane)
In the Drill panel add a "← Back to Learn" button that calls window.MTTabs.show("learn").
Only meaningful when drill was opened from a lesson. Small surgical edit to drill.js + index.html + css.

### ASK 4: Game-style level lock (backend + frontend lane)
Within a lesson, items are SEQUENTIAL STEPS like a game (level 1,2,3...). The NEXT item
stays LOCKED until the current item's score is GREEN (>= pass threshold, tone PASS_SCORE=70
or write WRITE_PASS_SCORE=65). Example: in u1l1, 好(thankyou-equivalent) locked until 你(hello)
is green. Show a level path UI (steps with lock/checkmark/score).
MINI-BOSS / FINAL BOSS: at the end of ALL basic units, the capstone is FULL self-introduction
(你好，我叫…，我来自印度尼西亚) spoken/written with NO guide/help. Passing the boss unlocks
Intermediate. (Backend capstone gating already exists at lesson level — extend so the boss is
explicit + requires the no-guide capstone, and per-item unlock data is exposed.)
- Backend (curriculum.py + app.py): expose per-item ordered scores + locked flag via the
  lesson/lesson-scores endpoints (frontend computes lock: item[i] locked unless item[i-1] green).
  Mark capstone lessons with is_boss=True + requires_no_guide=True. Keep signatures intact.
- Frontend (learn.js): render the level-path with locks; gate opening drill/write for a
  locked item; show the boss specially; reflect unlock of next level when boss passed.

### ASK 2: Chat upgrade (frontend lane)
Improve the Chat tab (app.js + chat section). Make it genuinely better, Pingo-style:
- Nicer message bubbles (user vs tutor), tutor messages show hanzi + pinyin + English toggle.
- Typing indicator while the tutor responds.
- Tap any tutor hanzi message to hear it (TTS via /tts) and to send it to Drill/Write.
- Suggested quick-reply chips to keep the conversation going (a few canned openers per level).
- Auto-scroll, timestamps optional, clean mobile layout. Keep existing /chat backend contract
  (POST {history, user_text}); only enrich the CLIENT. If pinyin needs server help, reuse
  existing endpoints; do NOT break /chat.

## LANES / GRAPH
T3_back (backend)  : curriculum.py per-item ordered scores + locked/boss flags + app.py exposure. ISOLATED, parallel.
T3_write (CODEX/ECC): ASK 1+5 Write scratchpad rewrite. Runs parallel (I manage via CLI), commit before frontend lane.
T3_fe (frontend)   : ASK 2 + 3 + 4-frontend. PARENT: T3_back (needs unlock data) — and I commit T3_write FIRST so index.html edits don't collide.
T3_qa (qa)         : PARENT T3_fe. Verify all, no Indonesian, scratchpad recognizes a clean 你, level-lock gates, chat renders, drill back works.

## ORCHESTRATOR
- Verify codex write rewrite myself: load page, draw-simulate or at least confirm HanziLookup
  init + Matcher returns candidates for a known stroke set; confirm % mapping.
- Re-verify QA verdict (PASS and FAIL) vs runtime truth.
- Browser visual check each changed tab. Rebuild APK. Report to Bell.
