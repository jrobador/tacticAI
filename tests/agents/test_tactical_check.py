import copy

from tacticai.interpret.domain.agent_check import check_tactical

LOG = [
    {"call_id": "c1", "tool": "match_context", "args": {}, "response": {"sufficient_evidence": True, "results": {"home": {"block_height": {"percentile": 88, "value": 0.587}}, "list": [4, 5]}}},
    {"call_id": "c2", "tool": "pressing_profile", "args": {}, "response": {"sufficient_evidence": False, "results": {"home": {"pressure": 0.4}}}},
    {"call_id": "c3", "tool": "possession_analysis", "args": {}, "response": {"results": {"home": {"phase_candidates": {"items": [{"candidate_id": 0}, {"candidate_id": 1}]},
                                                                                     "notes": {"items": [{"note_index": 0}, {"note_index": 1}]}}}}},
]


def ev(path="results.home.block_height.value", value=0.587, call_id="c1"):
    return {"call_id": call_id, "path": path, "value": value}


def good():
    return {"phases": [{"candidate_id": 0, "rank": 1, "text": "Home held a block height of 0.587 m.", "evidence": [ev()]},
                       {"candidate_id": 1, "rank": 2, "text": "A 88 percentile spell.", "evidence": [ev("results.home.block_height.percentile", 88)]}],
            "key_notes": [{"note_index": 0, "rank": 1, "text": "Second list item 5.", "evidence": [ev("results.list.1", 5)]}],
            "summary": {"text": "Home pushed up.", "evidence": []}}


def errors(mutate):
    t = good()
    mutate(t)
    return check_tactical(t, LOG, n_phases=2, n_notes=3)


def test_valid():
    assert check_tactical(good(), LOG, 2, 3) == []


def test_value_not_matching_log():
    assert errors(lambda t: t["phases"][0]["evidence"][0].update(value=0.59) or t["phases"][0].update(text="Block 0.59 m."))


def test_nonexistent_path():
    assert errors(lambda t: t["phases"][0]["evidence"][0].update(path="results.away.block_height.value"))
    assert errors(lambda t: t["key_notes"][0]["evidence"][0].update(path="results.list.7"))


def test_invented_call_id():
    assert errors(lambda t: t["phases"][0]["evidence"][0].update(call_id="c9"))


def test_repeated_rank():
    assert errors(lambda t: t["phases"][1].update(rank=1))


def test_number_word():
    assert errors(lambda t: t["summary"].update(text="Home made two runs."))


def test_number_in_text_without_evidence():
    assert errors(lambda t: t["summary"].update(text="Home pressed 62% of the time."))


def test_insufficient_evidence_response():
    assert errors(lambda t: t["summary"].update(text="Pressure 0.4.", evidence=[ev("results.home.pressure", 0.4, "c2")]))


def test_out_of_range_ids():
    assert errors(lambda t: t["phases"][0].update(candidate_id=2))
    assert errors(lambda t: t["key_notes"][0].update(note_index=3))


def test_limits_and_summary():
    assert errors(lambda t: t["summary"].update(text=" "))
    assert errors(lambda t: t.update(key_notes=[dict(copy.deepcopy(t["key_notes"][0]), rank=i + 1) for i in range(6)]))


def test_leaves_and_resolve():
    from tacticai.interpret.domain.agent_check import leaves, resolve_text
    cited = leaves("c1", LOG[0]["response"])
    assert cited["c1:results.home.block_height.value"] == 0.587 and cited["c1:results.list.1"] == 5 and "c1:sufficient_evidence" not in cited
    assert leaves("c2", LOG[1]["response"]) == {}
    text, evidence, errors = resolve_text("Block {c1:results.home.block_height.value} and {c1:results.home.block_height.value}.", cited)
    assert text == "Block 0.587 and 0.587." and evidence == [ev()] and errors == []
    assert resolve_text("Bad {c1:results.nope}.", cited)[2] == ["unknown placeholder {c1:results.nope}"]
    assert resolve_text("Has 5 digits.", cited)[2] == ["digit outside a placeholder"]


def test_unseen_note_index_in_range_is_rejected():
    assert any("key_notes[0]" in e for e in errors(lambda t: t["key_notes"][0].update(note_index=2)))


def test_duplicate_candidate_and_note_rejected():
    assert any("phases[1]" in e and "duplicate" in e for e in errors(lambda t: t["phases"][1].update(candidate_id=0)))
    assert any("key_notes[1]" in e and "duplicate" in e for e in errors(
        lambda t: t["key_notes"].append({"note_index": 0, "rank": 2, "text": "Again.", "evidence": []})))
