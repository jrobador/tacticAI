"""The 18 recaps: personalize/recaps/<lens>_<lang>_<club>.json. The code picks the moments; the Recap agent (or the template) writes the text, stored with its numbers resolved."""
import json
import os

from ...core.files import write_atomic
from ...explain.domain import placeholders as P
from ..domain.lenses import CLUBS, LANGS, LENSES, TEXT_LENSES, priority
from . import translator_agent
from .variants import variant_name

RECAP_VERSION = 1
MAX_MOMENTS = 5
NO_MOMENTS = {"en": "No key moments in this clip", "es": "No hay momentos clave en este clip"}


def pick_moments(insights, lens, club):
    """Candidates are the insights whose priority (importance + club bonus, no player bonus) reaches the lens threshold (n = their count).
    The best min(5, n) by priority, ties by show_t_s then insight_id; returned in playing order."""
    ranked = sorted(((priority(d, club), d) for d in insights if priority(d, club) >= LENSES[lens]["threshold"]), key=lambda x: (-x[0], x[1]["show_t_s"], x[1]["insight_id"]))
    return [d["insight_id"] for d in sorted((d for _, d in ranked[:MAX_MOMENTS]), key=lambda d: (d["show_t_s"], d["insight_id"]))]


def picks(insights):
    """{"<lens>_<club>": ids} for the combinations with moments (they do not depend on the language)."""
    out = {f"{lens}_{club}": pick_moments(insights, lens, club) for lens in TEXT_LENSES for club in CLUBS}
    return {k: ids for k, ids in out.items() if ids}


def _sentence(s):
    s = s.strip()
    return s if s[-1:] in ".!?" else s + "."


def text_errors(text, ids, by_id, lang):
    return P.validate_text(text, {}, [c for i in ids for c in by_id[i]["claims"]], lang, {i: by_id[i]["metrics"] for i in ids})


def valid_recaps(insights, picked, got):
    """Recap agent output -> ({combo: English text} that passes validation, warnings)."""
    by_id, out, warnings = {d["insight_id"]: d for d in insights}, {}, []
    if not got:
        return out, warnings
    for combo, ids in picked.items():
        errs = text_errors(got[combo], ids, by_id, "en") if isinstance(got.get(combo), str) else ["missing or not a string"]
        if errs:
            warnings.append(f"personalize: recap {combo} agent text rejected ({'; '.join(errs)})")
        else:
            out[combo] = got[combo]
    return out, warnings


def valid_translations(insights, picked, en, tr):
    """-> ({combo: Spanish text} that passes validation and keeps the placeholders of its English original, warnings)."""
    by_id, out, warnings = {d["insight_id"]: d for d in insights}, {}, []
    if not tr:
        return out, warnings
    for combo, text in en.items():
        es = tr.get(translator_agent.recap_key(combo))
        errs = text_errors(es, picked[combo], by_id, "es") if isinstance(es, str) else ["missing or not a string"]
        if not errs and not translator_agent.same_placeholders(text, es):
            errs = ["changes the placeholders"]
        if errs:
            warnings.append(f"personalize: recap {combo} translation rejected ({'; '.join(errs)})")
        else:
            out[combo] = es
    return out, warnings


def build_recap(insights, variant, lens, lang, club, text=None):
    """`text` = a validated recap with {iNNN.metric} placeholders, or None for the template (the titles of the variant). -> recap dict, stored with its numbers resolved."""
    ids = pick_moments(insights, lens, club)
    by_id = {d["insight_id"]: d for d in insights}
    source = "template"
    if not ids:
        text = NO_MOMENTS[lang]
    elif text is not None:
        text, source = P.resolve_text(text, {}, {i: by_id[i]["metrics"] for i in ids}, lang), "agent"
    else:
        text = " ".join(_sentence(P.resolve_text(variant["texts"][i]["title"], by_id[i]["metrics"], lang=lang)) for i in ids)
    return {"recap_version": RECAP_VERSION, "lens": lens, "lang": lang, "club": club, "insight_ids": ids, "text": text, "source": source}


def build_all(insights, variants, texts=None):
    """`texts` = {lang: {combo: validated text}}. -> {name: recap} for the 18 combinations."""
    return {variant_name(lens, lang, club): build_recap(insights, variants[variant_name(lens, lang, club)], lens, lang, club, (texts or {}).get(lang, {}).get(f"{lens}_{club}"))
            for lens in TEXT_LENSES for lang in LANGS for club in CLUBS}


def write_all(match_dir, recaps):
    d = os.path.join(match_dir, "personalize", "recaps")
    os.makedirs(d, exist_ok=True)
    for name, r in recaps.items():
        write_atomic(os.path.join(d, name + ".json"), json.dumps(r, ensure_ascii=False, indent=1))
