# API Contract v2 — frontend MUST match these exactly (verified live, all 200)

Base: same-origin (config.js API_BASE=""). All JSON.

## Gamification / Progress
GET  /gamification/state -> {xp, level, xp_to_next, level_progress_pct, hearts, streak, badges:[{id,label,desc}]}
GET  /stats              -> {tone:{attempts,avg_score}, writing:{attempts,avg_score},
                             per_level:{basic:{total,done,pct}, intermediate:{...}, hard:{...}},
                             ... (weak_items / daily activity if present — read actual keys)}
GET  /progress           -> existing summary (streak, totals, completed lessons, badges)

## SRS
GET  /srs/due            -> {due:[...], count}
POST /srs/review         body {item_key: str, rating: int(1=Again,2=Hard,3=Good,4=Easy)}
                         -> {item_key, ease, interval, due, reps, lapses, xp:{xp,level,xp_gained,leveled_up,new_badges}}

## Daily Challenge
GET  /challenge/today    -> {date, items:[pinyin...], done:[], total, completed, finished}
POST /challenge/complete body {item_key: str}   # NOTE field is item_key, NOT item
                         -> updated challenge state + xp

## Recall (sentence, no hanzi guide)
POST /recall-assess      body {lesson_id: str, prompt_id: str("0","1".. or prompt_en),
                               mode: str("writing"|"voice"), payload: str(hanzi attempt; client does STT for voice)}
                         -> score + pass

## Writing (existing)
POST /write-assess       body {hanzi, mode("trace"|"recall"), score, mistakes, lesson_id}
GET  /writing-scores/{lesson_id}

## Curriculum
GET  /curriculum         -> curriculum_status() : 7 units, level(basic/intermediate/hard), unlock gating, capstone flags
GET  /lesson/{id}        -> lesson items + recall_prompts list [{prompt_en, prompt_id, answer_hanzi, answer_pinyin}]
GET  /lesson-scores/{id} -> per-item best scores

## CRITICAL FIELD-NAME PITFALLS (caused 422s in testing)
- /challenge/complete uses `item_key` (NOT `item`)
- /recall-assess `prompt_id` and `payload` are STRINGS (not int/object)
- /srs/review `rating` is INT 1-4
