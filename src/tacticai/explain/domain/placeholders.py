"""Placeholders: no LLM writes a number. Texts carry `{metric}` (or `{i003.metric}` in recaps) and the backend fills in the formatted value.
API (shared by Explain, Personalize, Director and Q&A):
    validate_text(text, metrics, claims, lang, insights=None) -> list[str]   # [] = valid; metrics = {name: {"value", "unit"}}; insights = {insight_id: metrics} for {iNNN.metric}
    resolve_text(text, metrics, insights=None, lang="en") -> str                       # raises KeyError on an unknown placeholder (validate first)
    fmt(metric, lang="en") -> str                                             # ints for counts, 1 decimal for s and %, 2 decimals for everything else; decimal comma for "es"
Plural form: `{lines_broken|line|lines}` resolves to the word only ("line" if the rounded value is 1, else "lines"); the number itself is a separate `{lines_broken}`. The words may not contain digits.
Rules: no digit outside a placeholder; no number word of `lang` outside a placeholder (articles un/una/a/an are fine); special claim words only if the claim is in `claims`."""
import re

PLACEHOLDER = re.compile(r"\{(?:(i\d{3})\.)?([a-z_][a-z0-9_]*)(?:\|([^|{}]+)\|([^|{}]+))?\}")
COUNT_UNITS = {"lines", "passes", "entries", "count"}
ONE_DECIMAL = {"s", "%"}

NUMBER_WORDS = {
    "en": "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
          "thirty forty fifty sixty seventy eighty ninety hundred".split(),
    "es": "cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete dieciocho diecinueve veinte "
          "treinta cuarenta cincuenta sesenta setenta ochenta noventa cien".split(),
}
CLAIM_WORDS = {
    "match_max": ["highest", "peak", "record", "más alta", "pico", "récord", "máximo"],
    "first_goal": ["first goal", "opener", "opening goal", "primer gol", "abrió el marcador"],
    "equaliser": ["equaliser", "equalizer", "empató", "igualó"],
    "go_ahead": ["go-ahead", "took the lead", "puso arriba", "pasó al frente"],
}


def mask_numbers(obj):
    """Copy of obj (dicts/lists/strings) with every number in its strings replaced by '#', so a model sees the meaning but has no digits to copy."""
    if isinstance(obj, str):
        return re.sub(r"-?\d+(?:[.,]\d+)?", "#", obj)
    if isinstance(obj, dict):
        return {k: mask_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_numbers(v) for v in obj]
    return obj


def fmt(metric, lang="en"):
    v, unit = metric["value"], metric["unit"]
    out = str(int(round(v))) if unit in COUNT_UNITS else f"{v:.1f}" if unit in ONE_DECIMAL else f"{v:.2f}"
    return out.replace(".", ",") if lang == "es" else out


def _lookup(m, metrics, insights):
    iid, name = m.group(1), m.group(2)
    src = (insights or {}).get(iid) if iid else metrics
    return None if src is None else src.get(name)


def validate_text(text, metrics, claims, lang, insights=None):
    if not isinstance(text, str) or not text.strip():
        return ["empty text"]
    errors = [f"unknown placeholder {m.group(0)}" for m in PLACEHOLDER.finditer(text) if _lookup(m, metrics, insights) is None]
    errors += [f"digit in plural form {m.group(0)}" for m in PLACEHOLDER.finditer(text) if m.group(3) and re.search(r"\d", m.group(3) + m.group(4))]
    rest = PLACEHOLDER.sub(" ", text)
    if "{" in rest or "}" in rest:
        errors.append("malformed placeholder")
    if re.search(r"\d", rest):
        errors.append("digit outside a placeholder")
    words = NUMBER_WORDS.get(lang)
    if words is None:
        errors.append(f"unknown lang {lang!r}")
    else:
        low = rest.lower()
        errors += [f"number word {w!r}" for w in words if re.search(rf"(?<!\w){w}(?!\w)", low)]
    low = rest.lower()
    for claim, ws in CLAIM_WORDS.items():
        if claim not in (claims or []):
            errors += [f"claim word {w!r} without claim {claim}" for w in ws if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low)]
    return errors


def resolve_text(text, metrics, insights=None, lang="en"):
    def one(m):
        v = _lookup(m, metrics, insights)
        if v is None:
            raise KeyError(m.group(0))
        if m.group(3):
            return m.group(3) if int(round(v["value"])) == 1 else m.group(4)
        return fmt(v, lang)
    return PLACEHOLDER.sub(one, text)
