from tacticai.ingest.domain.styles import DEFAULT_TACTICS, STYLES, TACTIC_KEYS, tactics_for


def test_styles():
    assert len(TACTIC_KEYS) == 12 and set(STYLES) == {"balanced", "high_press", "counter", "possession"}
    for name, v in STYLES.items():
        assert len(v) == 12 and all(0 <= x <= 1 for x in v), name
    assert STYLES["balanced"] == DEFAULT_TACTICS
    assert STYLES["counter"][TACTIC_KEYS.index("position_defense_depth_factor")] == 1.0
    tactics_for("balanced").append(1)
    assert len(tactics_for("balanced")) == 12
