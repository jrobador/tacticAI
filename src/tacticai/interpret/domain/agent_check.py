"""Tactical agent validator: pure code, no LLM, no file reads. `check_tactical` returns the errors ([] = valid)."""
import re

from ...explain.domain.placeholders import NUMBER_WORDS

NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
MAX_PHASES, MAX_NOTES = 3, 5
_MISSING = object()


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def same(a, b):
    return _num(a) == _num(b) if _num(a) is not None and _num(b) is not None else a == b


def resolve(node, path):
    """Dotted path: dict keys, list indices as integers. _MISSING if it does not exist."""
    for k in str(path).split("."):
        if isinstance(node, dict) and k in node:
            node = node[k]
        elif isinstance(node, list) and k.isdigit() and int(k) < len(node):
            node = node[int(k)]
        else:
            return _MISSING
    return node


def _check_evidence(who, evidence, responses):
    errors = []
    for e in evidence:
        cid, path, value = e.get("call_id"), e.get("path"), e.get("value")
        resp = responses.get(cid)
        if resp is None:
            errors.append(f"{who}: unknown call_id {cid!r}")
        elif resp.get("sufficient_evidence") is False:
            errors.append(f"{who}: {cid} has sufficient_evidence false")
        else:
            got = resolve(resp, path)
            if got is _MISSING:
                errors.append(f"{who}: path {cid}:{path} does not exist")
            elif got is None:
                errors.append(f"{who}: {cid}:{path} is null")
            elif not same(got, value):
                errors.append(f"{who}: {cid}:{path} is {got!r}, not {value!r}")
    return errors


def _check_text(who, item, responses):
    text, evidence = item.get("text") or "", item.get("evidence") or []
    errors = _check_evidence(who, evidence, responses)
    values = [e.get("value") for e in evidence]
    for n in NUMBER.findall(text):
        if not any(_num(v) is not None and _num(v) == float(n) for v in values):
            errors.append(f"{who}: number {n} in text has no matching evidence")
    low = text.lower()
    errors += [f"{who}: number word {w!r}" for w in NUMBER_WORDS["en"] if re.search(rf"(?<!\w){w}(?!\w)", low)]
    return errors


def _seen(responses, key):
    """Every int `key` value that appears anywhere in a logged tool response."""
    out = set()

    def walk(n):
        if isinstance(n, dict):
            out.update(v for k, v in n.items() if k == key and isinstance(v, int))
            list(map(walk, n.values()))
        elif isinstance(n, list):
            list(map(walk, n))
    walk(list(responses.values()))
    return out


def _check_list(name, items, key, limit, size, responses):
    errors = [f"{name}: more than {limit} items"] if len(items) > limit else []
    seen, used = _seen(responses, key), set()
    for i, it in enumerate(items):
        who = f"{name}[{i}]"
        if not (isinstance(it.get(key), int) and 0 <= it[key] < size):
            errors.append(f"{who}: {key} {it.get(key)!r} out of range")
        elif it[key] not in seen:
            errors.append(f"{who}: {key} {it[key]!r} never appeared in a tool response")
        elif it[key] in used:
            errors.append(f"{who}: duplicate {key} {it[key]!r}")
        used.add(it.get(key))
        errors += _check_text(who, it, responses)
    if sorted(it.get("rank") for it in items) != list(range(1, len(items) + 1)):
        errors.append(f"{name}: ranks must be 1..{len(items)} without repeats")
    return errors


def check_tactical(tactical, log_entries, n_phases, n_notes):
    responses = {e["call_id"]: e["response"] for e in log_entries if e.get("call_id") and isinstance(e.get("response"), dict)}
    summary = tactical.get("summary") or {}
    errors = _check_list("phases", tactical.get("phases") or [], "candidate_id", MAX_PHASES, n_phases, responses)
    errors += _check_list("key_notes", tactical.get("key_notes") or [], "note_index", MAX_NOTES, n_notes, responses)
    if not str(summary.get("text") or "").strip():
        errors.append("summary: empty")
    return errors + _check_text("summary", summary, responses)


# ---- citations as placeholders: the model writes {c3:results.all.notes.items.1.evidence.xg}, the code writes the number and its evidence ----
PLACEHOLDER = re.compile(r"\{(c\d+:[^{}\s]+)\}")


def leaves(call_id, response):
    """Numeric leaves of a tool response as {"<call_id>:<dotted path>": value} (no bools, no nulls; nothing from sufficient_evidence false)."""
    out = {}
    if not isinstance(response, dict) or response.get("sufficient_evidence") is False:
        return out

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + [str(k)])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)])
        elif _num(node) is not None:
            out[f"{call_id}:{'.'.join(path)}"] = node
    walk(response, [])
    return out


def citable_text(cited):
    return "\n".join(f"{k} = {v}" for k, v in cited.items())


def resolve_text(text, cited):
    """(resolved text, evidence, errors): each {key} becomes the value as the tool returned it; no digit may remain outside placeholders."""
    evidence, errors = [], []

    def sub(m):
        key = m.group(1)
        if key not in cited:
            errors.append(f"unknown placeholder {{{key}}}")
            return m.group(0)
        call_id, path = key.split(":", 1)
        ev = {"call_id": call_id, "path": path, "value": cited[key]}
        if ev not in evidence:
            evidence.append(ev)
        return str(cited[key])
    text = text or ""
    out, rest = PLACEHOLDER.sub(sub, text), PLACEHOLDER.sub(" ", text)
    if re.search(r"\d", rest):
        errors.append("digit outside a placeholder")
    if "{" in rest or "}" in rest:
        errors.append("malformed placeholder")
    return out, evidence, errors
