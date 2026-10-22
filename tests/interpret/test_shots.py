import math

import pytest

from tacticai.ingest.domain.events import DEFAULTS
from tacticai.interpret.domain.shots import in_triangle, kick_candidates, visible_angle_deg

META = {"match_id": "m", "pitch": {"length_m": 108.8, "width_m": 70.2}}
ROSTER = {"players": [{"player_id": f"{s}-{k:02d}", "team": s, "name": "n", "number": k + 1, "role": "GK" if k == 0 else "CM"}
                      for s in ("home", "away") for k in range(11)]}


def fr(i, ball=(40.0, 0.0), v=(0.0, 0.0), z=0.0, vz=0.0, pos=None, state="open_play", score=(0, 0)):
    pl = {f"home-{k:02d}": (-20.0, 3.0 * k) for k in range(11)} | {f"away-{k:02d}": (-25.0, 3.0 * k) for k in range(11)}
    pl |= {"home-00": (-53.0, 0.0), "away-00": (53.0, 0.0)} | (pos or {})
    return dict(frame_index=i, t_s=i / 10, clock_s=i / 10, period=1, game_state=state, score=dict(home=score[0], away=score[1]),
                ball=dict(x=ball[0], y=ball[1], z=z, vx=v[0], vy=v[1], vz=vz),
                players=[dict(player_id=p, x=x, y=y, on_pitch=True, role="GK" if p.endswith("00") else "CM") for p, (x, y) in pl.items()])


def run(rows):
    return kick_candidates(rows, ROSTER, META, DEFAULTS)


def kick(after, kick_pos=None):
    """home-05 holds the ball at (40, 0), strikes it at row 2 (20 m/s toward goal); `after` = rows 3.."""
    own = {"home-05": (40.2, 0.0)}
    return [fr(0, pos=own), fr(1, pos=own), fr(2, v=(20.0, 0.0), pos=kick_pos or own)] + after


def test_geometry():
    assert visible_angle_deg(43.4, 0, 54.4) == pytest.approx(2 * math.degrees(math.atan(3.66 / 11)), abs=1e-6)
    assert visible_angle_deg(43.4, 0, 54.4) == pytest.approx(36.8, abs=0.1)
    assert in_triangle((50, 3), (40, 5), (54.4, -3.66), (54.4, 3.66))
    assert not in_triangle((41, 5), (40, 5), (54.4, -3.66), (54.4, 3.66))
    assert not in_triangle((54.4, 0), (40, 5), (54.4, -3.66), (54.4, 3.66))  # on the edge is not strictly inside


def test_features():
    own = {"home-05": (40.2, 5.0)}
    rows = [fr(0, (40, 5), pos=own), fr(1, (40, 5), pos=own),
            fr(2, (40, 5), (20.0, -2.0), z=0.3, vz=4.0,
               pos={"home-05": (40.2, 5.0), "away-03": (50, 3), "away-04": (41, 5), "away-00": (53, 2)})]
    [c] = run(rows)
    assert (c["team"], c["shooter_id"], c["shooter_role"], c["shooter_number"]) == ("home", "home-05", "CM", 6)
    assert c["projected_y_at_goal_m"] == pytest.approx(3.56) and c["projected_z_at_goal_m"] == pytest.approx(0.64, abs=0.01)
    assert c["on_target_projection"] and c["in_box"] and not c["header"]
    assert c["defenders_in_cone"] == 1 and c["defenders_within_3m"] == 1 and c["nearest_defender_m"] == pytest.approx(1.0)
    assert c["gk_present"] and c["gk_dist_to_goal_line_m"] == pytest.approx(1.4)
    assert c["gk_off_line_m"] == pytest.approx(math.hypot(1.4, 2), abs=0.01) and c["gk_dist_to_shot_line_m"] == pytest.approx(1.69, abs=0.01)
    assert c["detected_as_shot_by_ingest"] is None and c["previous_game_state_change_s"] == pytest.approx(0.2)
    assert len(c["teammates"]) == len(c["opponents"]) == 11 and c["opponents"][0][2] in ("GK", "CM")
    rows[2]["ball"]["vz"] = 1.0  # ballistic: lands under the grass before the goal line
    assert not run(rows)[0]["on_target_projection"]
    assert run(rows)[0]["projected_z_at_goal_m"] < 0


def test_not_candidates():
    assert run(kick([])) and not run([fr(0, pos={"away-05": (40.2, 0)}), fr(1, pos={"away-05": (40.2, 0)}),
                                      fr(2, v=(20.0, 0.0), pos={"away-05": (40.2, 0)})])  # away shoots toward -x: moving +x is away from its goal
    assert not run([fr(i, (0, 0), pos={"home-05": (0.2, 0)}) if i < 2 else fr(i, (0, 0), (20.0, 0.0), pos={"home-05": (0.2, 0)})
                    for i in range(3)])  # 54 m from the goal line
    two = kick([fr(3, (42, 0), (5.0, 0.0), pos={"home-05": (42.2, 0)}), fr(4, (44, 0), (20.0, 0.0), pos={"home-05": (42.2, 0)})])
    assert len(run(two)) == 1  # second crossing within 10 lines is debounced
    assert run(kick([]))[0]["is_pass_by_ingest_rule"] is False


def outcome(after):
    [c] = run(kick(after))
    return c["outcome"], c["goal"], c["next_owner_team"], c["next_owner_role"]


def test_goal_credit_and_out():
    mate = [fr(3, (45, 0), pos={"home-06": (45.2, 0)}), fr(4, (54, 0), score=(1, 0))]  # cross, teammate finishes
    assert outcome(mate) == ("kept", False, "home", "CM") and run(kick(mate))[0]["goal_in_sequence"]
    defl = [fr(3, (45, 0), pos={"away-03": (45.2, 0)}), fr(4, (54, 0), score=(1, 0))]  # defender deflects it in
    assert outcome(defl) == ("goal", True, "away", "CM") and run(kick(defl))[0]["goal_in_sequence"]
    assert not run(kick([fr(3, (45, 0))]))[0]["goal_in_sequence"]
    assert outcome([fr(3, (50, 0)), fr(4, (55, 8))]) == ("out", False, None, None)  # beyond the goal line, wide of the posts
    assert outcome([fr(3, (45, 0)), fr(4, (45, 36))])[0] == "out"  # beyond the touchline
    assert outcome([fr(3, (50, 0)), fr(8, (50, 0))])[0] == "out"  # frame_index gap: stoppage
    assert outcome([fr(3, (50, 0), pos={"away-03": (50.3, 0)}), fr(8, (50, 0))])[0] == "other"  # touch first
    assert outcome([fr(3, (50, 0)), fr(4, (50, 0), score=(0, 1))])[:2] == ("other", False)


def test_one_touch_candidate():
    own = {"home-05": (41.0, 0.0)}
    rows = [fr(0, (40, 0), (12.0, 0.0)), fr(1, (41, 0), (12.0, 0.0), pos=own), fr(2, (42.4, 0), (20.0, 0.0), pos=own)]
    assert len(run(rows)) == 1  # ball already >= 10 m/s: no crossing from below


def test_outcomes():
    own = {"home-05": (40.2, 0.0)}
    assert outcome([fr(3, (41, 0), (20, 0), pos=own), fr(4, (50, 0), pos={"away-00": (50.5, 0)}, score=(0, 0))])[0] == "saved"
    assert outcome([fr(3, (41, 0), pos={"away-03": (41.3, 0)})]) == ("blocked", False, "away", "CM")
    assert outcome([fr(3, (50, 0), pos={"away-03": (50.3, 0)})])[0] == "other"  # outfield touch after > 50% of the distance
    assert outcome([fr(3, (45, 0), pos={"home-06": (45.2, 0)})]) == ("kept", False, "home", "CM")
    assert outcome([fr(3, (50, 0), pos={"away-00": (50.5, 0)}), fr(4, (60, 0))])[0] == "saved"  # touch first
    assert outcome([fr(3, (45, 0)), fr(4, (54, 0), score=(1, 0))])[:2] == ("goal", True)
    assert outcome([fr(3, (45, 0)), fr(40, (54, 0), score=(1, 0))])[:2] == ("other", False)  # goal 3.8 s later is outside the window
    assert outcome([fr(3, (45, 0)), fr(4, (50, 0), score=(0, 1))])[:2] == ("other", False)  # only the shooting team's goal counts
    assert outcome([fr(3, (41, 0), pos=own)])[0] == "other"  # the shooter's own contact is not a new owner


def test_ingest_flag():
    ev = [dict(type="shot", team="home", frame_index=4), dict(type="shot", team="away", frame_index=2)]
    assert kick_candidates(kick([]), ROSTER, META, DEFAULTS, ev)[0]["detected_as_shot_by_ingest"] is True
    assert kick_candidates(kick([]), ROSTER, META, DEFAULTS, ev[1:])[0]["detected_as_shot_by_ingest"] is False


def test_field_dictionary_matches_rows():
    from tacticai.interpret.application.build_shot_dataset import FIELDS, make_recipe
    [c] = run(kick([]))
    assert [n for n, _, _ in FIELDS if n not in ("job_seed", "job_kind")] == list(c)
    assert make_recipe("situation", 50000).situation.template and make_recipe("full_match", 1000).mode == "full_match"
