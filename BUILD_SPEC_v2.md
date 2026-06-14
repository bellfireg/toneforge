# Mandarin Tutor — Full Build Spec v2 (orchestrated)

Owner: Kyo (orchestrator). Workers: backend, frontend, qa profiles + codex (ECC).
Goal: complete the app from zero-to-fluent — rich content, accurate voice+writing
scoring, full writing module, gamification + SRS, rich progress tracker. Update APK.
Name change deferred (not urgent).

## HARD RULES FOR ALL WORKERS
- Chunked writes: MAX 300 lines per write/edit op. Surgical edits on existing files.
- Backend runs via `mandarin-tutor.service` (user systemd). NEVER nohup/session-bound.
  After backend changes: `systemctl --user restart mandarin-tutor.service` then curl /health.
- Python NOT on PATH. Use `backend/venv/bin/python` and `backend/venv/bin/uvicorn`.
- All UI strings ENGLISH. No Indonesian leftovers.
- Verify your own work before kanban_complete (syntax check + run it). Report evidence.

## FILE OWNERSHIP (prevents edit conflicts)
- `backend/tone.py`        -> SCORING lane (codex/ECC). Nobody else edits.
- `backend/curriculum.py`  -> CONTENT lane, then BACKEND-LOGIC lane (serialized, gated).
- `backend/srs.py` (NEW)   -> BACKEND-LOGIC lane.
- `backend/gamification.py` (NEW) -> BACKEND-LOGIC lane.
- `backend/app.py`         -> BACKEND-LOGIC lane only.
- `app/*` (js/html/css/sw) -> FRONTEND lane only.

## LANES / TASK GRAPH
T_score  (codex)   tone.py scoring v2. Independent. Runs in parallel.
T_content(backend) curriculum.py content enrichment. No parent.
T_logic  (backend) srs.py + gamification.py + app.py endpoints + curriculum.py wiring.
                   PARENT: T_content (serialize curriculum.py + needs content).
T_front  (frontend) all UI. PARENT: T_logic (needs endpoints).
T_qa     (qa)      full verification. PARENT: T_front.

## CONTENT REQUIREMENTS (T_content)
Source: Taiwan "Let's Learn Mandarin Book 1" (TOCFL Novice), HSK 1-2 standard wordlists,
Notion templates (Beginner / HSK-1 Flashcards / Intermediate / Advanced 4-skill model).
- Keep existing u1-u5 but EXPAND each lesson to 6-12 items.
- Add HSK-1 vocab coverage (~150 words) spread across basic+intermediate units.
- Add HSK-2 starter set (~80 words) in hard units.
- Each item: hanzi, pinyin (tone marks), tone number(s), english gloss, audio_text.
- Sentence items for capstones already exist (self-intro). Add MORE full sentences:
  greetings, numbers-in-context, family, food, directions, shopping.
- NEW: sentence-recall questions ("write 'I can' with no hanzi guide"): each lesson gets
  a `recall_prompts` list = [{prompt_en, prompt_id, answer_hanzi, answer_pinyin}].
  These power the no-guide writing/speaking challenge.
- Add a 6th unit u6 "Daily Life" (intermediate) and u7 "Stories & Opinions" (hard) so the
  ladder reaches real conversational range. Maintain level + unlock + capstone fields.
- curriculum_outline()/curriculum_status() must still expose level, unlock, capstone,
  and now recall_prompts presence. Do NOT break existing function signatures used by app.py.

## BACKEND-LOGIC REQUIREMENTS (T_logic)
1. SRS (srs.py): SM-2 (reference open-spaced-repetition/anki-sm-2, but implement minimal
   pure-python, no AGPL dep). Table `srs_cards(user_id, item_key, ease, interval, due,
   reps, lapses, last_review)`. Functions: review(item_key, rating 1-4)->next due;
   due_items(user_id, limit). item_key = hanzi or lesson item id.
2. Gamification (gamification.py): XP (award per pass), hearts/lives (optional soft),
   daily streak (already partial — consolidate), levels from XP, daily challenge
   generator (pick N due/weak items), achievements/badges (extend existing BADGES).
   Tables: xp_log, daily_challenge, user_state(xp,level,hearts,last_active).
3. app.py endpoints (additive, don't break existing):
   GET  /srs/due            -> due review items
   POST /srs/review         -> {item_key, rating} update schedule
   GET  /challenge/today    -> today's daily challenge (generate if missing)
   POST /challenge/complete -> mark challenge item done, award XP
   GET  /gamification/state -> {xp, level, hearts, streak, badges}
   POST /recall-assess      -> sentence recall grading (voice or writing) {lesson_id,
                               prompt_id, mode, payload} -> score+pass
   GET  /stats              -> rich progress: per-level %, per-unit, tone vs writing
                               split, weak items (low score) list, daily activity series
4. Wire new tables into curriculum.py init_db() (or srs/gamification own init, called on boot).
5. Restart service + verify every new endpoint returns 200 with sane JSON.

## FRONTEND REQUIREMENTS (T_front)
- WRITE module: keep Hanzi Writer trace/recall/watch. ADD a true free-canvas SCRATCHPAD
  (Pointer Events API, pressure support for Huawei M-Pencil, clear/undo, no guide).
- Sentence-recall UI: show english/indonesian prompt, NO hanzi hint; user writes (canvas)
  or speaks (mic); submit to /recall-assess; show score.
- PROGRESS dashboard (rich): XP + level bar, streak calendar, per-level completion %,
  tone-vs-writing split, weak-items "review these" list with scores, daily activity chart
  (lightweight inline SVG/canvas, no heavy libs).
- CHALLENGES tab: today's daily challenge, complete flow, XP reward animation (CSS only).
- SRS REVIEW tab: due cards, rate Again/Hard/Good/Easy -> /srs/review.
- Achievements/badges display.
- Bump ALL cache-busters + sw.js CACHE version. Keep offline-first.
- Touch-friendly, tablet-first layout. No external heavy deps beyond Hanzi Writer CDN.

## QA REQUIREMENTS (T_qa)
- Boot backend via venv, import app — all routes present, no exceptions.
- curl every endpoint (old + new) -> 200 + valid JSON. Paste outputs.
- Grep for Indonesian leftover strings in app/ (broad: halo, ibu, kuda, saya, kamu,
  nada, benar, salah, sempurna). Report any hit.
- Scoring sanity: synthetic tone contours still score correctly; recall-assess returns
  score+pass; SRS review advances due date; XP increments.
- Verify curriculum item counts increased; recall_prompts present.
- Report PASS/FAIL with EVIDENCE (actual command output). Do NOT modify code.

## ORCHESTRATOR POST-QA
- Re-verify QA verdict against runtime ground truth (both PASS and FAIL).
- Browser visual check of new UI.
- Rebuild APK (thin wrapper -> only needed if web shell/cache requires; confirm server.url).
- Final report to Bell.
