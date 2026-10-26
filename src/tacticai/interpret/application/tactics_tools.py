"""Tactical tools for the tactical agent: deterministic questions over a match loaded once (`load_match`), as methods of `Tactics`.
Common parameters: team (None = both), from_t_s, until_t_s, period, score_state (from the team's point of view). Common response: from_t_s, until_t_s, parameters, thresholds_used, sample,
sufficient_evidence, limitations, evidence, results. Results are keyed by team. A missing value is null with a reason, never 0. Errors are {"error": ..., "valid": [...]}.
sample is flat for one team and {home, away} for both. Phase = own / opp (stable owner of that row) or loose; loose rows are never possession. Intervals are half-open [from_t_s, until_t_s) (closed at the end of the clip); steps, episodes and candidates are integrated by their intersection with the query and carry covered_s. Retrospective: the finished match is analysed, no causality."""
import os
from bisect import bisect_left, bisect_right

from ...core.files import read_json, read_jsonl
from ..domain import pressure as P, relative as R, shape as S, transitions as T
from ..domain.frame import opponent, x_att
from ..domain.physical import is_open

SCORE_STATES = ("all", "leading", "drawing", "trailing")
SHAPE_METRICS = ("block_height", "defensive_line", "length", "width", "occupation", "block_band")
PRESS_METRICS = ("pressure", "pressures", "high_press", "recoveries", "high_regains", "press_outcomes", "ppda_proxy")
POSSESSION_METRICS = ("possessions", "build_up", "attacking_transitions", "defensive_transitions", "counters", "phase_candidates")
EVIDENCE_KINDS = ("notes", "events", "sequences", "windows")
PLAYER_METRICS = ("rating",)
MIXED = {"n_windows": 0, "sufficient": False, "reason": "mixed_phases"}  # no single possession phase selected: no reference, no band
# compare_metrics ids -> (tool, kwargs, path under results[team], unit)
COMPARE = {
    "block_height": ("team_shape", {"metrics": ["block_height"]}, ("block_height", "value"), "m"),
    "defensive_line": ("team_shape", {"metrics": ["defensive_line"]}, ("defensive_line", "value"), "m"),
    "length": ("team_shape", {"metrics": ["length"]}, ("length", "value"), "m"),
    "width": ("team_shape", {"metrics": ["width"]}, ("width", "value"), "m"),
    "pressure": ("pressing_profile", {"metrics": ["pressure"]}, ("pressure", "value"), "0-1"),
    "pressures_per_min": ("pressing_profile", {"metrics": ["pressures"]}, ("pressures", "per_min"), "per min of rival possession"),
    "high_press_s": ("pressing_profile", {"metrics": ["high_press"]}, ("high_press", "total_s"), "s"),
    "high_regains": ("pressing_profile", {"metrics": ["high_regains"]}, ("high_regains", "count"), "count"),
    "recoveries_total": ("pressing_profile", {"metrics": ["recoveries"]}, ("recoveries", "total"), "count"),
    "press_recovery_rate": ("pressing_profile", {"metrics": ["press_outcomes"]}, ("press_outcomes", "rate"), "share"),
    "ppda_proxy": ("pressing_profile", {"metrics": ["ppda_proxy"]}, ("ppda_proxy", "value"), "approx. PPDA"),
    "possession_pct": ("match_context", {}, ("possession_pct", "value"), "%"),
    "shots": ("match_context", {}, ("shots",), "count"),
    "xg": ("match_context", {}, ("xg", "value"), "engine xG"),
}
POINT_UNITS = ("%",)
BASE_LIMITS = ["retrospective analysis of the finished match: associations in time, not causes"]


def _opt(path, read, dflt):
    return read(path) if os.path.exists(path) else dflt


def load_match(match_dir):
    """Reads the match package and its analysis package once (tracking included); owners are the stable owners used by analyze."""
    from ..domain.pressure import owners_for
    i = lambda f: os.path.join(match_dir, "interpret", f)
    rows = read_jsonl(os.path.join(match_dir, "tracking.jsonl"))
    return {"id": read_json(i("meta.json"))["match_id"], "meta": read_json(os.path.join(match_dir, "meta.json")), "analysis": read_json(i("meta.json")),
            "roster": {p["player_id"]: p for p in _opt(os.path.join(match_dir, "roster.json"), read_json, {"players": []})["players"]},
            "rows": rows, "owners": owners_for(rows), "events": read_jsonl(i("events_enriched.jsonl")), "sequences": read_jsonl(i("sequences.jsonl")),
            "timeline": read_jsonl(i("timeline.jsonl")), "players": read_json(i("players.json"))["players"], "quality": read_json(i("quality.json")),
            "notes": _opt(i("tactical_notes.jsonl"), read_jsonl, []), "phases": _opt(i("phases.jsonl"), read_jsonl, None)}


def _err(msg, valid=None, **kw):
    return {"error": msg, **({"valid": valid} if valid is not None else {}), **kw}


def _dig(node, path):
    for k in path:
        node = node.get(k) if isinstance(node, dict) else None
    return node


class Tactics:
    def __init__(self, m):
        self.m, self.rows, self.owners, self.events, self.seqs = m, m["rows"], m["owners"], m["events"], m["sequences"]
        self.length, self.width = m["meta"]["pitch"]["length_m"], m["meta"]["pitch"]["width_m"]
        self.durs, self.ts = R.durations(self.rows), [r["t_s"] for r in self.rows]
        self.idx = {r["frame_index"]: i for i, r in enumerate(self.rows)}
        self.end_t = self.ts[-1] if self.ts else 0.0
        self.st = R.step(self.rows)
        self._c = {}

    # ---- shared helpers -------------------------------------------------------------------------------------------------------------------------------------------------------------

    def _cached(self, key, fn):
        if key not in self._c:
            self._c[key] = fn()
        return self._c[key]

    def _ms(self, t):
        return self._cached(("ms", t), lambda: [S.row_metrics(r, t, self.length) if is_open(r) else None for r in self.rows])

    def _phs(self, t):
        return self._cached(("phs", t), lambda: R.phases(self.rows, self.owners, t))

    def _pres(self, t):
        return self._cached(("pres", t), lambda: P.pressure_series(self.rows, self.owners, t))

    def _series(self, t, metric):
        return {i: m[metric] for i, m in enumerate(self._ms(t)) if m}

    def _F(self, team, from_t_s, until_t_s, period, score_state):
        if team not in (None, "home", "away"):
            return _err(f"unknown team '{team}'", ["home", "away"])
        if score_state not in SCORE_STATES:
            return _err(f"unknown score_state '{score_state}'", list(SCORE_STATES))
        return {"team": team, "from_t_s": from_t_s, "until_t_s": self.end_t if until_t_s is None else until_t_s, "period": period, "score_state": score_state}

    def _teams(self, F):
        return [F["team"]] if F["team"] else ["home", "away"]

    def _state_ok(self, score, team, state):
        d = score[team] - score[opponent(team)]
        return state == "all" or (state == "leading" and d > 0) or (state == "drawing" and d == 0) or (state == "trailing" and d < 0)

    def _in(self, t, F):
        """True when the instant t is in the half-open interval [from, until) (closed at the end of the clip)."""
        return F["from_t_s"] <= t < F["until_t_s"] or (t == F["until_t_s"] and F["until_t_s"] >= self.end_t)

    def _touch(self, a, b, F):
        """True when the item [a, b] intersects the query (half-open; a zero-length item counts at an instant inside it)."""
        return (a < F["until_t_s"] or (a == F["until_t_s"] and F["until_t_s"] >= self.end_t)) and (b > F["from_t_s"] or (a == b and b >= F["from_t_s"]))

    def _row_ok(self, r, team, F):
        return (F["period"] is None or r["period"] == F["period"]) and self._state_ok(r["score"], team, F["score_state"])

    def _ok_t(self, t, team, F):
        """True when instant t is inside the interval and its row matches period and score state."""
        return self._in(t, F) and self._row_ok(self.rows[max(0, bisect_right(self.ts, t) - 1)], team, F)

    def _ovl(self, i, F):
        """Seconds of step i (row i until the next consecutive open frame) inside the query."""
        return max(0.0, min(self.ts[i] + self.durs[i], F["until_t_s"]) - max(self.ts[i], F["from_t_s"]))

    def _eligible(self, team, F):
        """Row indices whose step intersects the query, in open play, matching period and score state."""
        lo, hi = max(0, bisect_left(self.ts, F["from_t_s"]) - 1), bisect_left(self.ts, F["until_t_s"])
        return [i for i in range(lo, min(len(self.rows), hi + 1)) if self.durs[i] > 0 and self._ovl(i, F) > 0 and self._row_ok(self.rows[i], team, F)]

    def _elig_any(self, teams, F):
        return sorted(set().union(*(self._eligible(t, F) for t in teams)))

    def _cov(self, elig, t0, t1, F):
        """Eligible seconds inside [t0, t1] and the query (elig = sorted eligible row indices)."""
        a, b = max(t0, F["from_t_s"]), min(t1, F["until_t_s"])
        if b <= a:
            return 0.0
        tot = 0.0
        for i in elig[bisect_left(elig, a - 1.0, key=lambda i: self.ts[i]):]:
            if self.ts[i] >= b:
                break
            tot += max(0.0, min(self.ts[i] + self.durs[i], b) - max(self.ts[i], a))
        return tot

    def _pick(self, items, k0, k1, F, elig, extra=0.0):
        """[(item, covered_s)] of the items whose [k0, k1 + extra] holds eligible time inside the query (selected by overlap, never by their start)."""
        got = [(x, self._cov(elig, x[k0], x[k1] + extra, F)) for x in items]
        return [(x, c) for x, c in got if c > 0]

    def _sample(self, team, F, elig):
        s = {"eligible_s": 0.0, "owned_s": 0.0, "opponent_owned_s": 0.0, "loose_s": 0.0}
        for i in elig:
            o, d = self.owners[i], self._ovl(i, F)
            s["eligible_s"] += d
            s["loose_s" if o is None else "owned_s" if o[0] == team else "opponent_owned_s"] += d
        return {**s, "n_events": sum(e["team"] == team and self._ok_t(e["t_s"], team, F) for e in self.events)}

    def _runs(self, elig, cap=20):
        """[[first_frame, last_frame]] of the maximal runs of eligible consecutive rows (capped)."""
        out = []
        for i in elig:
            if out and i == out[-1][1] + 1:
                out[-1][1] = i
            else:
                out.append([i, i])
        return [[self.rows[a]["frame_index"], self.rows[b]["frame_index"]] for a, b in out[:cap]]

    def _windows_in(self, F):
        return [w["window"] for w in self.m["timeline"] if self._touch(w["start_t_s"], w["end_t_s"], F) and (F["period"] is None or w["period"] == F["period"])]

    def _evidence(self, F, events=(), seqs=(), ranges=(), elig=()):
        return {"event_indices": sorted(set(events)), "sequence_ids": sorted(set(seqs)), "timeline_windows": self._windows_in(F),
                "frame_ranges": [list(r) for r in ranges] or self._runs(sorted(elig))}

    def _out(self, F, params, teams, results, samples, thresholds, limits, evidence, sufficient, extra_results=None):
        sample = samples[teams[0]] if len(teams) == 1 else {t: samples[t] for t in teams}
        lim = BASE_LIMITS + limits + (["no eligible open-play time in the interval"] if all(s["eligible_s"] == 0 for s in samples.values()) else [])
        return R.rounded({"from_t_s": F["from_t_s"], "until_t_s": F["until_t_s"], "parameters": {**{k: F[k] for k in ("team", "from_t_s", "until_t_s", "period", "score_state")}, **params},
                          "thresholds_used": thresholds, "sample": sample, "sufficient_evidence": bool(sufficient), "limitations": lim, "evidence": evidence,
                          "results": {**(extra_results or {}), **results}})

    # ---- 1. match_context -----------------------------------------------------------------------------------------------------------------------------------------------------------

    def match_context(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all"):
        """Score (goals without a shot included), effective time, possession, shots and engine xG with model coverage, quality, calibration and available metrics."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        teams, res, samples, ev_idx, sufficient = self._teams(F), {}, {}, [], True
        rng = [r for r in self.rows if self._in(r["t_s"], F) and (period is None or r["period"] == period)]
        models = self.m["analysis"]["models"]
        for t in teams:
            elig = self._eligible(t, F)
            samples[t] = s = self._sample(t, F, elig)
            held = s["owned_s"] + s["opponent_owned_s"]
            shots = [(j, e) for j, e in enumerate(self.events) if e["type"] == "shot" and e["team"] == t and self._ok_t(e["t_s"], t, F)]
            with_xg = [e["xg"] for _, e in shots if e.get("xg") is not None]
            ev_idx += [j for j, _ in shots]
            xg = ({"value": None, "reason": "no_shots", "shots": 0, "shots_with_xg": 0} if not shots else
                  {"value": None, "reason": "no_model", "shots": len(shots), "shots_with_xg": 0} if models["xg"] is None else
                  {"value": sum(with_xg) if with_xg else None, "reason": None if len(with_xg) == len(shots) else "some_shots_without_xg" if with_xg else "no_shot_matched_a_kick_candidate",
                   "shots": len(shots), "shots_with_xg": len(with_xg)})
            res[t] = {"possession_pct": {"value": 100 * s["owned_s"] / held if held else None, "reason": None if held else "no_owned_time"},
                      "shots": len(shots), "xg": xg, "goals_by_shot": sum(e["outcome"] == "goal" for _, e in shots)}
            sufficient = sufficient and s["eligible_s"] > 0
        goals = [j for j, e in enumerate(self.events) if e["type"] == "goal" and self._ok_t(e["t_s"], teams[0], {**F, "score_state": "all"})]
        ev_idx += goals
        match = {"score": rng[-1]["score"] if rng else None, "score_at_start": rng[0]["score"] if rng else None, "score_reason": None if rng else "no rows in the interval",
                 "effective_time_s": samples[teams[0]]["eligible_s"] if len(teams) == 1 or score_state == "all" else {t: samples[t]["eligible_s"] for t in teams},
                 "quality": {"level": self.m["quality"]["level"], "notes": self.m["quality"]["notes"], "scope": "full_match"}, "calibration": self.m["analysis"]["calibration"],
                 "models": models, "metrics_available": {"team_shape": list(SHAPE_METRICS), "pressing_profile": list(PRESS_METRICS), "possession_analysis": list(POSSESSION_METRICS),
                                                        "player_profile": list(PLAYER_METRICS), "compare_metrics": sorted(COMPARE)}}
        limits = ["xG and xPass are engine-model values, not real probabilities", "possession counts stable-owner time only (loose-ball time is excluded from the percentage)"]
        if models["xg"] is None:
            limits.append("no xG model: xg is null, not 0")
        return self._out(F, {}, teams, res, samples, {}, limits, self._evidence(F, ev_idx, elig=self._elig_any(teams, F)), sufficient, {"match": match})

    # ---- 2. tactical_evidence -------------------------------------------------------------------------------------------------------------------------------------------------------

    def tactical_evidence(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all", kind=None, event_type=None, player_id=None, sequence_id=None,
                          limit=50, cursor=None):
        """Tactical notes, events, sequences and timeline windows in the interval, each section with its total and a page of `limit` items (cursor = offset, only with `kind`)."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        if kind not in (None, *EVIDENCE_KINDS):
            return _err(f"unknown kind '{kind}'", list(EVIDENCE_KINDS))
        teams = self._teams(F)
        mine = lambda t: t is None or t in teams
        of = lambda t: teams if t is None else [t]  # perspectives that judge an item of team t
        whole = {**F, "from_t_s": 0.0, "until_t_s": self.end_t + 1.0}
        state = lambda at, t: any(self._ok_t(at, x, whole) for x in of(t))  # period and score_state at the item's start
        every = {
            "notes": [{"note_index": k, **n} for k, n in enumerate(self.m["notes"]) if mine(n["team"]) and self._touch(n["t_s"], n["until_t_s"], F) and (period is None or n["period"] == period)
                      and state(n["t_s"], n["team"])],
            "events": [{"event_index": j, **e} for j, e in enumerate(self.events) if mine(e["team"]) and (event_type is None or e["type"] == event_type)
                       and (player_id is None or e["player_id"] == player_id) and (sequence_id is None or e["sequence_id"] == sequence_id)
                       and any(self._ok_t(e["t_s"], t, F) for t in of(e["team"]))],
            "sequences": [s for s in self.seqs if mine(s["team"]) and self._touch(s["start_t_s"], s["end_t_s"], F) and (period is None or s["period"] == period)
                          and (sequence_id is None or s["sequence_id"] == sequence_id) and (player_id is None or player_id in s["players"]) and state(s["start_t_s"], s["team"])],
            "windows": [w for w in self.m["timeline"] if self._touch(w["start_t_s"], w["end_t_s"], F) and (period is None or w["period"] == period) and state(w["start_t_s"], None)]}
        off = cursor or 0
        out = {}
        for k in (EVIDENCE_KINDS if kind is None else (kind,)):
            items = every[k][off:off + limit] if kind else every[k][:limit]
            out[k] = {"total": len(every[k]), "items": items, "next_cursor": off + limit if kind and off + limit < len(every[k]) else None}
        ev = [e["event_index"] for e in out.get("events", {"items": []})["items"]]
        sq = [s["sequence_id"] for s in out.get("sequences", {"items": []})["items"]]
        samples = {t: self._sample(t, F, self._eligible(t, F)) for t in teams}
        limits = ["score_state is applied to notes, sequences and windows at their start time; they are returned whole, not cut to the part that satisfies the filter"] if score_state != "all" else []
        evid = self._evidence(F, ev, sq, elig=[])
        evid["timeline_windows"] = [w["window"] for w in out.get("windows", {"items": []})["items"]] or evid["timeline_windows"]
        return self._out(F, {"kind": kind, "event_type": event_type, "player_id": player_id, "sequence_id": sequence_id, "limit": limit, "cursor": cursor}, teams,
                         {"all": out}, samples, {}, limits, evid,
                         any(v["total"] for v in out.values()) and any(x["eligible_s"] > 0 for x in samples.values()))

    # ---- 3. team_shape --------------------------------------------------------------------------------------------------------------------------------------------------------------

    def team_shape(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all", in_possession=None, metrics=SHAPE_METRICS, window_s=R.WINDOW_S):
        """Block height, defensive line, length, width (metres), occupation by third and lane, and the relative block band with low-block candidates."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        if bad := [m for m in metrics if m not in SHAPE_METRICS]:
            return _err(f"unknown metrics {bad}", list(SHAPE_METRICS))
        teams, res, samples, ranges, sufficient = self._teams(F), {}, {}, [], True
        want = None if in_possession is None else "own" if in_possession else "opp"
        for t in teams:
            elig = self._eligible(t, F)
            samples[t] = self._sample(t, F, elig)
            phs = self._phs(t)
            w = {i: self._ovl(i, F) for i in elig}  # seconds of each step inside the query
            ids = [i for i in elig if phs[i] is not None and (want is None or phs[i] == want)]
            tot, r = sum(w[i] for i in ids), {}
            geo = {}
            for m in ("block_height", "defensive_line", "length", "width"):
                if m not in metrics and not (m == "block_height" and "block_band" in metrics):
                    continue
                ser = self._series(t, m)
                got = [i for i in ids if i in ser]
                v = sum(w[i] * ser[i] for i in got) / sum(w[i] for i in got) if got else None
                # references: always R.WINDOW_S windows of one possession phase; without a single phase (in_possession None) there is no reference
                ref = MIXED if want is None else R.reference(R.window_values(self.rows, phs, ser, want), R.FLAT_IQR_M)
                geo[m] = (v, ref)
                if m in metrics:
                    r[m] = {"value": v, "unit": "m", "reason": None if v is not None else "no_eligible_rows", **R.place(v, ref)}
                    sufficient = sufficient and r[m]["band"] is not None
            if "occupation" in metrics:
                r["occupation"] = ({"cells": S.occupation(self.rows, w, ids, t, self.length, self.width), "reason": None} if tot else
                                   {"cells": None, "reason": "no_eligible_rows"})
                sufficient = sufficient and bool(tot)
            if "block_band" in metrics:
                v, ref = geo["block_height"]
                pl = R.place(v, ref)
                eps, reason = [], None
                if in_possession is True:
                    reason = "not_defending"
                else:
                    bh = self._series(t, "block_height")
                    dref = R.reference(R.window_values(self.rows, phs, bh, "opp"), R.FLAT_IQR_M)
                    if not dref["sufficient"]:
                        reason = dref["reason"]
                    else:
                        for a, b in S.low_block_episodes(self.rows, phs, bh, self.length, dref["q25"]):
                            cov = self._cov(elig, self.ts[a], self.ts[b] + self.st, F)
                            if cov > 0:  # selected by overlap with the query; from/until and duration are the episode's own, covered_s the part inside the query
                                eps.append({"from_t_s": self.ts[a], "until_t_s": self.ts[b], "duration_s": self.ts[b] - self.ts[a], "covered_s": cov,
                                            "frame_range": [self.rows[a]["frame_index"], self.rows[b]["frame_index"]], "mean_block_height": sum(bh[i] for i in range(a, b + 1)) / (b - a + 1)})
                        ranges += [e["frame_range"] for e in eps]
                r["block_band"] = {"band": pl["band"], "reason": pl["relative_reason"] if pl["band"] is None else None, "low_block_candidates": eps, "candidates_reason": reason}
                sufficient = sufficient and pl["band"] is not None
            res[t] = r
            sufficient = sufficient and tot > 0
        lim = ["outfield players only (goalkeepers excluded)", "loose-ball rows are their own phase: they are left out when in_possession is set and the reference is per possession phase",
               "bands are relative to the team's own complete 5 s match windows in the same phase; without in_possession there is no single phase and bands are null (mixed_phases)"]
        if window_s != R.WINDOW_S:
            lim.append(f"window_s={window_s:g} is ignored: references always use {R.WINDOW_S:g} s windows")
        return self._out(F, {"in_possession": in_possession, "metrics": list(metrics), "window_s": window_s}, teams, res, samples,
                         {"window_s": window_s, "reference_window_s": R.WINDOW_S, "min_reference_windows": R.MIN_WINDOWS, "flat_iqr_m": R.FLAT_IQR_M, "low_block_min_s": S.LOW_BLOCK_MIN_S,
                          "reference_phase": want or "mixed"}, lim, self._evidence(F, ranges=ranges, elig=self._elig_any(teams, F)), sufficient)

    # ---- 4. pressing_profile --------------------------------------------------------------------------------------------------------------------------------------------------------

    def _episodes(self, radius_m, min_s):
        return self._cached(("eps", radius_m, min_s), lambda: P.pressing_episodes(self.rows, self.owners, radius_m, min_s))

    def pressing_profile(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all", metrics=PRESS_METRICS, radius_m=P.RADIUS_M, min_press_s=P.PRESS_MIN_S):
        """Pressure index, pressing episodes, high press, recoveries by third, high regains, press outcomes and an approximate PPDA (no fouls in the data)."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        if bad := [m for m in metrics if m not in PRESS_METRICS]:
            return _err(f"unknown metrics {bad}", list(PRESS_METRICS))
        teams, res, samples, ev_idx, ranges, sufficient, L = self._teams(F), {}, {}, [], [], True, self.length
        for t in teams:
            elig = self._eligible(t, F)
            samples[t] = s = self._sample(t, F, elig)
            phs, pres, r = self._phs(t), self._pres(t), {}
            indexed = [(j, e) for j, e in enumerate(self.events) if self._ok_t(e["t_s"], t, F)]
            recs = P.recoveries(indexed, t, L)
            eps = [e for e in self._episodes(radius_m, min_press_s) if e["team"] == t and self._cov(elig, self.ts[e["i0"]], self.ts[e["i1"]] + self.st, F) > 0]
            ref = R.reference(R.window_values(self.rows, phs, pres, "opp"), R.FLAT_IQR_PRESSURE)
            none = lambda why: {"reason": why}
            if "pressure" in metrics:
                got = [i for i in elig if i in pres]
                vals = got
                v = sum(self._ovl(i, F) * pres[i] for i in got) / sum(self._ovl(i, F) for i in got) if got else None
                r["pressure"] = {"value": v, "reason": None if vals else "no_rival_possession_rows", **R.place(v, ref)}
                sufficient = sufficient and r["pressure"]["band"] is not None
            if "pressures" in metrics:
                r["pressures"] = {"count": len(eps), "players": len({e["player_id"] for e in eps}), "per_min": len(eps) / (s["opponent_owned_s"] / 60) if s["opponent_owned_s"] else None,
                                  "reason": None if s["opponent_owned_s"] else "no_rival_possession_time"}
                ranges += [[self.rows[e["i0"]]["frame_index"], self.rows[e["i1"]]["frame_index"]] for e in eps][:20]
            if "high_press" in metrics:
                if not ref["sufficient"]:
                    r["high_press"] = {"count": None, "total_s": None, "episodes": [], "pressure_q75": None, **none(ref["reason"])}
                    sufficient = False
                else:
                    st = self.st
                    hp = [(a, b, c) for a, b in P.high_press_episodes(self.rows, pres, t, L, ref["q75"], min_press_s) if (c := self._cov(elig, self.ts[a], self.ts[b] + st, F)) > 0]
                    r["high_press"] = {"count": len(hp), "total_s": sum(c for _, _, c in hp), "pressure_q75": ref["q75"], "reason": None,
                                       "episodes": [{"from_t_s": self.ts[a], "until_t_s": self.ts[b], "duration_s": self.ts[b] - self.ts[a] + st, "covered_s": c,
                                                     "mean_pressure": sum(pres[i] for i in range(a, b + 1)) / (b - a + 1)} for a, b, c in hp]}
                    ranges += [[self.rows[a]["frame_index"], self.rows[b]["frame_index"]] for a, b, _ in hp][:20]
            if "recoveries" in metrics:
                by = {th: sum(c["third"] == th for c in recs) for th in S.THIRDS}
                r["recoveries"] = ({"total": len(recs), **by, "reason": None} if s["eligible_s"] else {"total": None, **{th: None for th in S.THIRDS}, **none("no_eligible_rows")})
                ev_idx += [c["event_index"] for c in recs]
            if "high_regains" in metrics:
                hr = [c for c in recs if c["xa"] >= L / 6]
                r["high_regains"] = {"count": len(hr), "reason": None} if s["eligible_s"] else {"count": None, **none("no_eligible_rows")}
                ev_idx += [c["event_index"] for c in hr]
            if "press_outcomes" in metrics:
                k = P.press_outcomes(eps, recs)
                r["press_outcomes"] = ({"episodes": len(eps), "followed_by_recovery": k, "rate": k / len(eps), "window_s": 3.0, "reason": None} if eps else
                                       {"episodes": 0, "followed_by_recovery": None, "rate": None, "window_s": 3.0, **none("no_press_episodes")})
            if "ppda_proxy" in metrics:
                n_pass, n_rec = P.ppda_proxy(indexed, recs, t, L)
                r["ppda_proxy"] = {"label": "PPDA aproximado (no fouls or duels in the data)", "value": n_pass / n_rec if n_rec else None, "opponent_passes": n_pass, "own_recoveries": n_rec,
                                   "reason": None if n_rec else "no_recoveries_in_zone"}
                sufficient = sufficient and n_rec > 0
            res[t] = r
            sufficient = sufficient and s["eligible_s"] > 0
        lim = ["pressure is measured on the rival's stable owner only", "press_outcomes is a temporal association, not causality", "PPDA is approximate: recorded passes only, no fouls or duels"]
        return self._out(F, {"metrics": list(metrics), "radius_m": radius_m, "min_press_s": min_press_s}, teams, res, samples,
                         {"radius_m": radius_m, "min_press_s": min_press_s, "min_reference_windows": R.MIN_WINDOWS, "flat_iqr_pressure": R.FLAT_IQR_PRESSURE, "high_press_pressure_quantile": "q75",
                          "press_outcome_window_s": 3.0, "ppda_zone": "rival pass origin / own recovery at xa >= -L/10"}, lim,
                         self._evidence(F, ev_idx, ranges=ranges, elig=self._elig_any(teams, F)), sufficient)

    # ---- 5. compare_metrics ---------------------------------------------------------------------------------------------------------------------------------------------------------

    def _interval(self, iv):
        return {"from_t_s": iv.get("from_t_s", 0.0), "until_t_s": iv.get("until_t_s"), "period": iv.get("period"), "score_state": iv.get("score_state", "all")}

    def compare_metrics(self, metric_ids, subject, interval_a, interval_b=None, reference="match", in_possession=None):
        """a vs b for each metric id of COMPARE: difference, ratio, % change (points for % metrics), and where a sits among the match's 5 s windows (percentile, rank, match max).
        Without interval_b, b is `reference`: 'match' (the whole match, same team) or 'opponent' (the other team in interval_a). Every number is a tool result or computed from two of them."""
        if subject not in ("home", "away"):
            return _err(f"unknown subject '{subject}'", ["home", "away"])
        if bad := [m for m in metric_ids if m not in COMPARE]:
            return _err(f"unknown metric ids {bad}", sorted(COMPARE))
        if reference not in ("match", "opponent"):
            return _err(f"unknown reference '{reference}'", ["match", "opponent"])
        A = self._interval(interval_a)
        B = self._interval(interval_b) if interval_b else (self._interval({}) if reference == "match" else A)
        side_b = subject if (interval_b or reference == "match") else opponent(subject)
        res, calls, ok = {}, [], True
        for mid in metric_ids:
            tool, kw, path, unit = COMPARE[mid]
            if tool == "team_shape":
                kw = {**kw, "in_possession": in_possession}
            got = []
            for side, iv in ((subject, A), (side_b, B)):
                r = getattr(self, tool)(team=side, **iv, **kw)
                if "error" in r:
                    return r
                calls.append(r)
                node = r["results"][side]
                parent = node.get(path[0]) if isinstance(node, dict) else None
                val = _dig(node, path)
                blk = parent if isinstance(parent, dict) and "percentile" in parent else {}
                src = parent if isinstance(parent, dict) else {}
                got.append({"value": val, "percentile": blk.get("percentile"), "rank": blk.get("rank"), "band": blk.get("band"), "match_max": blk.get("max"),
                            "reason": src.get("reason") or ("no value" if val is None else None),  # the source reason survives a partial value (e.g. some_shots_without_xg)
                            "coverage": {k: src[k] for k in ("shots", "shots_with_xg", "episodes") if k in src} or None})
            a, b = got[0]["value"], got[1]["value"]
            miss = a is None or b is None
            partial = not miss and any(g["reason"] for g in got)
            zero = not miss and b == 0
            res[mid] = {"unit": unit, "a": got[0], "b": got[1], "diff": None if miss else a - b, "ratio": None if miss or zero else a / b,
                        "pct_change": None if miss or zero else 100 * (a - b) / abs(b), "change_pts": a - b if not miss and unit in POINT_UNITS else None,
                        "partial": partial, "ratio_reason": "zero_reference_denominator" if zero else None,
                        "reason": "a or b has no value (see their reasons)" if miss else "partial_inputs: " + ", ".join(f"{n}={g['reason']}" for n, g in zip("ab", got) if g["reason"]) if partial
                        else "zero_reference_denominator" if zero else None}
            ok = ok and not miss and not partial
        lim = BASE_LIMITS + sorted({x for c in calls for x in c["limitations"] if x not in BASE_LIMITS})
        ev = {k: sorted({x for c in calls for x in c["evidence"][k]}) if k != "frame_ranges" else [r for c in calls for r in c["evidence"][k]] for k in calls[0]["evidence"]} if calls else {}
        th = {}
        for c in calls:
            th.update(c["thresholds_used"])
        return R.rounded({"from_t_s": A["from_t_s"], "until_t_s": calls[0]["until_t_s"] if calls else None,
                          "parameters": {"metric_ids": list(metric_ids), "subject": subject, "interval_a": A, "interval_b": B, "reference": reference if not interval_b else None, "in_possession": in_possession},
                          "thresholds_used": th, "sample": {"a": calls[0]["sample"], "b": calls[1]["sample"]} if calls else {}, "sufficient_evidence": ok and all(c["sufficient_evidence"] for c in calls),
                          "limitations": lim, "evidence": ev, "results": {subject: res}})

    # ---- 6. possession_analysis (tanda 1) -------------------------------------------------------------------------------------------------------------------------------------------

    def possession_analysis(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all", metrics=POSSESSION_METRICS, transition_s=T.TRANSITION_S,
                            counter_gain_m=T.COUNTER_GAIN_M):
        """Possessions, build-up, attacking and defensive transitions (first transition_s after gaining or losing the ball), counters and the phase candidates of phases.jsonl."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        if bad := [m for m in metrics if m not in POSSESSION_METRICS]:
            return _err(f"unknown metrics {bad}", list(POSSESSION_METRICS))
        teams, res, samples, ev_idx, sq_ids, ranges, sufficient = self._teams(F), {}, {}, [], [], [], True
        L, args, st = self.length, (self.rows, self.idx, self.seqs, self.events), self.st
        for t in teams:
            elig = self._eligible(t, F)
            samples[t] = s = self._sample(t, F, elig)
            r = {}
            if "possessions" in metrics:
                picked = self._pick([q for q in self.seqs if q["team"] == t], "start_t_s", "end_t_s", F, elig, st)
                r["possessions"] = {**T.possession_summary([q for q, _ in picked]), "covered_s": sum(c for _, c in picked)}
                sq_ids += r["possessions"]["sequence_ids"]
            for name, fn in (("build_up", lambda: T.build_ups(*args, t, L)), ("attacking_transitions", lambda: T.attacking_transitions(*args, t, L, transition_s)),
                             ("defensive_transitions", lambda: T.defensive_transitions(*args, t, L, transition_s)),
                             ("counters", lambda: T.counters(*args, t, L, transition_s, counter_gain_m))):
                if name in metrics:
                    got = [{**x, "covered_s": c} for x, c in self._pick(fn(), "from_t_s", "until_t_s", F, elig, st)]
                    r[name] = {"count": len(got), "items": got, "reason": None}
                    ev_idx += [j for x in got for j in x["event_indices"]]
                    ranges += [x["frame_range"] for x in got]
                    sq_ids += [x["sequence_id"] for x in got]
            if "phase_candidates" in metrics:
                ph = self.m["phases"]
                if ph is None:
                    r["phase_candidates"] = {"count": None, "items": [], "unclassified_s": None, "reason": "phases.jsonl not found"}
                    sufficient = False
                else:
                    got = [{**c, "covered_s": cv} for c, cv in self._pick([c for c in ph if c["team"] == t], "from_t_s", "until_t_s", F, elig, st)]
                    union = sum(self._cov(elig, a0, b0, F) for a0, b0 in _merge([(c["from_t_s"], c["until_t_s"] + st) for c in got]))
                    r["phase_candidates"] = {"count": len(got), "items": got, "unclassified_s": max(0.0, s["eligible_s"] - union), "reason": None,
                                             "note": "stretches without a candidate are unclassified; items keep their own from/until, covered_s is the part inside the query"}
                    ev_idx += [j for c in got for j in c["evidence"]["event_indices"]]
                    sq_ids += [j for c in got for j in c["evidence"]["sequence_ids"]]
                    ranges += [fr for c in got for fr in c["evidence"]["frame_ranges"]]
            res[t] = r
            sufficient = sufficient and s["eligible_s"] > 0
        lim = ["a gain needs a previous sequence of the rival that ended 'lost': the first sequence of a clip proves no earlier recovery", "kick-offs and set pieces are restarts, not transitions",
               "candidate times and counts come from phases.jsonl and are not renumbered", "items are selected by overlap with the query and keep their own from/until; covered_s is the part inside the query"]
        return self._out(F, {"metrics": list(metrics), "transition_s": transition_s, "counter_gain_m": counter_gain_m}, teams, res, samples,
                         {"transition_s": transition_s, "counter_gain_m": counter_gain_m},
                         lim, self._evidence(F, ev_idx, sq_ids, ranges, elig=self._elig_any(teams, F)), sufficient)

    # ---- 7. player_profile (rating only) -----------------------------------------------------------------------------------------------------------------------------------------------

    def player_profile(self, team=None, from_t_s=0.0, until_t_s=None, period=None, score_state="all", player_id=None, metrics=PLAYER_METRICS, rank_by=None, limit=22):
        """Rating of each player as published in players.json (value, unit if present, breakdown, reason; scope full_match)."""
        F = self._F(team, from_t_s, until_t_s, period, score_state)
        if "error" in F:
            return F
        if bad := [m for m in metrics if m not in PLAYER_METRICS]:
            return _err(f"unknown metrics {bad}", list(PLAYER_METRICS))
        if rank_by not in (None, *PLAYER_METRICS):
            return _err(f"unknown rank_by '{rank_by}'", list(PLAYER_METRICS))
        if player_id and not any(p["player_id"] == player_id for p in self.m["players"]):
            return _err(f"unknown player '{player_id}'", [p["player_id"] for p in self.m["players"]])
        teams = self._teams(F)
        pl = [p for p in self.m["players"] if p["team"] in teams and (player_id is None or p["player_id"] == player_id)]
        rows = [{"player_id": p["player_id"], "team": p["team"], "name": self.m["roster"].get(p["player_id"], {}).get("name"), "role": self.m["roster"].get(p["player_id"], {}).get("role"),
                 "rating": {"scope": "full_match", **{k: v for k, v in p["rating"].items()}}} for p in pl]
        if rank_by:
            rows.sort(key=lambda r: (r["rating"].get("value") is None, -(r["rating"].get("value") or 0)))
        rows = rows[:limit]
        samples = {t: self._sample(t, F, self._eligible(t, F)) for t in teams}
        full = F["from_t_s"] > 0 or F["until_t_s"] < self.end_t or period is not None or score_state != "all"
        lim = ["rating is a full-match value: the time, period and score filters do not cut it"] if full else []
        lim.append("a null rating carries its reason (e.g. goalkeepers)")
        return self._out(F, {"player_id": player_id, "metrics": list(metrics), "rank_by": rank_by, "limit": limit}, teams, {t: [r for r in rows if r["team"] == t] for t in teams}, samples,
                         {}, lim, self._evidence(F, elig=[]), any(r["rating"].get("value") is not None for r in rows))


def _merge(spans):
    """Disjoint sorted [(a, b)] union of the (a, b) spans."""
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [tuple(x) for x in out]
