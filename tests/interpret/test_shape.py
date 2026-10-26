import pytest

from tacticai.interpret.domain.shape import LANES, lane, low_block_episodes, occupation, row_metrics

L, W = 108.8, 70.2


def pl(pid, x, y, role="CM", on=True):
    return {"player_id": pid, "x": x, "y": y, "role": role, "on_pitch": on}


def frame(players):
    return {"players": players}


HOME = [pl("home-00", -50, 0, "GK"), pl("home-01", -30, -10), pl("home-02", -20, 0), pl("home-03", -10, 10), pl("home-04", 0, 5), pl("home-05", 10, -20), pl("home-06", 40, 40, on=False)]


def test_hand_geometry():
    m = row_metrics(frame(HOME), "home", L)  # outfield xa: -30 -20 -10 0 10 -> h = xa + 54.4
    assert m["block_height"] == pytest.approx(54.4 - 10) and m["defensive_line"] == pytest.approx((24.4 + 34.4 + 44.4 + 54.4) / 4)
    assert m["length"] == pytest.approx(40) and m["width"] == pytest.approx(30)  # ya -20 .. 10
    assert row_metrics(frame([pl("home-00", 0, 0, "GK")]), "home", L) is None


def test_away_is_the_mirror_of_home():
    mirror = [pl(p["player_id"].replace("home", "away"), -p["x"], -p["y"], p["role"], p["on_pitch"]) for p in HOME]
    assert row_metrics(frame(mirror), "away", L) == row_metrics(frame(HOME), "home", L)


def test_lanes_and_occupation():
    assert [lane(y, W) for y in (-30, -10, 0, 10, 30)] == list(LANES)
    rows = [frame(HOME)] * 3
    cells = occupation(rows, [0.1, 0.1, 0.0], [0, 1], "home", L, W)
    assert cells["def_third"]["half_left"] == {"player_s": pytest.approx(0.2), "mean_players": pytest.approx(1.0)}
    assert cells["att_third"]["center"]["player_s"] == 0.0 and cells["mid_third"]["center"]["mean_players"] == pytest.approx(1.0)  # xa 0 (home-04) is mid third


def test_low_block_episodes():
    rows = [{"frame_index": i, "t_s": i / 10} for i in range(30)]
    phs = ["opp"] * 30
    bh = {i: (30.0 if 5 <= i < 28 else 60.0) for i in range(30)}  # own half and below q25 = 40 on rows 5..27 (2.3 s + step)
    assert low_block_episodes(rows, phs, bh, L, 40.0) == [(5, 27)]
    assert low_block_episodes(rows, phs, {**bh, **{i: 60.0 for i in range(15, 28)}}, L, 40.0) == []  # 1.0 s only
    assert low_block_episodes(rows, ["own"] * 30, bh, L, 40.0) == []  # not defending
    assert low_block_episodes(rows, phs, bh, L, 20.0) == []  # not below q25
