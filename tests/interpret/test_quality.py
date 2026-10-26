from tacticai.interpret.domain.quality import quality

META = {"source": {"camera_setup": "broadcast"}, "video": {"frames": 99}}


def rows_of(cam="main", obs=True, conf=1.0, jump=0.0):
    return [{"frame_index": f, "camera": cam, "ball": {"observed": True, "confidence": conf},
             "players": [{"player_id": "home-01", "x": f * jump, "y": 0.0, "on_pitch": True, "observed": obs, "confidence": conf}]} for f in (1, 2, 4)]


def test_levels_and_notes():
    q = quality(rows_of(), META)
    assert (q["level"], q["notes"], q["gaps"], q["tracking_lines"], q["video_frames"], q["camera_setup"]) == ("high", [], 1, 3, 99, "broadcast")
    assert quality(rows_of(conf=0.7), META)["level"] == "medium"
    low = quality(rows_of(cam="replay"), META)
    assert low["level"] == "low" and low["notes"] and low["main_camera_share"] == 0.0


def test_swap_proxy():
    assert quality(rows_of(jump=5.0), META)["identity_swaps_suspected"] == 1  # frames 1 to 2 are consecutive, 2 to 4 is a gap
