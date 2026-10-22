# Data contracts

This file has two sections:

1. **Match package** (Ingest output): v1, approved 2026-10-22. The synthetic adapter produces it (`python -m tacticai.ingest generate`); see "Migration from the current package" for how the old package maps.
2. **Analysis package** (Interpret output): v1, approved 2026-10-22. Not produced yet; Interpret is being built against it.

# 1. Match package

## Purpose

Ingest publishes one **match package** per match. Every later stage (Interpret, Explain, Render, Personalize) reads only this package and never the source that produced it. Today the source is our synthetic engine; in production it is real broadcast video processed by computer vision (detection, tracking, pitch calibration, re-identification, OCR). A source adapter must fill **every** field: there are no optional fields. If a source cannot observe something directly, the adapter infers it.

The contract describes football, not an engine: metres on the pitch, seconds, teams called home and away, and football vocabulary.

## Package layout

```
<match_id>/
  meta.json       match-level facts: teams, pitch, clocks, source
  roster.json     players: stable id, team, name, shirt number, role
  tracking.jsonl  one line per frame: positions, velocities, ball, possession, game state
  events.jsonl    football events derived from tracking
  video.mp4       the broadcast video, frame-aligned with tracking (frame_index)
```

Synthetic-only files (`recipe.json`, `search_report.json`) may be present; consumers must ignore them.

## Conventions

- **Coordinates:** metres, origin at the centre spot. `x` runs along the pitch, `y` across it. The home team attacks towards `+x` in **both** periods (adapters normalise the half-time switch). `+y` is the right-hand touchline as seen by the home team when attacking.
- **Direction of `+y`:** looking from the home goal towards the away goal (the home team's attacking direction, `+x`), `+y` points to the **right** touchline and `-y` to the left one. A "left winger" of the home team plays at `y < 0`; for the away team, which attacks `-x`, its left side is `y > 0`.
- **Pitch size:** given per match in `meta.pitch` (real stadiums differ). Goal lines are at `x = ±length_m / 2`, touchlines at `y = ±width_m / 2`.
- **Fixed pitch markings are measured from the goal line, never from an assumed 105 × 68 pitch:** they have fixed sizes in the Laws of the Game while the pitch length and width vary. For the home team's attacking goal at `x_g = +length_m / 2`: goal posts at `y = ±3.66`, penalty spot at `x = x_g − 11`, penalty area from `x = x_g − 16.5` to `x_g` and `|y| ≤ 20.16`, goal area from `x = x_g − 5.5` and `|y| ≤ 9.16`. Mirror with `x_g = −length_m / 2` for the other goal. Consumers derive zones (box entries, shots from the area) this way.
- **Time:** two clocks, both given **per frame** (never derived from a ratio, which breaks with stopped clocks, replays and half-time).
  - `t_s`: seconds of video since the first frame, the physical time. It drives velocities and video sync. For real video it comes from each frame's presentation timestamp (PTS).
  - `clock_s` and `period`: the match clock **as the source shows it**, so overlays match the scoreboard in the video (for broadcast video, read from the on-screen clock). For the synthetic source it is the engine's clock, which runs about 18 times faster than `t_s` (a 90' match is ~300 s of physics).
- **Teams:** always `"home"` / `"away"`.
- **Players:** referenced by `player_id`, a string stable for the whole match (e.g. `"home-07"`). Its meaning lives in `roster.json`.
- **Velocities:** metres per second.

## meta.json

```json
{
  "contract_version": 1,
  "match_id": "recipe_full_match_3",
  "source": {"kind": "synthetic", "camera_setup": "synthetic", "detail": "tacticAI engine, seed 3"},
  "teams": {"home": {"name": "Brackenford Athletic", "short": "BKA"},
            "away": {"name": "Wexmoor City", "short": "WXC"}},
  "pitch": {"length_m": 108.8, "width_m": 70.2},
  "video": {"fps": 10, "frames": 759, "width": 1280, "height": 720},
  "formations": {"home": "4-3-3", "away": "5-4-1"},
  "projection": {"applies": true, "effective_play_s": 3300},
  "calibration": {"physical_absolute": false}
}
```

### Rates, projection and calibration

- **Every metric is computed as a rate over time in open play:** per minute of `t_s` where `game_state` is `open_play`. Totals are a display choice, not a calculation choice, so the same metrics work for any source.
- `projection`: how to turn rates into match totals. `total = rate per open-play second × effective_play_s`, where `effective_play_s` is the **effective playing time of a real match** (55:00 per match in the Premier League 2025/26, 54:45 to 58:11 in the previous seasons, Opta Analyst: https://theanalyst.com/articles/premier-league-ball-in-play-are-we-seeing-less-football-2025-26), not the full 90'. The synthetic source has ~297 s of open play per match (measured on seeds 1–5), so its projection factor is ~11× (3300 / 297), not the ~18× of the display clock. `applies: false` for real video (its totals are already real); `applies: true` for the synthetic source. UIs label projected totals ("projected to 90'") or show rates ("passes per minute").
- `calibration.physical_absolute`: whether physical values are realistic in absolute terms. The synthetic engine's players run far more than real players (e.g. ~4.3 m/s average for one midfielder), so it declares `false`: distance, sprints and load are shown **relative** only (rank, percentile, "covered the most ground"), and sprint thresholds are relative too (e.g. top 10 % of speeds in the match). Point speeds (a player's top speed, ball and shot speed) may be shown in absolute terms only if validated to fall in a real range across several seeds. Real video sources declare `true`. No narrative may rely on absolute distance ("ran 11 km") or fatigue when `false`.

## roster.json

```json
{"players": [
  {"player_id": "home-00", "team": "home", "name": "Venmere", "number": 1, "role": "GK"},
  {"player_id": "home-01", "team": "home", "name": "Thornquill", "number": 3, "role": "LB"}
]}
```

`role` is one of `GK, CB, LB, RB, DM, CM, LM, RM, AM, CF` (the starting role; the live role per frame is in tracking).

## tracking.jsonl (one line per frame)

```json
{"frame_index": 659, "t_s": 65.9, "clock_s": 1189.6, "period": 1, "camera": "main",
 "ball": {"x": 12.31, "y": -4.02, "z": 0.11, "vx": 6.2, "vy": -1.1, "vz": 0.0, "observed": true, "confidence": 0.93},
 "players": [
   {"player_id": "home-00", "x": -51.2, "y": 0.4, "vx": 0.1, "vy": 0.0, "role": "GK", "on_pitch": true,
    "observed": false, "confidence": 0.4}
 ],
 "possession": {"team": "home", "player_id": "home-07"},
 "game_state": "open_play",
 "score": {"home": 0, "away": 0},
 "cards": {"yellow": ["away-04"], "red": []}}
```

- `players` always lists all players of both teams; `on_pitch: false` for a sent-off player.
- `possession` is `{"team": null, "player_id": null}` when the ball is loose.
- `game_state` is one of `open_play, kick_off, goal_kick, free_kick, corner, throw_in, penalty`.
- **Target: one line per video frame**, including frames with the ball out of play (their `game_state` says so), so tracking is continuous with the video. **v1 (hackathon):** the synthetic source still writes in-play frames only, so `frame_index` has gaps during stoppages. Consumers must use `frame_index` / `t_s` and never assume consecutive lines are consecutive frames.

### Data quality fields

Every value is filled, but not every value was seen. These fields say how much to trust each one, so later stages can weigh, filter or caveat their output instead of treating estimates as observations.

- `camera` (per frame): `main` (the view that shows the play), `replay`, `closeup` or `other`. Positions are only meaningful on `main` frames; consumers skip the rest for metrics and events.
- `observed` (per player and for the ball): `true` if detected in this frame, `false` if the adapter estimated it (off-screen, occluded, interpolated through a gap).
- `confidence` (per player and for the ball, 0 to 1): the adapter's confidence in the position **and** the identity (`player_id`). An observed player with an uncertain identity has `observed: true` and a low `confidence`.

What each source can deliver:

| `source.camera_setup` | What it means for quality |
|---|---|
| `synthetic` | Exact ground truth: every frame `camera: main`, every value `observed: true`, `confidence: 1`. The degrader (see "Vision-like degradation") lowers them on purpose. |
| `fixed_full_pitch` | A fixed camera (panoramic or stitched lenses) that sees the whole pitch, installed by the club. No cuts, replays or off-screen players: `camera` is always `main` and players are almost always `observed`. Remaining hard parts: identity through occlusions and ball height (`z`). |
| `broadcast` | The TV feed: one moving camera following the ball, with cuts to replays and close-ups. Many players are off-screen at any moment (`observed: false`, estimated), the ball is lost in stretches, `z` is rough, and identity is the hardest part. |

## events.jsonl (one line per event, ordered by `t_s`)

Common fields: `type`, `frame_index`, `t_s`, `clock_s`, `period`, `team`, `player_id`, `x`, `y` (where it happened).

| type | extra fields |
|---|---|
| `pass` | `to_player_id`, `end_x`, `end_y`, `outcome` (`complete` / `intercepted`), `intercepted_by` (player_id or null) |
| `tackle` | `from_player_id` (who lost the ball) |
| `shot` | `end_x`, `end_y` (projected at the goal line), `speed_m_s`, `outcome` (`goal` / `no_goal`) |
| `goal` | `scorer_id` (player_id or null if unknown) |
| `set_piece` | `kind` (same values as `game_state` minus `open_play`) |

**Events are derived from positions only** (ball and player positions, velocities, `game_state`, `score`), never from source-specific signals, so the same detectors run on synthetic and on vision tracking. They do not read `possession`: the ball owner is inferred as the nearest on-pitch player to the ball within 1.25 m while the ball is at most 1.0 m high, and an owner counts only after holding for 3 consecutive tracking lines (defaults `owner_radius_m`, `owner_max_z_m` and `owner_min_frames`, the latter for possession changes only; shots and goals use the last touch, calibrated on synthetic seeds 1 to 5, where the stabilized owner equals the engine `possession` in 89.3% of frames on seeds 1 to 3).

## Migration from the current package

| Current field (engine observation) | Contract |
|---|---|
| `left_team_eng`, `right_team_eng` (+ raw and `_m` copies) | `players[].x/y` in metres (engine `_eng` scale); raw and `_m` copies dropped |
| `*_team_direction` (units per step) | `players[].vx/vy` in m/s (`dx*54.4*10`, `dy*83.6*10`) |
| `ball`, `ball_direction` | `ball.x/y/z`, `ball.vx/vy/vz` |
| `ball_owned_team/player` (-1 = none) | `possession.team/player_id` (null = loose) |
| `*_team_roles` (ints 0..9) | `players[].role` (names) |
| `*_team_active`, `*_yellow_card` | `on_pitch`, `cards` |
| `game_mode` (ints) | `game_state` (names) |
| `score` [left, right] | `score.home/away` |
| `step`, `engine_time_s`, `match_time_s`, `half`, `steps_left` | `t_s` (= `engine_time_s`), `clock_s` (= `match_time_s`), `period` (= `half`), all per frame; `step` and `steps_left` dropped |
| `*_tired_factor` | dropped (not observable from video). Fatigue is described with observable **derived metrics** computed by Interpret from tracking: distance covered, sprints, and drop in top speed over the match |
| events `team` int / `team_side`, `player` index, `origin_eng`/`dest_eng` | `team` home/away, `player_id`, `x/y`, `end_x/end_y` |
| meta engine fields (`seed`, `physics_steps_per_frame`, coordinate notes) | `source.detail`; engine notes move to docs/ingest/engine-reference.md |
| (none) | `camera: "main"`, `observed: true`, `confidence: 1.0` everywhere; `source.camera_setup: "synthetic"` |
| (none) | `projection: {"applies": true, "effective_play_s": 3300}`, `calibration: {"physical_absolute": false}` |

Pitch size for the synthetic source: `length_m = 2 × 54.4 = 108.8`, `width_m = 2 × 0.42 × 83.6 ≈ 70.2`, the engine's observation scale (see engine-reference.md, "coordinates").

## Vision-like degradation

Because the synthetic source has exact ground truth, Ingest can also publish a **degraded** copy of a match that mimics a real camera setup: position noise, off-screen and occluded players (`observed: false`), lost ball stretches, identity swaps (lower `confidence`), and replay/close-up frames for `broadcast`. Running the same detectors and metrics on the clean and the degraded copy measures how much each insight degrades per camera setup, which cannot be measured on real video. Optional (built only if time allows); the degrader produces packages in this same contract.

# 2. Analysis package (Interpret output)

## Purpose of the analysis package

Interpret reads one match package (section 1) and publishes one **analysis package** next to it. Explain, Render and Personalize read only this package plus the match package, never Interpret's code. Every number is computed by deterministic code (Stats Tools); agents query it, they never compute it with an LLM. Like the match package, every field is always present: a value that does not apply is `null`, never a missing key.

## Analysis package layout

```
<match_id>/interpret/
  meta.json               versions, models, thresholds and the rules used for this package
  events_enriched.jsonl   every event of events.jsonl with Interpret's fields added
  sequences.jsonl         possession sequences, one line each
  timeline.jsonl          fixed windows over open play: possession, pressure, xG, momentum
  players.json            per-player table: physical, passing, shooting, defending, rating
  teams.json              per-team table: totals, rates, projected totals
  quality.json            tracking quality summary and the confidence level for later stages
  tactical_notes.jsonl    Tactical Analyst Agent output (phases, patterns), each with its evidence
```

## Analysis conventions

- **Time:** every record carries `t_s` (and `frame_index` where it is a point in time) so any Stats Tool can answer "up to minute 60" with `until_t_s`. Labels shown to people use `clock_s` and `period`. Cumulative values are computed by the tools on demand, not stored.
- **Rates first:** rate fields end in `_per_min` (per minute of open play, see contracts.md). Projected totals end in `_projected` and are `null` when `meta.projection.applies` is false (real video totals are already real).
- **Physical values:** when `meta.calibration.physical_absolute` is false, physical fields keep their measured value but every table also carries `rank` and `percentile`, and downstream text must use only the relative fields.
- **Attacking direction:** everything that measures advance (sequences, `progressive_m`, lines broken, thirds) uses `x_att`, the x oriented towards the opponent goal: `x_att = x` for home and `x_att = -x` for away. Fields in this frame end in `_att`.
- **Thresholds in physical units:** every threshold is in metres or seconds, never in frames, so it holds at any frame rate (10 fps synthetic, 25 fps video).
- **Engine-relative models:** xG and xPass are trained on synthetic data; `meta.json` names the model and its training dataset, and the UI labels them as such until a model trained on real data replaces them.

## interpret/meta.json

```json
{
  "analysis_version": 1,
  "match_id": "recipe_full_match_3",
  "open_play_s": 297.4,
  "projection": {"applies": true, "effective_play_s": 3300},
  "calibration": {"physical_absolute": false},
  "models": {
    "xg": {"id": "xg_v1", "trained_on": "shots_v2", "kind": "logistic", "features": ["dist_goal_center_m", "visible_goal_angle_deg", "defenders_in_cone", "gk_dist_to_shot_line_m", "header"]},
    "xpass": {"id": "xpass_v1", "trained_on": "passes_v1", "kind": "logistic", "features": ["length_m", "passer_pressure", "opponents_near_line"]}
  },
  "thresholds": {"sprint_speed_m_s": 6.9, "sprint_min_s": 1.0, "pressure_radius_m": 5.0, "window_open_play_s": 16.5}
}
```

## interpret/events_enriched.jsonl

Same lines and order as `events.jsonl` (which already carry `t_s`, `clock_s` and `period`), plus:

| Added to | Fields |
|---|---|
| every event | `sequence_id`, `pressure` (0–1 on the player making the action, see Definitions), `score_before` (`{"home": n, "away": n}`, the score just before the event, so Explain can weigh its context: minute and score) |
| `pass` | `length_m`, `progressive_m` (gain in `x_att`), `lines_broken` (0–3), `xpass` (probability of completion), `difficulty` (= 1 − `xpass`) |
| `shot` | `xg`, `dist_goal_center_m`, `visible_goal_angle_deg`, `defenders_in_cone`, `ball_speed_m_s`, `on_target` |
| `tackle` | `zone` (`def_third`, `mid_third`, `att_third` of the tackling team) |

## interpret/sequences.jsonl

One possession sequence per line: from the moment a team gains the ball until it loses it.

```json
{"sequence_id": 41, "team": "home", "start_t_s": 120.3, "end_t_s": 131.9, "start_frame": 1203, "end_frame": 1319,
 "start_clock_s": 2161.0, "period": 1, "start_cause": "recovery", "end_cause": "shot",
 "passes": 5, "duration_s": 11.6, "start_x_att": -20.1, "max_x_att": 44.7, "lines_broken": 2, "xg": 0.18, "goal": false,
 "players": ["home-04", "home-07", "home-09"]}
```

- `start_cause`: `kick_off`, `recovery` (tackle or interception), `set_piece:<kind>`, `loose_ball`.
- `end_cause`: `goal`, `shot`, `lost` (opponent gains it), `out` (set piece for the opponent), `end_of_period`.

## interpret/timeline.jsonl

Fixed windows over **open-play time**. There are 18 windows per match, so one window ≈ 5' of a 90' match for any source (synthetic: ~16.5 s of `t_s`).

```json
{"window": 7, "start_t_s": 115.5, "end_t_s": 132.0, "start_clock_s": 2088.0, "end_clock_s": 2385.0, "period": 1,
 "home": {"possession_share": 0.58, "pressure": 0.41, "xg": 0.18, "final_third_entries": 3},
 "away": {"possession_share": 0.42, "pressure": 0.55, "xg": 0.02, "final_third_entries": 1},
 "momentum": 0.34}
```

`momentum` is −1 (away dominates) to +1 (home dominates). Synthetic windows are short (~16.5 s, about 4 passes and rarely a shot), so momentum is noisy even after smoothing: check it on one match against the video before showing the chart, and use fewer windows if it does not read well.

## interpret/players.json

```json
{"players": [{
  "player_id": "home-07", "team": "home", "minutes_open_play": 4.9,
  "physical": {"distance_m": 1452, "distance_per_min": 296, "distance_rank": 1, "distance_percentile": 100,
               "top_speed_m_s": 8.1, "top_speed_rank": 3, "top_speed_percentile": 90, "sprints": 7, "sprints_per_min": 1.4,
               "top_speed_drop_pct": 4.0},
  "passing": {"passes": 41, "completed": 31, "completion_pct": 75.6, "mean_length_m": 14.2, "progressive_passes": 6,
              "lines_broken": 9, "mean_difficulty": 0.31, "passes_per_min": 8.4},
  "shooting": {"shots": 2, "xg": 0.27, "goals": 1, "max_shot_speed_m_s": 31.0},
  "defending": {"tackles": 3, "interceptions": 2, "pressures": 18},
  "rating": {"value": 7.8, "breakdown": [{"item": "lines_broken", "count": 9, "points": 0.9},
                                         {"item": "goal_minus_xg", "value": 0.73, "points": 0.7}]}
}]}
```

## interpret/teams.json

Per team: the same blocks summed or averaged over outfield players, each count with its `_per_min` and `_projected`, plus `possession_pct`, `pressure` (match mean), `xg`, `goals`, `sequences`, `sequences_ending_in_shot`.

## interpret/quality.json

```json
{"camera_setup": "synthetic", "tracking_lines": 3000, "video_frames": 3380, "main_camera_share": 1.0, "ball_observed_share": 1.0,
 "players_observed_share": 1.0, "mean_confidence": 1.0, "gaps": 41, "identity_swaps_suspected": 0,
 "level": "high", "notes": []}
```

`tracking_lines` counts lines of tracking.jsonl (in-play frames only in v1); `video_frames` counts frames of the video. They are equal once tracking has one line per video frame.

`level` (`high`, `medium`, `low`) is what Explain uses to caveat its text ("medium confidence").

## interpret/tactical_notes.jsonl

Output of the Tactical Analyst Agent. Each note cites the windows, sequences or events that support it; a note without evidence is not published.

```json
{"t_s": 180.0, "until_t_s": 230.0, "team": "home", "kind": "phase_change", "text_key": "high_press_from",
 "evidence": {"timeline_windows": [11, 12, 13], "metric": "pressure", "before": 0.38, "after": 0.61}}
```

## Analysis definitions

Each is a deterministic Stats Tool.

1. **Pressure (0–1)** on the player with the ball: `sum over opponents within 5 m of (1 − d / 5)`, capped at 1. Team pressure in a window = mean pressure it applies on the opponent's ball carrier while the opponent has the ball.
2. **Lines broken:** grouped by position, not by role (roles are not observed in video, and a full-back pushing up or a centre-back stepping out breaks role-based lines). At the pass frame, the opponent's on-pitch outfield players are clustered by their `x_att` with a one-dimensional k-means (k = 3); lines whose centres are closer than 4 m are merged, so there are up to 3 lines. A completed pass breaks a line when it starts behind the line's centre and ends beyond it; `lines_broken` counts how many (0–3).
3. **Sequences:** a sequence changes when the stabilized owner (ingest rules) changes team, or at a set piece, goal or period end.
4. **Momentum per window:** `tanh` of a weighted difference home − away of xG, final-third entries and possession share, smoothed over 3 windows. Weights documented in `meta.json`.
5. **Rating (1–10):** 6.0 plus documented points per action (lines broken, progressive passes, xG and goals minus xG, tackles and interceptions, losses in own half negative), always published with its breakdown. **Goalkeepers get `rating.value: null`** with `"reason": "saves_not_validated"` until save detection is checked against video: the dataset shows very few saves (156 in 8,238 kicks), which would score keepers low for a detection or engine problem, not for their play.
6. **xG / xPass:** logistic models trained on synthetic data, split by match (not by shot) for testing, reported with Brier score and a calibration curve. Known risks: (a) labels inherit the shot detector's noise (a hard pass can look like a shot), mitigated by training only on kicks inside the reviewed shot definition, checked on video; (b) the engine converts more chances than real football (43 % of on-target shots vs ~30 % [UNVERIFIED]), so its xG reads higher than a real-football xG for the same chance. The UI shows it as "engine xG", and the AI-level calibration (`docs/ingest/engine-calibration.md`, phase 1) runs before training.
