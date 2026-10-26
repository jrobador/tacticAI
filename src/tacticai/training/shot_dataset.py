"""Build the synthetic kick-candidate dataset: many headless engine jobs -> kicks.jsonl, jobs.jsonl, README.md, summary.json."""
import json
import os
import random
import tempfile
import time
from collections import Counter
from multiprocessing import Pool

from ..ingest.application.generate_match import generate_from_recipe
from ..ingest.domain.events import DEFAULTS
from ..ingest.domain.formations import CATALOG
from ..ingest.domain.recipe import from_dict, to_dict
from ..ingest.domain.situations import TEMPLATES
from ..ingest.domain.styles import STYLES
from ..core.files import read_json, read_jsonl, write_json
from ..interpret.domain.passes import pass_features
from ..interpret.domain.pressure import owners_for
from ..interpret.domain.shots import kick_candidates

FULL_SEED, SITUATION_SEED = 1000, 50000

FIELDS = [  # (name, unit, definition)
    ("match_id", "-", "Match package id (recipe_<mode>_<seed>)."),
    ("frame_index", "-", "Tracking frame of the kick (first frame with ball speed >= 10 m/s)."),
    ("t_s", "s", "Seconds of video since the first frame."),
    ("clock_s", "s", "Match clock as the source shows it (engine clock, ~18x faster than t_s)."),
    ("period", "-", "Match period (1 or 2)."), ("team", "-", "Team that struck the ball: home or away."),
    ("shooter_id", "-", "player_id of the last raw ball owner before the kick (nearest on-pitch player within 1.25 m, ball z <= 1 m)."),
    ("shooter_role", "-", "Starting role of the shooter from the roster."), ("shooter_number", "-", "Shirt number of the shooter."),
    ("ball_x", "m", "Ball x at the kick frame (home attacks +x)."), ("ball_y", "m", "Ball y at the kick frame."),
    ("ball_z", "m", "Ball height at the kick frame."), ("ball_vx", "m/s", "Ball velocity x."), ("ball_vy", "m/s", "Ball velocity y."),
    ("ball_vz", "m/s", "Ball velocity z."), ("speed_m_s", "m/s", "Horizontal ball speed, hypot(vx, vy)."),
    ("dist_goal_center_m", "m", "2D distance from the ball to the centre of the opponent goal line."),
    ("dist_goal_line_m", "m", "Distance from the ball to the opponent goal line along x."),
    ("angle_to_goal_center_deg", "deg", "Absolute angle between the ball to goal-centre direction and the goal-line normal (0 = straight on)."),
    ("visible_goal_angle_deg", "deg", "Angle subtended by the two posts (y = +-3.66) seen from the ball."),
    ("projected_y_at_goal_m", "m", "y where the straight-line projection of (vx, vy) reaches the goal line."),
    ("projected_z_at_goal_m", "m", "Ballistic height at the goal line: z + vz*t - 4.905*t^2 with t = (gx - x)/vx, no drag."),
    ("on_target_projection", "bool", "|projected_y| <= 3.66 and 0 <= projected_z <= 2.44."),
    ("in_box", "bool", "dist_goal_line <= 16.5 m and |y| <= 20.16 m."), ("header", "bool", "Ball z > 1.0 m at the kick."),
    ("nearest_defender_m", "m", "Distance from the ball to the nearest opponent (any role, on pitch)."),
    ("defenders_within_3m", "count", "Opponents within 3 m of the ball."),
    ("defenders_in_cone", "count", "Opponent outfield players strictly inside the triangle ball-post-post."),
    ("gk_present", "bool", "The opponent has an on-pitch GK."),
    ("gk_dist_to_goal_line_m", "m", "Opponent GK distance to its goal line along x (null without GK)."),
    ("gk_dist_to_shot_line_m", "m", "Opponent GK perpendicular distance to the segment ball to (gx, clamp(projected_y, +-3.66))."),
    ("gk_off_line_m", "m", "Opponent GK distance to its goal centre."),
    ("score_diff", "goals", "Shooting team score minus opponent score at the kick frame."),
    ("game_state", "-", "game_state of the kick frame."),
    ("previous_game_state_change_s", "s", "Seconds since game_state last changed (since the first frame if it never did); small after a set piece."),
    ("is_pass_by_ingest_rule", "bool", "Ingest is_pass with stabilised owners says the first owner after the kick is the shooting team."),
    ("detected_as_shot_by_ingest", "bool", "Ingest events.jsonl has a shot of the same team within +-3 frames."),
    ("teammates", "[x, y, role]", "Freeze frame: on-pitch players of the shooting team at the kick frame (includes the shooter), metres."),
    ("opponents", "[x, y, role]", "Freeze frame: on-pitch players of the other team at the kick frame, metres."),
    ("goal", "bool", "Shooting team score increases within 3.0 s of t_s before any touch by a teammate of the shooter (raw owner, player_id != shooter). Opponent touches (GK parry, deflection) do not cancel it (tracking only)."),
    ("goal_in_sequence", "bool", "Shooting team score increases within 3.0 s of t_s whoever touches the ball in between (goal implies goal_in_sequence). True with goal false: a teammate touched first (cross then finish), outcome is then kept."),
    ("next_owner_team", "-", "Team of the first raw owner after the kick other than the shooter, within 3.0 s (null if none)."),
    ("next_owner_role", "-", "Tracking role of that owner (null if none)."),
    ("outcome", "-", "goal; out (before any other player's touch and without a goal, the ball is beyond a goal line or touchline, |x| > length_m/2 or |y| > width_m/2, or the next tracking row has a frame_index gap > 1, i.e. a stoppage: tracking keeps in-play frames only); saved (next owner is the opponent GK); "
                     "blocked (opponent outfield next owner and the ball travelled < 50% of dist_goal_line); kept (next owner is the shooting team); other."),
    ("job_seed", "-", "Engine seed of the job that produced the row."), ("job_kind", "-", "full_match or situation."),
]


PASS_FIELDS = [  # (name, unit, definition)
    ("match_id", "-", "Match package id."), ("frame_index", "-", "Tracking frame of the reception (the ingest pass event frame)."),
    ("release_frame_index", "-", "Last frame, walking back from the reception over consecutive open-play frames, where the passer was the stable owner; the reception frame if none."),
    ("t_s", "s", "Seconds of video of the reception."), ("team", "-", "Passing team: home or away."), ("passer_id", "-", "player_id of the passer."),
    ("passer_role", "-", "Live tracking role of the passer at the release frame (null if absent)."),
    ("start_x_att", "m", "Pass start x oriented towards the opponent goal."), ("end_x_att", "m", "Pass end x oriented towards the opponent goal."),
    ("length_m", "m", "2D distance from pass start to end."), ("progressive_m", "m", "end_x_att - start_x_att (negative = backwards)."),
    ("start_third", "-", "Pitch third of the pass start: def_third, mid_third or att_third."),
    ("passer_pressure", "0-1", "Pressure on the passer at the release frame: sum over on-pitch opponents within 5 m of 1 - d/5, capped at 1."),
    ("opponents_near_line", "count", "On-pitch opponents (GK included) within 2.0 m of the segment start to end at the release frame."),
    ("nearest_opponent_to_receiver_m", "m", "Distance from the pass end to the nearest on-pitch opponent at the release frame."),
    ("lines_broken", "count", "Opponent lines (k-means of outfield x_att at the release frame) strictly between start and end along x_att, whatever the outcome."),
    ("game_state", "-", "game_state at the release frame."), ("score_diff", "goals", "Passing team score minus opponent score at the release frame."),
    ("complete", "bool", "Label: the ingest outcome is complete (false: intercepted)."),
]


def make_recipe(kind, seed):
    rng = random.Random(seed)

    def team():
        return dict(formation=rng.choice(sorted(CATALOG)), style=rng.choice(sorted(STYLES)), level=round(rng.uniform(0.7, 1.0), 3))
    d = dict(mode=kind, home=team(), away=team(), seed=seed)
    if kind == "situation":
        d |= dict(steps=300, situation=dict(template=rng.choice(sorted(TEMPLATES)), ball_owner=rng.choice(["home", "away"]),
                                            ends_when="steps"))
    return from_dict(d)


def run_job(job):
    kind, seed = job
    recipe = make_recipe(kind, seed)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = generate_from_recipe(recipe, seed, tmp, render=False)[0]
        except RuntimeError as err:
            return [], [], {"seed": seed, "kind": kind, "error": str(err)}
        rows, ev = read_jsonl(os.path.join(out, "tracking.jsonl")), read_jsonl(os.path.join(out, "events.jsonl"))
        meta = read_json(os.path.join(out, "meta.json"))
        ks = kick_candidates(rows, read_json(os.path.join(out, "roster.json")), meta, DEFAULTS, ev)
        ps = pass_features(rows, owners_for(rows), ev, {r["frame_index"]: i for i, r in enumerate(rows)}, meta)
    ks = [k | dict(job_seed=seed, job_kind=kind) for k in ks]
    ing = [e for e in ev if e["type"] == "shot"]
    hit = sum(any(k["team"] == e["team"] and abs(k["frame_index"] - e["frame_index"]) <= 3 for k in ks) for e in ing)
    return ks, ps, dict(seed=seed, kind=kind, recipe=to_dict(recipe), frames=len(rows), n_candidates=len(ks), passes=len(ps), passes_complete=sum(q["complete"] for q in ps),
                    goals=sum(k["goal"] for k in ks), goals_in_sequence=sum(k["goal_in_sequence"] for k in ks), ingest_shots=len(ing), ingest_shots_matched=hit)


def readme(summary):
    lines = [
        "# Shot and pass dataset v3: kick candidates and passes", "",
        "Every ball strike toward goal in synthetic matches and situations, with features from tracking and tracking-only outcome labels, to define what a shot is and to train an xG model. All data is synthetic, produced by the tacticAI engine; none of it is real football.", "",
        "A kick candidate is a frame where the horizontal ball speed is at least 10 m/s and either crossed 10 m/s from below, jumped by at least 5 m/s in one row, or the last raw ball owner changed to a player other than that team's previous candidate shooter; the last raw ball owner before it is the shooter, the ball moves toward that team's opponent goal, it is at most 40 m from the goal line and, for the same shooter, at least 10 tracking lines after that team's previous candidate. The projected y is not filtered. Coordinates are metres, home attacks +x, goal lines at x = +-54.4, posts at y = +-3.66, crossbar 2.44 m. Labels look 3.0 s ahead in tracking only, never in ingest events.", "",
        "## Generation", "", f"- Parameters: {json.dumps(summary['params'])}",
        f"- Full matches: seeds {FULL_SEED}.., random formation (8 of the catalog), style (4) and level in [0.7, 1.0] per team. Situations: seeds {SITUATION_SEED}.., random template (4), ball owner, 300 steps, random formations, styles and levels.",
        "- Headless engine, `generate_from_recipe(render=False)`; tracking is deleted after feature extraction.", "",
        "## Counts", "", f"- Jobs: {summary['jobs']} ({summary['jobs_failed']} failed with an engine error)",
        f"- Passes: {summary['passes']}, complete: {summary['passes_complete']}", f"- Candidates: {summary['candidates']}, goals: {summary['goals']}, goals in sequence: {summary['goals_in_sequence']}", f"- Outcomes: {json.dumps(summary['outcomes'])}", "",
        "## Files", "", "- `kicks.jsonl`: one candidate per line. `passes.jsonl`: one ingest pass per line (any outcome), features at the release frame. `jobs.jsonl`: one line per job (seed, recipe, frames, counts, ingest shot recall). `summary.json`: totals.", "",
        "## Fields", "", "| field | unit | definition |", "|---|---|---|"]
    table = lambda fs: [f"| {n} | {u} | {d} |" for n, u, d in fs]
    return "\n".join(lines + table(FIELDS) + ["", "## Pass fields (`passes.jsonl`)", "", "| field | unit | definition |", "|---|---|---|"] + table(PASS_FIELDS)) + "\n"


def build(matches, situations, workers, out):
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    jobs = [("full_match", FULL_SEED + i) for i in range(matches)] + [("situation", SITUATION_SEED + i) for i in range(situations)]
    outcomes, n, goals, seq, failed, npass, npc = Counter(), 0, 0, 0, 0, 0, 0
    with Pool(workers, maxtasksperchild=1) as p, open(os.path.join(out, "kicks.jsonl"), "w") as kf, \
            open(os.path.join(out, "jobs.jsonl"), "w") as jf, open(os.path.join(out, "passes.jsonl"), "w") as pf:
        for ks, ps, info in p.imap_unordered(run_job, jobs):
            kf.writelines(json.dumps(k) + "\n" for k in ks)
            pf.writelines(json.dumps(q) + "\n" for q in ps)
            jf.write(json.dumps(info) + "\n")
            kf.flush(), jf.flush(), pf.flush()
            npass, npc = npass + len(ps), npc + sum(q["complete"] for q in ps)
            n, goals, seq, failed = n + len(ks), goals + sum(k["goal"] for k in ks), seq + sum(k["goal_in_sequence"] for k in ks), failed + ("error" in info)
            outcomes.update(k["outcome"] for k in ks)
            print(f"{n} candidates, {goals} goals, {failed} failed, {time.time() - t0:.0f}s", flush=True)
    summary = dict(params=dict(matches=matches, situations=situations, workers=workers), jobs=len(jobs), jobs_failed=failed,
                   passes=npass, passes_complete=npc, candidates=n, goals=goals, goals_in_sequence=seq, outcomes=dict(outcomes), elapsed_s=round(time.time() - t0, 1))
    write_json(os.path.join(out, "summary.json"), summary)
    with open(os.path.join(out, "README.md"), "w") as f:
        f.write(readme(summary))
    return summary
