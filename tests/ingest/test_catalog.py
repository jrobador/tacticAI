import pytest

from tacticai.ingest.domain import formations as f
from tacticai.ingest.domain.recipe import ROLES

NAMES = ["4-4-2", "4-3-3", "4-2-3-1", "4-1-4-1", "3-5-2", "3-4-3", "5-3-2", "5-4-1"]


def test_names():
    assert list(f.CATALOG) == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_formation(name):
    e = f.CATALOG[name]
    assert len(e) == 11 and f.roles(name).count("GK") == 1 and set(f.roles(name)) <= ROLES
    assert all(-1 <= x <= 1 and -1 <= y <= 1 for _, x, y in e)
    assert all(y > 0 for r, _, y in e if r in ("LB", "LM")) and all(y < 0 for r, _, y in e if r in ("RB", "RM"))
    assert len(f.shape_vector(name)) == 22
    assert all(p[0] <= 0 for p in f.kickoff_positions(e, False))
    k = f.kickoff_positions(e, True)
    assert all(p[0] <= 0 for p in k) and sum(p[0] == 0.0 for p in k) == 2
    assert k[0][0] == -1.0


def test_legacy_unchanged():
    assert f.choose(7) == ("4-3-3", "4-4-2", "right")
    assert f.build_team("4-4-2", True) == [
        [-1.0, 0, "GK"], [-0.42, -0.2, "LB"], [-0.5, -0.07, "CB"], [-0.5, 0.07, "CB"], [-0.42, 0.2, "RB"],
        [-0.18, -0.22, "LM"], [-0.25, -0.06, "CM"], [-0.25, 0.06, "CM"], [-0.18, 0.22, "RM"],
        [0.0, -0.02, "CF"], [0.0, 0.02, "CF"]]
    assert f.build_team("4-3-3", False) == [
        [-1.0, 0, "GK"], [-0.42, -0.2, "LB"], [-0.5, -0.07, "CB"], [-0.5, 0.07, "CB"], [-0.42, 0.2, "RB"],
        [-0.27, -0.1, "CM"], [-0.32, 0, "DM"], [-0.27, 0.1, "CM"], [-0.1, -0.22, "LM"],
        [-0.1, 0, "CF"], [-0.1, 0.22, "RM"]]
    assert f.build_team("4-3-3", True)[8:] == [[0.0, 0.02, "LM"], [0.0, -0.02, "CF"], [-0.05, 0.22, "RM"]]
