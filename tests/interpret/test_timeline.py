from tacticai.interpret.domain.timeline import timeline

H, A = ("home", "home-01"), ("away", "away-01")
META = {"pitch": {"length_m": 108.0, "width_m": 70.0}}


def rows_of(n, bx=lambda i: 0.0, gap_at=None):
    f = 0
    out = []
    for i in range(n):
        f += 11 if i == gap_at else 1
        out.append({"frame_index": f, "t_s": f / 10, "clock_s": 100 + f / 10, "period": 1, "camera": "main", "game_state": "open_play",
                    "score": {"home": 0, "away": 0}, "ball": {"x": bx(i)}, "players": []})
    return out


def test_windows_cover_all_open_play():
    rows = rows_of(100, gap_at=40)
    w = timeline(rows, [H] * 100, [], META)
    assert [x["window"] for x in w] == list(range(18))
    assert w[0]["start_t_s"] == rows[0]["t_s"] and w[-1]["end_t_s"] == rows[-1]["t_s"]
    assert all(a["end_t_s"] <= b["start_t_s"] for a, b in zip(w, w[1:]))


def test_momentum_sign_smoothing_and_entries():
    n = 36  # 2 rows per window
    rows = rows_of(n, bx=lambda i: 40.0 if i == 20 else 0.0)  # ball crosses 108/6 = 18 m at row 20, owner home
    ev = [{"type": "shot", "team": "home", "t_s": rows[20]["t_s"]}]
    own = [H if i < 24 else A for i in range(n)]
    w = timeline(rows, own, ev, META, {0: 0.5})
    k = next(i for i, x in enumerate(w) if x["home"]["xg"])
    assert w[k]["home"]["xg"] == 0.5 and sum(x["home"]["final_third_entries"] for x in w) == 1
    assert w[0]["momentum"] > 0 and w[-1]["momentum"] < 0 and all(-1 <= x["momentum"] <= 1 for x in w)
    assert w[0]["home"]["xg"] is None and w[0]["home"]["possession_share"] == 1.0 and w[-1]["away"]["possession_share"] == 1.0
    assert timeline(rows, own, ev, META)[k]["home"]["xg"] is None


def test_xg_is_null_without_shots_or_model():  # review #1
    rows = rows_of(36, bx=lambda i: 40.0 if i == 20 else 0.0)
    own = [H for _ in range(36)]
    shot = {"type": "shot", "team": "home", "t_s": rows[20]["t_s"]}
    none = timeline(rows, own, [], META, {})  # model present, no shots
    assert all(w[t]["xg"] is None for w in none for t in ("home", "away"))
    unscored = timeline(rows, own, [shot], META, {})  # a shot the model did not score
    assert all(w["home"]["xg"] is None for w in unscored)
    scored = timeline(rows, own, [shot], META, {0: 0.0})  # a real xG of 0.0 stays 0.0
    assert [w["home"]["xg"] for w in scored if w["home"]["xg"] is not None] == [0.0] and all(w["away"]["xg"] is None for w in scored)
