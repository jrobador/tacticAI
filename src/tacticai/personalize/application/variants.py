"""The 18 text variants: personalize/variants/<lens>_<lang>_<club>.json. The Lens agent writes the neutral body of each insight and lens, the code adds the side; anything wrong falls back to the template of that insight."""
import json
import os

from ...core.files import write_atomic
from ...explain.domain import placeholders as P
from ..domain import templates
from ..domain.lenses import CLUBS, LANGS, TEXT_LENSES
from . import translator_agent

VARIANT_VERSION = 1


def variant_name(lens, lang, club):
    return f"{lens}_{lang}_{club}"


def body_errors(body, d, lang):
    if not isinstance(body, dict) or not all(isinstance(body.get(f), str) for f in ("title", "text")):
        return ["title and text must be strings"]
    return [e for f in ("title", "text") for e in P.validate_text(body[f], d["metrics"], d["claims"], lang)]


def valid_bodies(insights, got):
    """Lens output -> ({insight_id: {lens: {"title", "text"}}} with the bodies that pass validation, warnings). The rest falls back to the template."""
    ids = {d["insight_id"] for d in insights}
    warnings = [f"personalize: lens agent returned unknown insight id {iid}" for iid in got if iid not in ids]
    out = {}
    for d in insights:
        item = got.get(d["insight_id"])
        if item is None:
            continue
        for lens in TEXT_LENSES:
            body = item.get(lens) if isinstance(item, dict) else None
            errs = body_errors(body, d, "en")
            if errs:
                warnings.append(f"personalize: {d['insight_id']} {lens} agent text rejected ({'; '.join(errs)})")
            else:
                out.setdefault(d["insight_id"], {})[lens] = body
    return out, warnings


def valid_translations(insights, en, tr):
    """English bodies + translator output -> ({insight_id: {lens: {"title", "text"}}} in Spanish that pass validation, warnings). Same metrics as the original; the rest uses the Spanish template."""
    out, warnings = {}, []
    if not tr:
        return out, warnings
    for d in insights:
        for lens, body in en.get(d["insight_id"], {}).items():
            es = {f: tr.get(translator_agent.body_key(d["insight_id"], lens, f)) for f in ("title", "text")}
            errs = body_errors(es, d, "es")
            if not errs:
                errs = [f"{f} changes the placeholders" for f in es if not translator_agent.same_placeholders(body[f], es[f])]
            if errs:
                warnings.append(f"personalize: {d['insight_id']} {lens} translation rejected ({'; '.join(errs)})")
            else:
                out.setdefault(d["insight_id"], {})[lens] = es
    return out, warnings


def build_variant(insights, lens, lang, club, names, bodies=None):
    """-> variant dict. `bodies` = valid neutral bodies of `lang` ({insight_id: {lens: {"title", "text"}}}); the code adds the side. Every insight gets a text, whether or not it passes any lens threshold."""
    name, texts, sources = variant_name(lens, lang, club), {}, {}
    for d in insights:
        body = (bodies or {}).get(d["insight_id"], {}).get(lens)
        if body:
            title, text = templates.perspective_text(d, body["title"], body["text"], lens, lang, club)
            t = {"title": title, "text": text, "source": "agent"}
        else:
            title, text = templates.template(d, names, lens, lang, club)
            bad = [e for s in (title, text) for e in P.validate_text(s, d["metrics"], d["claims"], lang)]
            if bad:  # a template bug is a code error, not an LLM failure
                raise ValueError(f"template for {d['insight_id']} ({d['kind']}/{d['subtype']}) {name} invalid: {bad}")
            t = {"title": title, "text": text, "source": "template"}
        texts[d["insight_id"]] = t
        sources[t["source"]] = sources.get(t["source"], 0) + 1
    return {"variant_version": VARIANT_VERSION, "lens": lens, "lang": lang, "club": club, "texts": texts, "sources": sources}


def build_all(insights, names, bodies=None):
    """`bodies` = {lang: valid bodies}. -> {name: variant} for the 18 combinations."""
    return {variant_name(lens, lang, club): build_variant(insights, lens, lang, club, names, (bodies or {}).get(lang))
            for lens in TEXT_LENSES for lang in LANGS for club in CLUBS}


def write_all(match_dir, variants):
    d = os.path.join(match_dir, "personalize", "variants")
    os.makedirs(d, exist_ok=True)
    for name, v in variants.items():
        write_atomic(os.path.join(d, name + ".json"), json.dumps(v, ensure_ascii=False, indent=1))
