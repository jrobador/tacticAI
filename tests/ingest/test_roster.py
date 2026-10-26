from tacticai.ingest.domain.roster import build_roster, shirt_numbers
from tacticai.ingest.domain.formations import CATALOG, roles


def test_build_roster():
    teams, r = build_roster("Home FC", "HFC", [("Smith", "GK"), ("Jones", "CB")], "Away FC", "AFC", [("Lee", "GK")])
    assert teams == {"home": {"name": "Home FC", "short": "HFC"}, "away": {"name": "Away FC", "short": "AFC"}}
    assert r == {"players": [
        {"player_id": "home-00", "team": "home", "name": "Smith", "number": 1, "role": "GK"},
        {"player_id": "home-01", "team": "home", "name": "Jones", "number": 5, "role": "CB"},
        {"player_id": "away-00", "team": "away", "name": "Lee", "number": 1, "role": "GK"}]}


def test_shirt_numbers_every_formation():
    for name in CATALOG:
        n = shirt_numbers(roles(name))
        assert len(set(n)) == 11 and n[roles(name).index("GK")] == 1, name


def test_shirt_numbers_explicit():
    assert shirt_numbers(roles("4-4-2")) == [1, 3, 5, 4, 2, 11, 8, 10, 7, 9, 19]
    assert shirt_numbers(roles("3-5-2")) == [1, 5, 4, 6, 3, 8, 16, 10, 2, 9, 19]
