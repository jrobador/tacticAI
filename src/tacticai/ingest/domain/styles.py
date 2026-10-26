"""Tactic style presets. Values are plain data; the engine adapter passes them in TACTIC_KEYS order."""

TACTIC_KEYS = [
    "dribble_centermagnet", "dribble_offensiveness",
    "position_defense_depth_factor", "position_defense_microfocus_strength", "position_defense_midfieldfocus",
    "position_defense_sidefocus_strength", "position_defense_width_factor",
    "position_offense_depth_factor", "position_offense_microfocus_strength", "position_offense_midfieldfocus",
    "position_offense_sidefocus_strength", "position_offense_width_factor",
]
DEFAULT_TACTICS = [0.72, 0.50, 0.30, 0.96, 0.96, 0.16, 0.70, 0.34, 0.92, 0.88, 0.88, 0.74]

# Depth factors are inverted in the engine: 1.0 = deeper line (measured).
_OVERRIDES = {
    "balanced": {},
    "high_press": dict(position_defense_depth_factor=0.0, position_defense_width_factor=0.45,
                       position_defense_midfieldfocus=1.0, position_offense_depth_factor=0.2,
                       dribble_offensiveness=0.7),
    "counter": dict(position_defense_depth_factor=1.0, position_defense_width_factor=0.5,
                    position_offense_depth_factor=0.0, position_offense_width_factor=0.6,
                    dribble_offensiveness=0.9),
    "possession": dict(position_defense_depth_factor=0.6, position_offense_width_factor=1.0,
                       position_offense_depth_factor=0.5, position_offense_midfieldfocus=1.0,
                       dribble_offensiveness=0.2),
}


def _style(over):
    d = dict(zip(TACTIC_KEYS, DEFAULT_TACTICS))
    d.update(over)
    return [d[k] for k in TACTIC_KEYS]


STYLES = {name: _style(over) for name, over in _OVERRIDES.items()}


def tactics_for(style):
    return list(STYLES[style])
