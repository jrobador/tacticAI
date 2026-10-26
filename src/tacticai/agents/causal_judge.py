"""Causal judge: one Foundry call that rejects texts claiming causality or intention the data does not show. Fails closed; never raises."""
import json
import os
from typing import Literal

from pydantic import BaseModel

from . import foundry

INSTRUCTIONS = """You judge football texts for causality only. Each text comes with the data that backs it. Judge every text by id.

Accept (verdict "ok"):
- Statements of importance or significance of a moment ("it matters", "decisive", "significant", "important", "at a decisive stage"). Explaining why a moment matters by its timing, rarity or the score at stake is allowed ("it matters because it came at a decisive stage of the match").
- Scoreboard consequences that follow from the rules of football: a goal puts a team ahead, levels the score, extends or cuts a lead ("giving them the lead", "to take the lead", "go-ahead goal", "equaliser").
- A temporal sequence the data shows ("then", "followed by", "ended in", "during", "while", "later").

Reject:
- Claims that one action or phase produced, created, caused, forced, enabled or resulted in another ("led to", "produced", "created the chance", "caused", "forced", "resulted in", "culminated in", "set the tone", "which allowed", "thanks to", "as a result", "responded with/to").
- Attributed intentions ("trying to", "in an attempt to", "aiming to").
- Speculative effects ("potentially affecting", "may have unsettled").
- A sequence the data does not show.
When in doubt between causal and temporal, reject.
Judge only causality and sequence, not style or numbers.

For every text return its id, verdict "ok" or "reject", the exact quote that is the problem (empty for ok) and a short reason (empty for ok). Return every id exactly once."""


class Verdict(BaseModel):
    id: str
    verdict: Literal["ok", "reject"]
    quote: str
    reason: str


class Out(BaseModel):
    items: list[Verdict]


def judge(items, data, timeout_s=60) -> dict[str, str]:
    """items: [{"id", "text"}]; data: the JSON backing them. -> {id: reason} for the rejected ids ({} = all ok)."""
    if not items or not foundry.configured():
        return {}
    ids = [i["id"] for i in items]
    try:
        out = foundry.run(INSTRUCTIONS, json.dumps({"data": data, "texts": items}, ensure_ascii=False, default=str), response_format=Out,
                          timeout_s=timeout_s, max_output_tokens=1500, deployment=os.environ.get("FOUNDRY_JUDGE_DEPLOYMENT") or None)
    except Exception as e:  # fail closed
        return {i: f"causal judge failed: {type(e).__name__}: {e}" for i in ids}
    by = {v.id: v for v in out.items}
    return {i: "no verdict" if i not in by else f"{by[i].quote!r}: {by[i].reason}" for i in ids if i not in by or by[i].verdict == "reject"}
