# Engine calibration: bringing the synthetic engine closer to real football

Status: **plan, 2026-10-22.** Phase 1 (recipe-only) is in progress; phase 2 (engine code) is for after the hackathon.

## Why

The synthetic engine is the data source of the demo. Every later stage reads only the data contract, so the pipeline does not need a realistic engine to work. But the closer the engine is to real football, the more the numbers we show mean something: xG and xPass are trained on synthetic data, physical values can stop being "relative only", and styles and formations become visible in the data.

The engine computes no statistics or events: everything is derived by our code from its positions (see `docs/contracts.md`). Calibrating the engine means changing **how it plays**, not how we measure.

## Gaps measured today

| Aspect | Engine | Real reference | Source of the engine value |
|---|---|---|---|
| Player top speed | capped at 8.0 m/s in every match | PL 2025/26 fastest: 36–37 km/h (10.0–10.4 m/s); typical peak in other top leagues 29–33 km/h [1][2] | `interpret/domain/physical.py` on `data/_exp/contract/match_1..5` |
| Running intensity | ~250 m per open-play minute per outfield player | ~120 m/min (≈ 10–11 km per 90') [1] [UNVERIFIED: no league-wide average published] | same |
| Pass completion | 67.6 % (seed 1); 57–84 % per team on seeds 1–5 | PL 81.5–83.7 % | `docs/pipeline.md` realism check; `interpret/domain/passes.py` |
| Passes per minute | 14.2 | PL 16–18 | `docs/pipeline.md` realism check |
| Goalkeepers | 43 % of shots on target are goals (177/411) | ~30 % [UNVERIFIED] | `data/datasets/shots_v1` |
| Styles | high press raises the defensive line by ~3 m vs balanced, inside the ±6 m seed noise | clearly different team shapes | `docs/ingest/presets.md` |
| Formations | a 5-4-1 defends higher than a 4-4-2 (35.0 vs 32.9 m) | a back five defends deeper | `docs/ingest/presets.md` |
| Ball in play | ~297 s of open play per match (the clock runs ~18× faster) | 55:00 per match, PL 2025/26 [3] | measured; handled by rates and `meta.projection` |

The clock compression does not need calibration: every metric is a rate per open-play minute, and totals are projected with `meta.projection.effective_play_s`.

## Method

1. **Targets:** each gap gets a numeric target with a source (the table above). No target, no change.
2. **Measure:** headless runs (no video) of full matches and situations, metrics computed with Interpret's code (`physical.py`, `passes.py`, `shots.py`) and `python -m tacticai.ingest measure`. 10–20 seeds per setting; report mean ± std.
3. **Change one lever at a time**, measure again, keep it only if it moves the metric towards the target without breaking another one.
4. **Accept** when the metric is inside the real range or the remaining gap is documented.

## Levers

### Phase 1: recipe only (no engine change)

- **AI level** (`level` in the recipe, `left_team_difficulty` / `right_team_difficulty` in `engine/src/main.hpp:196`). Sweep 0.4 / 0.6 / 0.8 / 1.0 for both teams, 4-4-2 balanced: 10 full matches per value for passing and physical metrics, ~100 attacking situations per value for on-target conversion and saves. Pick the value closest to the targets and use it as the recipe default **before training xG**, so the model learns on the calibrated engine.
- Cost: ~10 minutes headless, nothing else changes.
- **Result (2026-10-22, `data/_exp/level_sweep.json`, 10 full matches + 100 situations per level, 13 min):** level is not a calibration lever. Pass completion is 68.8 / 73.3 / 73.1 / 71.6 % at 0.4 / 0.6 / 0.8 / 1.0 (± 4–6.5, all below 81.5–83.7 %); passes per minute 13.6–14.5 at every level; running intensity 260–266 m/min, top speed 8.0 m/s and sprints 115–119 per team do not move; on-target conversion 44 / 50 / 56 / 31 % rests on 26–44 shots per level, inside the sampling noise. Decision (approved 2026-10-22): keep the dataset recipes at level 0.7–1.0 (variety) and treat realism as phase 2 work.

### Phase 2: engine code (after the hackathon)

| Gap | Lever | Where |
|---|---|---|
| Top speed | `sprintVelocity = 8.0f` (and `walkSprintSwitch = 6.0f`) | `engine/src/gamedefines.hpp:32,38` |
| Running intensity | how much players move off the ball: positioning force field and idle/sprint choice | `engine/src/onthepitch/AIsupport/AIfunctions.cpp` (~line 329) |
| Pass completion | pass error and decision quality | [UNVERIFIED: location not identified yet] |
| Goalkeepers | goalkeeper positioning and reaction | `engine/src/onthepitch/player/controller/strategies/offtheball/goalie_default.cpp` |
| Styles | wider tactical multipliers | `engine/src/onthepitch/teamAIcontroller.cpp:72-81` |
| Formations | weight of the injected shape (today 60/40 with the role default) | `engine/src/data/teamdata.cpp` |

Every engine file touched gets the "Modified by the tacticAI project" line; Apache notices stay intact.

## Cost of each engine change

- Rebuild the `tai-engine` image.
- The tracking regression hash changes (`docs/ingest/engine-reference.md`): record the new one.
- Regenerate datasets trained on the engine (shot dataset: ~47 min for 40 matches + 2400 situations) and retrain xG / xPass.
- Re-check the event detectors against the previous calibration (owner agreement, pass and tackle precision/recall), since speeds and movement change.
- Re-measure presets (`docs/ingest/presets.md`).

## What calibration unlocks

- `meta.calibration.physical_absolute` can become `true` for the synthetic source only when player top speed, running intensity and sprint counts fall inside the real ranges across several seeds. Until then physical values are shown relative only.
- Shot and ball speeds can be shown in km/h once a real typical range is sourced (today only the record is: 183 km/h [4]).
- xG and xPass become closer to real football, but stay labelled "engine" models until trained on real tracking.

## Beyond calibration

Calibration tunes a rule-based AI. Learning behaviour from real tracking (imitation learning) is a separate production line, described in `docs/pipeline.md` ("Camino a producción").

## Sources

1. Premier League, "Who ran fastest and furthest in 2025/26": https://www.premierleague.com/en/news/4673057/who-ran-fastest-and-furthest-in-202526-premier-league
2. Morgans et al. 2025, Biology of Sport 42(3), sprint > 7 m/s, high-speed running 5.5–7 m/s (EPL, Second Spectrum): https://pmc.ncbi.nlm.nih.gov/articles/PMC12244393/
3. Opta Analyst, Premier League ball in play 2025/26: https://theanalyst.com/articles/premier-league-ball-in-play-are-we-seeing-less-football-2025-26
4. Guinness World Records, fastest shot in the English top division: https://www.guinnessworldrecords.com/world-records/fastest-shot-on-goal-in-english-top-division-football-(soccer)
