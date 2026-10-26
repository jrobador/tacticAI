import pytest

from tacticai.interpret.domain import relative as R


def rows(n, gap_at=None):
    return [{"frame_index": i + (5 if gap_at is not None and i >= gap_at else 0), "t_s": i / 10, "game_state": "open_play", "camera": "main"} for i in range(n)]


def test_phases_loose_stays_loose_and_interruptions_are_none():
    rs = rows(8)
    rs[4]["game_state"] = "corner"
    owners = [None, ("home", "a"), None, ("away", "b"), None, ("away", "b"), None, None]
    assert R.phases(rs, owners, "home") == ["loose", "own", "loose", "opp", None, "opp", "loose", "loose"]
    assert R.phases(rs, owners, "away")[1:4] == ["opp", "loose", "own"]
    assert R.durations(rs)[3:5] == [pytest.approx(0.1), 0.0]


def test_windows_are_complete_and_never_cross_phase_or_gaps():
    rs = rows(130, gap_at=60)
    phs = ["own"] * 40 + ["opp"] * 90
    # run 1: 40 rows (4.0 s) -> fragment; run 2: rows 40..59 (2.0 s) fragment; run 3: rows 60..129 (7.0 s) -> one window of 50 rows + fragment
    assert R.windows(rs, phs) == [(60, 109)]
    assert R.windows(rs, ["opp"] * 130, window_s=2.0)[:2] == [(0, 19), (20, 39)] and R.windows(rs, phs, want="own") == []


def test_flag_runs_min_duration_and_gaps():
    rs = rows(20, gap_at=10)
    assert R.flag_runs(rs, [False] * 3 + [True] * 12 + [False] * 5, 0.5) == [(3, 9), (10, 14)]
    assert R.flag_runs(rs, [True] * 20, 2.5) == [] and R.flag_runs(rs, [True] * 20, 1.0) == [(0, 9), (10, 19)]


def test_reference_guards_and_place():
    assert R.reference([1.0, 5.0, 9.0], R.FLAT_IQR_M)["sufficient"] is False  # < 4 windows
    flat = R.reference([5.0, 5.2, 5.1, 5.0, 5.3], R.FLAT_IQR_M)
    assert flat["sufficient"] is False and "flat" in flat["reason"]
    assert R.reference([0.1, 0.12, 0.11, 0.1], R.FLAT_IQR_PRESSURE)["sufficient"] is False  # flat for pressure
    assert R.reference([0.0, 1.0, 2.0, 3.0], R.FLAT_IQR_M)["sufficient"] is True
    ref = R.reference([0.0, 10.0, 20.0, 30.0, 40.0], R.FLAT_IQR_M)
    assert (ref["q25"], ref["median"], ref["q75"], ref["max"]) == (10.0, 20.0, 30.0, 40.0)
    assert R.place(35.0, ref)["band"] == "high_relative" and R.place(5.0, ref)["band"] == "low_relative" and R.place(20.0, ref)["band"] == "typical"
    p = R.place(20.0, ref)
    assert p["percentile"] == pytest.approx(50.0) and p["rank"] == 3
    none = R.place(20.0, R.reference([1.0, 2.0], R.FLAT_IQR_M))
    assert none["band"] is None and none["percentile"] is None and none["q25"] is None and none["relative_reason"]


def test_window_values_and_rounded():
    rs = rows(100)
    ser = {i: float(i // 50) for i in range(100)}
    assert R.window_values(rs, ["opp"] * 100, ser, "opp") == [0.0, 1.0] and R.window_values(rs, ["opp"] * 100, {}, "opp") == []
    assert R.rounded({"a": [1.23456, (2.0, None)], "b": True}) == {"a": [1.235, [2.0, None]], "b": True}


def test_window_needs_full_effective_coverage():  # review #5
    rs = rows(100)
    ser = {i: 1.0 for i in range(100) if i != 7}  # one row of the first window has no value
    assert R.window_values(rs, ["opp"] * 100, ser, "opp") == [1.0]


def test_loose_is_never_a_reference_phase():  # review #2
    rs = rows(100)
    assert R.windows(rs, ["loose"] * 100) == [] and R.windows(rs, ["loose"] * 100, want="opp") == []


def test_place_treats_float_noise_as_equal():
    ref = R.reference([0.3, 1.0, 2.0, 3.0, 4.0], R.FLAT_IQR_M)
    p = R.place(0.1 + 0.2, ref)  # 0.30000000000000004 vs 0.3: exact equality would count it as above the window
    assert p["rank"] == 5 and p["percentile"] == pytest.approx(10.0)
