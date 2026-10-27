"""Personalize stage: <match>/explain/insights.jsonl -> <match>/personalize/variants/ (18) and recaps/ (18). Deterministic; agents only write text and any failure falls back to templates."""
import os

from ...explain.application.build_insights import build_match_context
from ...core.files import read_json, read_jsonl
from . import fan, lens_agent as lens_mod, recap_agent as recap_mod, recaps, studio, translator_agent as translator_mod, variants


def _ask(fn, what, fallback, warnings, *args):
    """One agent call; a failure becomes a warning and {}. NotImplementedError is the silent not-configured path."""
    try:
        got = fn(*args)
        if not isinstance(got, dict):
            raise TypeError(f"returned {type(got).__name__}, expected dict")
        return got
    except NotImplementedError:
        return {}
    except Exception as err:  # a failing LLM never fails the job
        warnings.append(f"personalize: {what} failed ({err}); {fallback}")
        return {}


def run(match_dir, lens_agent=None, recap_agent=None, translator=None, context=None, supporter_agent=None):
    """-> warnings (list of str) for the job message. `lens_agent` / `recap_agent` / `translator` are optional replacements of adapt_texts / write_recaps / translate (tests).
    Order: Lens call, Recap call, Translator call, then the 18 variants and 18 recaps are assembled and written; last, the fan view
    (facts detected by code, written by the Supporter agent). `supporter_agent` replaces supporter_agent.write (tests)."""
    insights = read_jsonl(os.path.join(match_dir, "explain", "insights.jsonl"))
    meta = read_json(os.path.join(match_dir, "meta.json"))
    names = {t: meta["teams"][t]["name"] for t in ("home", "away")}
    ctx = context if context is not None else build_match_context(match_dir)
    warnings = []
    en_bodies, w = variants.valid_bodies(insights, _ask(lens_agent or lens_mod.adapt_texts, "lens agent", "all texts from templates", warnings, insights, ctx))
    warnings += w
    picked = recaps.picks(insights)
    got = _ask(recap_agent or recap_mod.write_recaps, "recap agent", "recaps from templates", warnings, insights, picked, ctx) if picked else {}  # no moments, no call
    en_recaps, w = recaps.valid_recaps(insights, picked, got)
    warnings += w
    texts = {translator_mod.body_key(iid, lens, f): body[f] for iid, by_lens in en_bodies.items() for lens, body in by_lens.items() for f in ("title", "text")}
    texts.update({translator_mod.recap_key(combo): t for combo, t in en_recaps.items()})
    tr = _ask(translator or translator_mod.translate, "translator", "Spanish from templates", warnings, texts, ctx)
    es_bodies, w = variants.valid_translations(insights, en_bodies, tr)
    warnings += w
    es_recaps, w = recaps.valid_translations(insights, picked, en_recaps, tr)
    warnings += w
    vs = variants.build_all(insights, names, {"en": en_bodies, "es": es_bodies})
    rs = recaps.build_all(insights, vs, {"en": en_recaps, "es": es_recaps})
    variants.write_all(match_dir, vs)
    recaps.write_all(match_dir, rs)
    warnings += fan.run(match_dir, supporter_agent)
    warnings += studio.run(match_dir)
    return warnings
