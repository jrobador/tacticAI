from tacticai.ingest.domain.roster import build_roster


def test_build_roster():
    r = build_roster("Home FC", "HFC", [("Smith", "GK"), ("Jones", "CB")], "Away FC", "AFC", [("Lee", "GK")])
    assert r["left"] == {"team": "Home FC", "short": "HFC", "players": [
        {"index": 0, "name": "Smith", "role": "GK"}, {"index": 1, "name": "Jones", "role": "CB"}]}
    assert r["right"]["players"] == [{"index": 0, "name": "Lee", "role": "GK"}]
