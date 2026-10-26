import json
import os

import pytest

from tacticai.interpret.domain import transitions as T
from tacticai.interpret.domain.phases import phase_candidates
from tacticai.interpret.domain.pressure import owners_for
from tacticai.interpret.domain.sequences import sequences
from tests.interpret.test_tactics_tools import counter_match, make_rows, tackle, varied

META = {"pitch": {"length_m": 108.8, "width_m": 70.2}}


def candidates(rows, events=()):
    owners = owners_for(rows)
    seqs, _ = sequences(rows, list(events), owners)
    return phase_candidates(rows, owners, list(events), seqs, META)


def test_counter_and_build_up_by_rule_only():
    over = lambda i: {"home-02": (min(34.0, -20.0 + (i - 50) * 1.8), 0.0)} if i >= 50 else {}
    rows = make_rows(150, owner_of=lambda i: "away-02" if i < 50 else "home-02", over=over)
    got = candidates(rows, [tackle(50, "home", "home-02", -20.0, "away-02")])
    assert [(c["candidate_id"], c["phase"], c["team"], c["from_t_s"]) for c in got] == [(0, "build_up", "away", 0.0), (1, "build_up", "home", 5.0), (2, "counter", "home", 5.0)]
    c = got[2]
    assert c["values"] == {"gain_m": 54.0, "duration_s": 5.0} and c["evidence"]["sequence_ids"] == [1] and c["evidence"]["event_indices"] == [0] and "start_xa < L/6" in c["rule"]
    # without the tackle the same movement is not a recovery: no counter
    assert [c["phase"] for c in candidates(rows)] == ["build_up", "build_up"]
    # a slower advance (< 20 m in 5 s) is not a counter
    slow = make_rows(150, owner_of=lambda i: "away-02" if i < 50 else "home-02", over=lambda i: {"home-02": (-20.0 + (i - 50) * 0.1, 0.0)} if i >= 50 else {})
    assert candidates(slow, [tackle(50, "home", "home-02", -20.0, "away-02")])[-1]["phase"] == "build_up"


def test_first_sequence_is_not_a_gain():
    rows = make_rows(100, owner_of=lambda i: "home-02")
    owners = owners_for(rows)
    seqs, _ = sequences(rows, [], owners)
    assert T.gains(seqs) == []


def test_low_block_needs_a_relative_reference():
    shifts = [0.0, 0.0, 30.0, 30.0, 30.0, 30.0]  # block h = 34.4 (low) then 64.4; own half only in the first 10 s
    rows = make_rows(300, shift_of=lambda i: shifts[i // 50])
    low = [c for c in candidates(rows) if c["phase"] == "low_block"]
    assert len(low) == 1 and low[0]["team"] == "home" and low[0]["from_t_s"] == 0.0 and low[0]["until_t_s"] == 9.9 and low[0]["values"]["block_height_m"] == 34.4
    assert not [c for c in candidates(make_rows(300)) if c["phase"] in ("low_block", "high_press")]  # flat: no reference, no relative candidate
    assert not [c for c in candidates(make_rows(60, shift_of=varied)) if c["phase"] in ("low_block", "high_press")]  # < 4 windows


def test_phases_jsonl_ids_are_consecutive_and_sorted(tmp_path):
    d, _ = counter_match(tmp_path)
    lines = [json.loads(l) for l in open(os.path.join(d, "interpret", "phases.jsonl"))]
    assert [c["candidate_id"] for c in lines] == [0, 1, 2] and [c["from_t_s"] for c in lines] == sorted(c["from_t_s"] for c in lines)
    assert set(lines[0]) == {"candidate_id", "phase", "team", "from_t_s", "until_t_s", "rule", "evidence", "values"} and set(lines[0]["evidence"]) == {"event_indices", "sequence_ids", "frame_ranges"}


def test_build_up_inside_a_possession_without_minimum():  # review #8
    # home keeps the ball all the time; it drops into its own third for 0.5 s after a spell outside it
    xs = lambda i: -30.0 if 50 <= i < 55 else 0.0
    rows = make_rows(100, owner_of=lambda i: "home-02", over=lambda i: {"home-02": (xs(i), 0.0)})
    got = [c for c in candidates(rows) if c["phase"] == "build_up"]
    assert [(c["team"], c["from_t_s"], c["values"]["outcome"]) for c in got] == [("home", 5.0, "exited_third")] and got[0]["values"]["duration_s"] == pytest.approx(0.5)


HP_FRAMES = (20, 70, 120, 170, 220, 270)


def hp_events(x):
    return [dict(type="tackle", frame_index=f, t_s=f / 10, team="home", player_id="home-03", x=x, y=0.0, from_player_id="away-02", period=1) for f in HP_FRAMES]


def hp_rows():
    d = [4.0, 1.0] * 3
    shifts = [0.0, 20.0, 0.0, 30.0, 0.0, 40.0]
    return make_rows(300, owner_of=lambda i: "away-02", shift_of=lambda i: shifts[i // 50], over=lambda i: {"away-02": (25.0, 0.0), "home-03": (25.0 - d[i // 50], 0.0)})


def test_high_press_regain_evidence_inside_interval_and_ppda_alternative():  # review #6, #7
    hp = [c for c in candidates(hp_rows(), hp_events(30.0)) if c["phase"] == "high_press"]
    assert hp and all(c["from_t_s"] <= HP_FRAMES[j] / 10 <= c["until_t_s"] for c in hp for j in c["evidence"]["event_indices"])
    # regains in the zone but not high (x = 10 < L/6): no candidate without the PPDA alternative
    assert not [c for c in candidates(hp_rows(), hp_events(10.0)) if c["phase"] == "high_press"]
    # with rival passes in the zone, the last 5 s have the lowest PPDA proxy of the match: the alternative fires
    passes = [dict(type="pass", frame_index=f, t_s=f / 10, team="away", player_id="away-02", x=0.0, y=0.0, outcome="completed", intercepted_by=None, period=1)
              for w, n in enumerate([6, 5, 4, 3, 2, 1]) for f in range(w * 50 + 1, w * 50 + 1 + n)]
    ev = sorted(hp_events(10.0) + passes, key=lambda e: e["frame_index"])
    got = [c for c in candidates(hp_rows(), ev) if c["phase"] == "high_press"]
    assert len(got) == 1 and got[0]["from_t_s"] == 25.0 and got[0]["values"]["ppda_proxy"] == 1.0 and got[0]["values"]["high_regains"] == 0 and "PPDA proxy" in got[0]["rule"]


def test_high_press_does_not_join_across_own_possession():  # review #6
    shifts = lambda i: 0.0 if i < 50 else 40.0 if i < 100 else 50.0 if i < 200 else 0.0
    d = lambda i: 1.0 if 50 <= i < 200 else 4.0
    mk = lambda own: make_rows(300, owner_of=own, shift_of=shifts, over=lambda i: {"away-02": (25.0, 0.0), "home-03": (25.0 - d(i), 0.0)})
    ev = [tackle(190, "home", "home-03", 30.0, "away-02")]
    split = [c for c in candidates(mk(lambda i: "home-02" if 100 <= i < 110 else "away-02"), ev) if c["phase"] == "high_press"]
    assert all(not (c["from_t_s"] < 10.0 and c["until_t_s"] >= 11.0) for c in split)
