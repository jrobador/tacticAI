import json
import os
from pathlib import Path

import pytest

from tacticai.render.application import heatmaps as H

REAL = Path(__file__).resolve().parents[2] / "data" / "matches" / "20261023-235553-f205"


def row(f, x, state="open_play", period=1, on=True, pid="home-09", camera="main"):
    return {"frame_index": f, "t_s": f / 10, "period": period, "game_state": state, "camera": camera,
            "players": [{"player_id": pid, "x": x, "y": 0.0, "on_pitch": on}]}


def test_pairs_cells_clamp_and_null():
    rows = [row(0, -54.4), row(1, 54.4), row(2, 99.0), row(3, 0.0, state="dead_ball"), row(4, 0.0), row(6, 0.0), row(7, 0.0, period=2), row(8, 0.0, period=2)]
    out = H.compute(rows, ["home-09", "home-00"], 108.8, 70.2)
    p = out["players"]
    assert out["bounds"] == {"x": [-54.4, 54.4], "y": [-35.1, 35.1]} and (out["x_bins"], out["y_bins"]) == (16, 12)
    assert p["home-09"]["eligible_s"] == 0.3  # 0->1, 1->2 and 7->8; 2->3, 3->4 not open both; 4->6 not consecutive; 6->7 other period
    g = p["home-09"]["grid"]
    assert g[0][6] == 0.1 and g[15][6] == 0.1 and g[8][6] == 0.1 and round(sum(map(sum, g)), 3) == 0.3  # x=99 is clamped to the last column of the grid
    assert p["home-00"] == {"eligible_s": 0.0, "grid": None}


def test_player_off_pitch_is_not_counted():
    out = H.compute([row(0, 0.0), row(1, 0.0, on=False)], ["home-09"], 108.8, 70.2)
    assert out["players"]["home-09"] == {"eligible_s": 0.0, "grid": None}


@pytest.mark.skipif(not (REAL / "tracking.jsonl").exists(), reason="no recorded match")
def test_grid_sum_equals_eligible_on_real_match(tmp_path):
    import shutil
    d = tmp_path / "m"
    d.mkdir()
    for n in ("meta.json", "roster.json", "tracking.jsonl"):
        shutil.copy(REAL / n, d / n)
    H.run(str(d))
    out = json.loads((d / "render" / "heatmaps.json").read_text(encoding="utf-8"))
    with_grid = [v for v in out["players"].values() if v["grid"]]
    assert with_grid and all(len(v["grid"]) == 16 and len(v["grid"][0]) == 12 for v in with_grid)
    for v in with_grid:
        assert abs(sum(map(sum, v["grid"])) - v["eligible_s"]) <= 0.01 * v["eligible_s"] + 1e-6
    assert all(v["grid"] is None for v in out["players"].values() if v["eligible_s"] == 0)
    assert not os.path.exists(d / "render" / "heatmaps.json.tmp")
