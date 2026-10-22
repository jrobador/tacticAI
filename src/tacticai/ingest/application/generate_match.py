"""Generate one synthetic match: video.mp4 + tracking.jsonl + roster.json + meta.json."""
import json
import os

from ..domain.clock import MATCH_DURATION_FACTOR, SECOND_HALF_STEP, STEPS_PER_MATCH, engine_time_s, match_time_s
from ..domain.formations import build_team, choose
from ..domain.roster import build_roster
from ..domain.pitch import DRAW_X, DRAW_Y, ENG_X, ENG_Y, to_draw, to_eng
from ..infrastructure.engine_adapter import EngineMatch, H, PHYSICS_STEPS_PER_FRAME, W
from ..infrastructure.files import write_json
from ..infrastructure.video_writer import VideoWriter, count_frames
from ..infrastructure.watchdog import RenderWatchdog

MAX_IDLE_FRAMES = 3000


def make_row(obs, step, fi, engine_step):
    """Tracking row: engine observation + clocks + pitch-scaled copies (*_eng canonical, *_m drawing only)."""
    d = {"step": step, "frame_index": fi, "engine_time_s": engine_time_s(fi), "match_time_s": match_time_s(step), **obs}
    d["steps_left"] = STEPS_PER_MATCH - engine_step
    b = d["ball"]
    d["ball_m"] = [round(b[0] * DRAW_X, 3), round(b[1] * DRAW_Y, 3), round(b[2], 3)]
    d["ball_eng"] = [round(b[0] * ENG_X, 3), round(b[1] * ENG_Y, 3), round(b[2], 3)]
    for t in ("left", "right"):
        d[f"{t}_team_m"] = to_draw(d[f"{t}_team"])
        d[f"{t}_team_eng"] = to_eng(d[f"{t}_team"])
    d["half"] = 2 if engine_step >= SECOND_HALF_STEP else 1
    return d


def make_meta(seed, fl, fr, kick, rows, frames, mp4_frames, roster):
    return {
        "seed": seed, "engine": "tacticAI Match Engine", "engine_image_id": os.environ.get("TAI_ENGINE_IMAGE"),
        "steps": rows, "frames": frames, "mp4_frames": mp4_frames, "fps": 10, "physics_steps_per_frame": 10,
        "formations": {"left": fl, "right": fr}, "kickoff_team": kick, "second_half_step": SECOND_HALF_STEP,
        "teams": {"left": roster["left"]["short"], "right": roster["right"]["short"]},
        "frame_mapping": "every engine frame is in the video; tracking rows only for in-play frames; "
                         "frame_index is exact by construction",
        "time": {
            "engine_time_s": "frame_index * 0.1 (0.1 s per rendered frame)",
            "match_time_s": "step * 0.1 / 0.0554 (step counts in-play rows only)",
            "engine_time_s_factor": 0.1, "match_time_s_divisor": MATCH_DURATION_FACTOR,
        },
        "velocity_note": "*_direction = displacement per step (0.1 s) in observation units; "
                         "speed_m_s = hypot(dx*54.4, dy*83.6)*10; km/h = *3.6",
        "coordinates": {
            "canonical": "*_eng (engine metres) — use for every distance, speed and event position",
            "drawing_only": "*_m (normalized 105x68: x*52.5, y*34/0.42) — only for drawing on a standard pitch, never for calculations",
            "engine_pitch_note": "The engine pitch is defined as pitchHalfW=55, pitchHalfH=36 (110x72 m), while the "
                                 "observation scale maps the goal line x=±1 to ±54.4 m and y=±0.42 to ±35.1 m.",
            "orientation": "left/home team attacks +x, +y is the bottom touchline",
        },
        "orientation_home": "left team, attacks +x",
        "licenses": {"engine": "Apache-2.0 (with public-domain base)", "font": "SIL OFL 1.1"},
    }


def generate_match(seed, steps, out_root, frame_timeout=60.0):
    """Returns the match directory. Raises RuntimeError on engine stall or ffmpeg failure.
    Exits the process (code 3) if no engine frame arrives within frame_timeout seconds."""
    fl, fr, kick = choose(seed)
    game = EngineMatch(seed, build_team(fl, kick == "left"), build_team(fr, kick == "right"),
                       STEPS_PER_MATCH, SECOND_HALF_STEP)
    out = os.path.join(out_root, f"match_{seed}")
    os.makedirs(out, exist_ok=True)
    mp4 = os.path.join(out, "video.mp4")
    video = VideoWriter(mp4, W, H)
    frames = rows = idle = 0
    roster = None
    dog = RenderWatchdog(frame_timeout, out)
    dog.start()
    with open(os.path.join(out, "tracking.jsonl"), "w") as f:
        while rows < steps:
            obs, bgr = game.step()
            dog.progress(rows, frames)
            video.write(bgr)
            engine_step = obs.pop("engine_step")
            if obs.pop("in_play"):
                if roster is None:
                    roster = build_roster(*game.roster())
                f.write(json.dumps(make_row(obs, rows, frames, engine_step)) + "\n")
                rows += 1
                idle = 0
            else:
                idle += 1
            frames += 1
            if idle >= MAX_IDLE_FRAMES:
                raise RuntimeError(f"no in-play frame for {MAX_IDLE_FRAMES} consecutive frames (seed {seed})")
            if engine_step >= STEPS_PER_MATCH:
                break
    dog.stop()
    video.close()
    mp4_frames = count_frames(mp4)
    if roster is None:
        raise RuntimeError(f"no in-play frame, cannot build roster (seed {seed})")
    write_json(os.path.join(out, "roster.json"), roster)
    write_json(os.path.join(out, "meta.json"), make_meta(seed, fl, fr, kick, rows, frames, mp4_frames, roster))
    return out, rows, frames, mp4_frames
