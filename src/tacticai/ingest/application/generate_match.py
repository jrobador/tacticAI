"""Generate one synthetic match as a contract package: video.mp4 + tracking.jsonl + roster.json + meta.json."""
import json
import os

from ..domain.clock import SECOND_HALF_STEP, STEPS_PER_MATCH
from ..domain.contract import make_row
from ..domain.formations import build_team, choose
from ..domain.pitch import PITCH
from ..domain.roster import build_roster
from ..infrastructure.engine_adapter import EngineMatch, H, PHYSICS_STEPS_PER_FRAME, W
from ...core.files import write_json
from ..infrastructure.video_writer import VideoWriter, count_frames
from ..infrastructure.watchdog import RenderWatchdog
from .infer_events import infer_events
from .recipe_config import EndWatch, recipe_config
from ..domain.recipe import to_dict

MAX_IDLE_FRAMES = 3000


def make_meta(match_id, seed, fl, fr, kick, rows, frames, mp4_frames, teams, **extra):
    """meta.json (contract) + the engine-specific facts under source.synthetic. kick: "home" / "away"."""
    return {
        "contract_version": 1, "match_id": match_id,
        "source": {"kind": "synthetic", "camera_setup": "synthetic", "detail": f"tacticAI engine, seed {seed}",
                   "synthetic": {"seed": seed, "engine": "tacticAI Match Engine",
                                 "engine_image_id": os.environ.get("TAI_ENGINE_IMAGE"), "steps": rows,
                                 "mp4_frames": mp4_frames, "physics_steps_per_frame": PHYSICS_STEPS_PER_FRAME,
                                 "kickoff_team": kick, "second_half_step": SECOND_HALF_STEP, **extra,
                                 "licenses": {"engine": "Apache-2.0 (with public-domain base)", "font": "SIL OFL 1.1"}}},
        "teams": teams, "pitch": PITCH, "video": {"fps": 10, "frames": frames, "width": W, "height": H},
        "formations": {"home": fl, "away": fr},
        "projection": {"applies": True, "effective_play_s": 3300}, "calibration": {"physical_absolute": False},
    }


def _simulate(game, out, seed, steps, render, frame_timeout, last_step, end_on=None, row0=0, frame0=0, preview_path=None):
    """Shared loop -> (rows, frames, mp4_frames or None, teams). Stops at `steps` in-play rows, at engine_step
    `last_step`, or when the engine reports the episode done. Counting starts at row0/frame0 (segments);
    `steps` stays absolute."""
    video = dog = None
    if render:
        video = VideoWriter(os.path.join(out, "video.mp4"), W, H, **({"preview_path": preview_path} if preview_path else {}))
        dog = RenderWatchdog(frame_timeout, out)
        dog.start()
    try:
        rows, frames, idle = row0, frame0, 0
        roster = teams = None
        watch = EndWatch(end_on)
        with open(os.path.join(out, "tracking.jsonl"), "w") as f:
            while rows < steps:
                obs, bgr = game.step()
                if render:
                    dog.progress(rows, frames)
                    video.write(bgr)
                ended = watch.update(obs)
                engine_step = obs.pop("engine_step")
                if obs.pop("in_play"):
                    if roster is None:
                        teams, roster = build_roster(*game.roster())
                    f.write(json.dumps(make_row(obs, rows, frames, engine_step)) + "\n")
                    f.flush()  # the API serves the last line of a running job
                    rows += 1
                    idle = 0
                else:
                    idle += 1
                frames += 1
                if idle >= MAX_IDLE_FRAMES:
                    raise RuntimeError(f"no in-play frame for {MAX_IDLE_FRAMES} consecutive frames (seed {seed})")
                if ended or engine_step >= last_step or game.done:
                    break
        mp4_frames = None
        if render:
            dog.stop()
            video.close()
            mp4_frames = count_frames(os.path.join(out, "video.mp4"))
    finally:
        if dog:
            dog.stop()  # a failing render must not leave a watchdog that later calls os._exit(3)
        if video and video.proc.poll() is None:  # not closed normally: kill ffmpeg and reap it
            video.proc.kill()
            video.proc.wait()
            try:
                video.proc.stdin.close()
            except OSError:
                pass
    if roster is None:
        raise RuntimeError(f"no in-play frame, cannot build roster (seed {seed})")
    write_json(os.path.join(out, "roster.json"), roster)
    return rows, frames, mp4_frames, teams


def generate_match(seed, steps, out_root, frame_timeout=60.0, render=True):
    """Returns (dir, rows, frames, mp4_frames). Raises RuntimeError on engine stall or ffmpeg failure.
    Exits the process (code 3) if no engine frame arrives within frame_timeout seconds."""
    fl, fr, kick = choose(seed)
    kick = "home" if kick == "left" else "away"
    game = EngineMatch(seed, build_team(fl, kick == "home"), build_team(fr, kick == "away"),
                       STEPS_PER_MATCH, SECOND_HALF_STEP, render=render)
    out = os.path.join(out_root, f"match_{seed}")
    os.makedirs(out, exist_ok=True)
    rows, frames, mp4_frames, teams = _simulate(game, out, seed, steps, render, frame_timeout, STEPS_PER_MATCH)
    write_json(os.path.join(out, "meta.json"), make_meta(os.path.basename(out), seed, fl, fr, kick, rows, frames,
                                                         mp4_frames, teams, recipe_mode=None, render=render))
    return out, rows, frames, mp4_frames


def generate_from_recipe(recipe, seed, out_root, render=True, frame_timeout=60.0, steps=None, preview_path=None):
    """Same outputs as generate_match plus recipe.json; also writes events.jsonl + events_summary.json."""
    cfg = recipe_config(recipe, seed, steps)
    kw = dict(cfg["kwargs"])
    kick = "home" if seed % 2 == 0 else "away"
    game = EngineMatch(seed, kw.pop("left"), kw.pop("right"), kw.pop("total_steps"), kw.pop("second_half_step"),
                       render=render, **kw)
    out = os.path.join(out_root, f"recipe_{recipe.mode}_{seed}")
    os.makedirs(out, exist_ok=True)
    rows, frames, mp4_frames, teams = _simulate(game, out, seed, cfg["steps"], render, frame_timeout,
                                                 3000 if recipe.mode == "full_match" else cfg["steps"], cfg["end_on"],
                                                 preview_path=preview_path)
    write_json(os.path.join(out, "recipe.json"), to_dict(recipe))
    write_json(os.path.join(out, "meta.json"), make_meta(
        os.path.basename(out), seed, recipe.home.formation, recipe.away.formation, kick, rows, frames, mp4_frames, teams,
        recipe_mode=recipe.mode, render=render, styles={"home": recipe.home.style, "away": recipe.away.style}))
    infer_events(out)
    return out, rows, frames, mp4_frames


def _skip_rows(game, rows_wanted, last_step):
    """Step headless, no files, counting in-play rows and frames exactly like _simulate -> (rows, frames, engine_step)."""
    rows = frames = idle = 0
    engine_step = -1
    while rows < rows_wanted:
        obs, _ = game.step()
        engine_step = obs["engine_step"]
        if obs["in_play"]:
            rows += 1
            idle = 0
        else:
            idle += 1
        frames += 1
        if idle >= MAX_IDLE_FRAMES or engine_step >= last_step or game.done:
            raise RuntimeError(f"match ended or stalled before in-play row {rows_wanted} (reached {rows})")
    return rows, frames, engine_step


def generate_segment(recipe, seed, from_step, to_step, out_root, frame_timeout=60.0):
    """Render in-play rows [from_step, to_step) of a recipe match: simulate headless to from_step, transfer the engine
    state to a render engine, record from there. Rows keep their original clock_s/frame_index.
    Returns (dir, rows, frames, mp4_frames) where rows/frames are the totals at the end (absolute)."""
    cfg = recipe_config(recipe, seed)

    def engine(render):
        kw = dict(cfg["kwargs"])
        return EngineMatch(seed, kw.pop("left"), kw.pop("right"), kw.pop("total_steps"), kw.pop("second_half_step"),
                           render=render, **kw)

    last_step = 3000 if recipe.mode == "full_match" else cfg["steps"]
    head = engine(False)
    row0, frame0, _ = _skip_rows(head, from_step, last_step)
    game = engine(True)
    game.set_state(head.get_state())
    game.env.render(True)  # get_frame() lags one render behind; prime it with the loaded scene so video frame 0 is right
    out = os.path.join(out_root, f"recipe_{recipe.mode}_{seed}_seg_{from_step}_{to_step}")
    os.makedirs(out, exist_ok=True)
    rows, frames, mp4_frames, teams = _simulate(game, out, seed, to_step, True, frame_timeout, last_step,
                                                 row0=row0, frame0=frame0)
    kick = "home" if seed % 2 == 0 else "away"
    write_json(os.path.join(out, "recipe.json"), to_dict(recipe))
    write_json(os.path.join(out, "meta.json"), make_meta(
        os.path.basename(out), seed, recipe.home.formation, recipe.away.formation, kick, rows, frames, mp4_frames, teams,
        recipe_mode=recipe.mode, render=True, styles={"home": recipe.home.style, "away": recipe.away.style},
        segment={"from_step": from_step, "to_step": to_step, "first_frame_index": frame0,
                 "video_frame0_is_frame_index": frame0}))
    infer_events(out)
    return out, rows, frames, mp4_frames
