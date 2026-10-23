"""Pure tracking-quality summary (contract interpret/quality.json). identity_swaps_suspected is a cheap proxy: player position jumps above SWAP_JUMP_M between consecutive frames."""
import math

HIGH = {"main_camera_share": 0.95, "players_observed_share": 0.9, "mean_confidence": 0.8}
MEDIUM = {"main_camera_share": 0.8, "players_observed_share": 0.7, "mean_confidence": 0.6}
SWAP_JUMP_M = 3.0


def quality(rows, meta):
    n = len(rows)
    ps = [p for r in rows for p in r["players"] if p["on_pitch"]]
    conf = [p["confidence"] for p in ps] + [r["ball"]["confidence"] for r in rows]
    gaps = swaps = 0
    for a, b in zip(rows, rows[1:]):
        if b["frame_index"] - a["frame_index"] > 1:
            gaps += 1
        else:
            pa = {p["player_id"]: p for p in a["players"] if p["on_pitch"]}
            swaps += sum(p["player_id"] in pa and math.dist((p["x"], p["y"]), (pa[p["player_id"]]["x"], pa[p["player_id"]]["y"])) > SWAP_JUMP_M
                         for p in b["players"] if p["on_pitch"])
    out = {"camera_setup": meta["source"]["camera_setup"], "tracking_lines": n, "video_frames": meta["video"]["frames"],
           "main_camera_share": sum(r["camera"] == "main" for r in rows) / n if n else 0.0,
           "ball_observed_share": sum(r["ball"]["observed"] for r in rows) / n if n else 0.0,
           "players_observed_share": sum(p["observed"] for p in ps) / len(ps) if ps else 0.0,
           "mean_confidence": sum(conf) / len(conf) if conf else 0.0, "gaps": gaps, "identity_swaps_suspected": swaps}
    out["level"] = "high" if all(out[k] >= v for k, v in HIGH.items()) else "medium" if all(out[k] >= v for k, v in MEDIUM.items()) else "low"
    out["notes"] = [f"{k} {out[k]:.2f} below {v}" for k, v in HIGH.items() if out[k] < v]
    return out
