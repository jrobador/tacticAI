from tacticai.interpret.domain.patterns import tactical_notes


def tl(mom=None, hp=None, ap=None, n=None, xg=None):
    n = n or len(mom or hp or ap)
    mom, hp, ap = mom or [0.0] * n, hp or [0.2] * n, ap or [0.2] * n
    return [{"window": i, "start_t_s": 10.0 * i, "end_t_s": 10.0 * i + 9, "start_clock_s": 100.0 * i, "end_clock_s": 100.0 * i + 90, "period": 1, "momentum": mom[i],
             "home": {"pressure": hp[i], "xg": (xg or {}).get(i, 0.0), "final_third_entries": 1, "possession_share": 0.5},
             "away": {"pressure": ap[i], "xg": 0.0, "final_third_entries": 0, "possession_share": 0.5}} for i in range(n)]


def seq(i, team="home", lines=0, end="lost", t0=0.0):
    return {"sequence_id": i, "team": team, "start_t_s": t0, "end_t_s": t0 + 5, "start_clock_s": t0 * 10, "period": 1, "end_cause": end, "passes": 4, "duration_s": 5.0, "lines_broken": lines, "xg": 0.1}


def shot(xg, outcome="no_goal", t=1.0, team="home"):
    return {"type": "shot", "team": team, "t_s": t, "clock_s": t * 10, "period": 1, "frame_index": 7, "player_id": "home-09", "xg": xg, "outcome": outcome}


def run(timeline=(), seqs=(), events=(), kind=None):
    ns = tactical_notes(list(timeline), list(seqs), list(events), {})
    return [n for n in ns if kind is None or n["kind"] == kind]


def test_pressure_shift_threshold_and_sparsity():
    assert run(tl(hp=[0.2] * 3 + [0.35] * 3), kind="pressure_shift")  # exactly 0.15 fires
    assert not run(tl(hp=[0.2] * 3 + [0.34] * 3), kind="pressure_shift")
    n = run(tl(hp=[0.5] * 3 + [0.2] * 3), kind="pressure_shift")[0]
    assert n["text_key"] == "pressure_down" and n["team"] == "home" and n["evidence"] == {"timeline_windows": [0, 1, 2, 3, 4, 5], "metric": "pressure", "before": 0.5, "after": 0.2}
    got = run(tl(hp=[0.0] * 3 + [0.3] * 3 + [0.0] * 3), kind="pressure_shift")  # k=3 down/up neighbours: one per 3 windows
    assert len(got) == 1 and got[0]["text_key"] == "pressure_up" or len(got) == 2 and got[0]["team"] == got[1]["team"]
    assert not run(tl(hp=[None] * 3 + [0.9] * 3), kind="pressure_shift")


def test_pressure_peak():
    n = run(tl(hp=[0.1, 0.9, 0.2, 0.2]), kind="pressure_peak")
    h = next(x for x in n if x["team"] == "home")
    assert h["text_key"] == "highest_pressure_of_match" and h["evidence"]["timeline_windows"] == [1] and h["evidence"]["value"] == 0.9 and h["evidence"]["match_mean"] == 0.35


def test_momentum_swing_edges():
    assert run(tl(mom=[-0.2, 0.2]), kind="momentum_swing")[0]["text_key"] == "momentum_to_home"  # change 0.4 fires
    assert not run(tl(mom=[-0.19, 0.2]), kind="momentum_swing")
    assert not run(tl(mom=[-0.35, 0.05]), kind="momentum_swing")  # change 0.4 but new value 0.05 < 0.1
    assert not run(tl(mom=[0.1, 0.9]), kind="momentum_swing")  # no sign change
    flip = run(tl(mom=[0.5, 0.5, 0.1, -0.1, -0.5, -0.5]), kind="momentum_swing")  # steps too small for a jump; the 3-window means flip
    assert [(n["text_key"], n["evidence"]["mean_before"]) for n in flip] == [("momentum_to_away", 0.367)]
    assert not run(tl(mom=[0.4, 0.4, 0.0, 0.0, -0.4, -0.4]), kind="momentum_swing")  # means +-0.267 < 0.3



def test_dominance_spell():
    n = run(tl(mom=[0.0, 0.4, 0.5, 0.6, 0.0]), kind="dominance_spell")
    assert len(n) == 1 and n[0]["team"] == "home" and n[0]["evidence"]["timeline_windows"] == [1, 2, 3] and n[0]["evidence"]["mean_momentum"] == 0.5
    assert n[0]["evidence"]["final_third_entries"] == {"home": 3, "away": 0}
    assert not run(tl(mom=[0.4, 0.4, 0.39]), kind="dominance_spell")
    assert run(tl(mom=[-0.4] * 3), kind="dominance_spell")[0]["team"] == "away"


def test_line_breaking():
    ss = [seq(0, lines=2, end="shot"), seq(1, lines=3, end="lost", t0=10), seq(2, lines=2, end="lost", t0=20), seq(3, "away", lines=0, t0=30), seq(4, "away", lines=1, end="lost", t0=40)]
    got = {n["evidence"]["sequence_ids"][0]: n for n in run(seqs=ss, kind="line_breaking_sequence")}
    assert set(got) == {0, 1, 4} and got[0]["text_key"] == "line_breaking_move" and got[0]["evidence"]["lines_broken"] == 2 and got[4]["team"] == "away"


def test_big_chance_edges():
    ev = [shot(0.3, "goal"), shot(0.29, t=2), shot(0.5, t=3), shot(None, t=4)]
    got = run(events=ev, kind="big_chance")
    assert [(n["text_key"], n["evidence"]["event_indices"]) for n in got] == [("big_chance_scored", [0]), ("big_chance_missed", [2])]
    assert got[0]["evidence"]["player_id"] == "home-09" and got[0]["strength"] == 0.3


def test_dedupe_keeps_strongest_and_evidence_never_empty():
    ss = [seq(0, lines=2, end="shot"), seq(1, lines=5, end="shot", t0=2)]  # overlap in time, same team
    got = run(seqs=ss, kind="line_breaking_sequence")
    assert [n["evidence"]["sequence_ids"] for n in got] == [[1]]
    ns = run(tl(mom=[-0.5, 0.5, 0.5, 0.5, 0.5], hp=[0.1, 0.1, 0.1, 0.6, 0.6]), ss, [shot(0.6, "goal")])
    assert ns and all(n["evidence"] and 0 <= n["strength"] <= 1 for n in ns) and ns == sorted(ns, key=lambda n: n["t_s"])
