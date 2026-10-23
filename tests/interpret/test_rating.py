from tacticai.interpret.domain.rating import rating

P = dict(role="CM", lines_broken=0, progressive_passes=0, xg=0.0, goals=0, tackles=0, interceptions=0, losses_own_half=0)


def test_gk_has_no_value():
    assert rating({**P, "role": "GK", "tackles": 5}) == {"value": None, "breakdown": [], "reason": "saves_not_validated"}


def test_breakdown_omits_zeros_and_sums():
    r = rating({**P, "lines_broken": 9, "xg": 0.27, "goals": 1, "losses_own_half": 2})
    assert [b["item"] for b in r["breakdown"]] == ["lines_broken", "xg", "goals_minus_xg", "losses_own_half"]
    assert r["value"] == 7.5 and r["reason"] is None and r["breakdown"][0] == {"item": "lines_broken", "count": 9, "points": 0.9}


def test_clamp_and_no_xg():
    assert rating({**P, "tackles": 100})["value"] == 10.0 and rating({**P, "losses_own_half": 100})["value"] == 1.0
    r = rating({**P, "xg": None, "goals": 1, "tackles": 1})
    assert [b["item"] for b in r["breakdown"]] == ["tackles"] and r["value"] == 6.2
