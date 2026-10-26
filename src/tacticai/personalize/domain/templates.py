"""Fallback texts: one (title, text) per kind x subtype x text lens x lang x perspective. Placeholders only: no literal number or number word ever appears.

Plural choice: counts are written as `{lines_broken} {lines_broken|line|lines}`; the second placeholder is the plural form of placeholders.py, resolved from the metric value
(1 -> first word, anything else -> second), so "1 line" and "2 lines" come from the same stored text. Decimal comma for "es" is done by resolve_text(..., lang="es").

Build: each (kind, subtype) has an analyst pair, a fan pair and a first_match title (its text is the concept sentence of the kind plus the fan text).
Perspective: neutral names both teams ("<vs>"); own / opponent add a mood-dependent prefix to the title and a closing sentence to the fan and first_match texts.
Tokens in the strings below are `<T>` (team of the insight), `<vs>`, `<xgp>`, `<xgw>`, `<shot>`, `<why>`, `<hi>`, `<pkt>` and `<dom>`; they are replaced here, never by a user."""
import re

from .lenses import perspective

_LB_EN = "<T> broke {lines_broken} {lines_broken|line|lines} in {passes} {passes|pass|passes} over {duration_s} s<vs>"
_LB_ES = "<T> rompió {lines_broken} {lines_broken|línea|líneas} en {passes} {passes|pase|pases} durante {duration_s} s<vs>"
_BROKE_EN = "{lines_broken} {lines_broken|line|lines}"
_BROKE_ES = "{lines_broken} {lines_broken|línea|líneas}"

# (analyst title, analyst text, fan title, fan text, first_match title)
TEXTS = {
    "en": {
        ("lines_broken", "goal"): ("Line-breaking move ends in a goal", _LB_EN + ", and the move ended in a goal<xgp>.",
                                    "Goal after breaking " + _BROKE_EN + "!", "<T> carved the defence open and finished the move with a goal<xgp>.", "A goal from a clever move"),
        ("lines_broken", "shot"): ("Line-breaking move ends in a shot", _LB_EN + ", and the move ended in a shot<xgp>.",
                                    "A dangerous move: " + _BROKE_EN + " broken", "<T> got through the defence and took a shot<xgp>.", "A move that ends in a shot"),
        ("lines_broken", "lost"): ("Line-breaking move, ball lost", _LB_EN + ", but the ball was lost at the end of the move.",
                                    "So close: the move broke down", "<T> got through the defence but lost the ball.", "A promising move that was lost"),
        ("lines_broken", "out"): ("Line-breaking move, ball out of play", _LB_EN + ", but the ball went out of play.",
                                   "Out of play", "<T> got through the defence but the ball went out of play.", "A promising move that went out"),
        ("lines_broken", "end_of_period"): ("Line-breaking move cut by the end of the period", _LB_EN + ", and the period ended before the move was finished.",
                                             "Time ran out mid-move", "<T> got through the defence, but the period ended before the move was finished.", "A move cut short by the whistle"),
        ("pressure_spell", "shift_up"): ("Pressure rises", "<T> raised its pressure from {before} to {after}<vs>, and it held over a sustained spell.",
                                          "More pressure from <T>", "<T> started squeezing the rival much harder: pressure went from {before} to {after}.", "A team starts pressing harder"),
        ("pressure_spell", "shift_down"): ("Pressure drops", "<T> lowered its pressure from {before} to {after}<vs>, and it held over a sustained spell.",
                                            "Less pressure from <T>", "<T> stopped squeezing the rival as hard: pressure went from {before} to {after}.", "A team presses less"),
        ("pressure_spell", "peak"): ("<pkt>", "<T> reached a pressure of {value}<vs>, against a match mean of {match_mean}.<hi>",
                                      "Heavy pressure from <T>", "<T> pressed at {value}, far above its usual {match_mean}.<hi>", "A team presses very hard"),
        ("goal_or_chance", "goal"): ("Goal", "<T> scored<vs><shot>. <why>.", "Goal for <T>!", "<T> scored<shot>. <why>.", "A goal"),
        ("goal_or_chance", "chance_scored"): ("Big chance, scored", "<T> scored from a big chance<xgw><vs>.",
                                               "A big chance, and it goes in!", "<T> had a big chance<xgw> and made it count.", "A good chance that ends in a goal"),
        ("goal_or_chance", "chance_missed"): ("Big chance, missed", "<T> created a big chance<xgw><vs>, but did not score.",
                                               "So close!", "<T> had a great chance<xgw> but the ball did not go in.", "A good chance that was missed"),
        ("momentum_shift", "swing"): ("Momentum swing", "Momentum swung to <T>, from {before} to {after}<vs>, over a sustained spell.",
                                       "The game turns for <T>", "The match tilted towards <T>: momentum went from {before} to {after}.", "The match changes hands"),
        ("momentum_shift", "dominance"): ("Dominant spell", "<T> dominated a spell with a mean momentum of {mean_momentum}<dom><vs>.",
                                           "Control for <T>", "<T> controlled the match for a while<dom>.", "A team takes control"),
    },
    "es": {
        ("lines_broken", "goal"): ("Jugada que rompe líneas y termina en gol", _LB_ES + ", y la jugada terminó en gol<xgp>.",
                                    "¡Gol tras romper " + _BROKE_ES + "!", "<T> abrió la defensa y cerró la jugada con un gol<xgp>.", "Un gol que sale de una buena jugada"),
        ("lines_broken", "shot"): ("Jugada que rompe líneas y termina en remate", _LB_ES + ", y la jugada terminó en un remate<xgp>.",
                                    "Jugada peligrosa: " + _BROKE_ES + " superadas", "<T> atravesó la defensa y llegó al remate<xgp>.", "Una jugada que termina en remate"),
        ("lines_broken", "lost"): ("Jugada que rompe líneas, pero se pierde la pelota", _LB_ES + ", pero perdió la pelota al final de la jugada.",
                                    "Casi: la jugada se cortó", "<T> atravesó la defensa pero perdió la pelota.", "Una buena jugada que se pierde"),
        ("lines_broken", "out"): ("Jugada que rompe líneas, pero la pelota sale", _LB_ES + ", pero la pelota salió del campo.",
                                   "Se fue afuera", "<T> atravesó la defensa, pero la pelota salió del campo.", "Una buena jugada que termina afuera"),
        ("lines_broken", "end_of_period"): ("Jugada que rompe líneas, cortada por el final del período", _LB_ES + ", y el período terminó antes de que la jugada se definiera.",
                                             "Se acabó el tiempo en plena jugada", "<T> atravesó la defensa, pero el período terminó antes de definir.", "Una jugada cortada por el pitazo final"),
        ("pressure_spell", "shift_up"): ("Sube la presión", "<T> subió su presión de {before} a {after}<vs>, y se sostuvo durante un tramo.",
                                          "<T> aprieta más", "<T> empezó a presionar mucho más al rival: la presión pasó de {before} a {after}.", "Un equipo empieza a presionar más"),
        ("pressure_spell", "shift_down"): ("Baja la presión", "<T> bajó su presión de {before} a {after}<vs>, y se sostuvo durante un tramo.",
                                            "<T> afloja", "<T> dejó de presionar tanto al rival: la presión pasó de {before} a {after}.", "Un equipo presiona menos"),
        ("pressure_spell", "peak"): ("<pkt>", "<T> alcanzó una presión de {value}<vs>, frente a una media del partido de {match_mean}.<hi>",
                                      "Mucha presión de <T>", "<T> presionó a {value}, muy por encima de su nivel habitual de {match_mean}.<hi>", "Un equipo presiona con mucha fuerza"),
        ("goal_or_chance", "goal"): ("Gol", "<T> marcó un gol<vs><shot>. <why>.", "¡Gol de <T>!", "<T> marcó<shot>. <why>.", "Un gol"),
        ("goal_or_chance", "chance_scored"): ("Ocasión clara, convertida", "<T> convirtió una ocasión clara<xgw><vs>.",
                                               "¡Ocasión clara y es gol!", "<T> tuvo una ocasión clara<xgw> y la aprovechó.", "Una buena ocasión que termina en gol"),
        ("goal_or_chance", "chance_missed"): ("Ocasión clara, desperdiciada", "<T> generó una ocasión clara<xgw><vs>, pero no convirtió.",
                                               "¡Casi!", "<T> tuvo una gran ocasión<xgw>, pero la pelota no entró.", "Una buena ocasión que se desperdició"),
        ("momentum_shift", "swing"): ("Cambio de momentum", "El momentum pasó a <T>, de {before} a {after}<vs>, durante un tramo sostenido.",
                                       "El partido cambia para <T>", "El partido se inclinó a favor de <T>: el momentum pasó de {before} a {after}.", "El partido cambia de manos"),
        ("momentum_shift", "dominance"): ("Tramo dominante", "<T> dominó un tramo con un momentum medio de {mean_momentum}<dom><vs>.",
                                           "<T> manda en el partido", "<T> controló el partido durante un buen rato<dom>.", "Un equipo toma el control"),
    },
}

# one sentence that explains the concept before the fact (first_match)
CONCEPT = {
    "en": {
        "lines_broken": "In football, defenders stand in rows called lines, and a pass that gets the ball past a row is a big step towards goal.",
        "pressure_spell": "Pressure measures how hard a team squeezes its rival to win the ball back quickly.",
        "goal_or_chance": "A goal counts when the ball fully crosses the goal line, and xG, or expected goals, says how likely a shot is to score.",
        "momentum_shift": "Momentum shows which team is pushing the match in its favour at a given time.",
    },
    "es": {
        "lines_broken": "En el fútbol, los defensores se paran en filas llamadas líneas, y un pase que deja una fila atrás acerca mucho al gol.",
        "pressure_spell": "La presión mide qué tan fuerte un equipo aprieta al rival para recuperar la pelota rápido.",
        "goal_or_chance": "Hay gol cuando la pelota cruza por completo la línea de meta, y el xG, o goles esperados, dice qué tan probable es que un remate termine en gol.",
        "momentum_shift": "El momentum muestra qué equipo está inclinando el partido a su favor en cada momento.",
    },
}

# is the event good or bad for the team it belongs to?
BAD = {("pressure_spell", "shift_down")}
FLAT = {("lines_broken", "lost"), ("lines_broken", "out"), ("lines_broken", "end_of_period"), ("goal_or_chance", "chance_missed")}

PREFIX = {  # lang -> lens -> perspective -> mood -> title prefix
    "en": {"analyst": {"own": dict.fromkeys(("good", "bad", "flat"), "Own side: "), "opponent": dict.fromkeys(("good", "bad", "flat"), "Opponent: ")},
           "fan": {"own": {"good": "Yes! ", "bad": "Careful: ", "flat": "Own side: "}, "opponent": {"good": "Watch out: ", "bad": "Good news: ", "flat": "Opponent: "}},
           "first_match": {"own": {"good": "Your side: ", "bad": "Your side: ", "flat": "Your side: "}, "opponent": {"good": "The rival: ", "bad": "The rival: ", "flat": "The rival: "}}},
    "es": {"analyst": {"own": dict.fromkeys(("good", "bad", "flat"), "Equipo propio: "), "opponent": dict.fromkeys(("good", "bad", "flat"), "Rival: ")},
           "fan": {"own": {"good": "Muy bien: ", "bad": "Ojo: ", "flat": "Equipo propio: "}, "opponent": {"good": "Ojo: ", "bad": "Buena señal: ", "flat": "Rival: "}},
           "first_match": {"own": {"good": "Tu equipo: ", "bad": "Tu equipo: ", "flat": "Tu equipo: "}, "opponent": {"good": "El rival: ", "bad": "El rival: ", "flat": "El rival: "}}},
}
SUFFIX = {  # lang -> perspective -> mood -> closing sentence (fan and first_match only)
    "en": {"own": {"good": " A great moment for your side.", "bad": " Time to react.", "flat": " Keep going."},
           "opponent": {"good": " Time to defend well.", "bad": " An opening for your side.", "flat": " A chance to regroup."}},
    "es": {"own": {"good": " Un gran momento para tu equipo.", "bad": " Hay que reaccionar.", "flat": " A seguir."},
           "opponent": {"good": " Hay que defender bien.", "bad": " Se abre una oportunidad para tu equipo.", "flat": " Momento de reagrupar."}},
}

VS = {"en": " against <O>", "es": " ante <O>"}
XGP = {"en": " ({xg} engine xG)", "es": " ({xg} xG del motor)"}
XGW = {"en": " worth {xg} engine xG", "es": " de {xg} xG del motor"}
SHOT = {"en": " from a shot worth {xg} engine xG", "es": " con un remate de {xg} xG del motor"}
WHY = {"en": {"first_goal": "It opened the scoring", "equaliser": "It levelled the score", "go_ahead": "It put <T> ahead", None: "It changed the score"},
       "es": {"first_goal": "Abrió el marcador", "equaliser": "Igualó el partido", "go_ahead": "Puso arriba a <T>", None: "Cambió el marcador"}}
PKT = {"en": {True: "Highest pressure of the match", False: "Strong spell of pressure"}, "es": {True: "Presión más alta del partido", False: "Tramo de presión fuerte"}}
HI = {"en": " It is its highest pressure of the match.", "es": " Es su presión más alta del partido."}
DOM_XG = {"en": "{xg} engine xG", "es": "{xg} xG del motor"}
DOM_IN = {"en": "{final_third_entries} {final_third_entries|entry|entries} into the final third", "es": "{final_third_entries} {final_third_entries|entrada|entradas} al último tercio"}
DOM_WITH = {"en": ", producing ", "es": ", generando "}
AND = {"en": " and ", "es": " y "}


def mood(kind, subtype):
    return "bad" if (kind, subtype) in BAD else "flat" if (kind, subtype) in FLAT else "good"


def _tokens(c, names, lang, persp):
    m, cl = c["metrics"], c["claims"]
    other = names["away" if c["team"] == "home" else "home"]
    why = next((WHY[lang][k] for k in ("first_goal", "equaliser", "go_ahead") if k in cl), WHY[lang][None])
    dom = [t for k, t in (("xg", DOM_XG), ("final_third_entries", DOM_IN)) if k in m]
    return {"T": names[c["team"]], "O": other, "vs": VS[lang].replace("<O>", other) if persp == "neutral" else "",
            "xgp": XGP[lang] if "xg" in m else "", "xgw": XGW[lang] if "xg" in m else "", "shot": SHOT[lang] if "xg" in m else "",
            "why": why, "pkt": PKT[lang]["match_max" in cl], "hi": HI[lang] if "match_max" in cl else "",
            "dom": DOM_WITH[lang] + AND[lang].join(t[lang] for t in dom) if dom else ""}


def neutral_body(c, names, lens, lang, persp="neutral"):
    """-> (title, text) of an insight for a text lens, before the perspective and the concept sentence. Placeholders unresolved."""
    at, ax, ft, fx, mt = TEXTS[lang][(c["kind"], c["subtype"])]
    title, text = {"analyst": (at, ax), "fan": (ft, fx), "first_match": (mt, fx)}[lens]
    tok = _tokens(c, names, lang, persp)
    for _ in range(2):  # tokens can contain tokens (<why> holds <T>)
        title, text = (re.sub(r"<(\w+)>", lambda m: tok[m.group(1)], s) for s in (title, text))
    return title, text


def perspective_text(c, title, text, lens, lang, club):
    """Neutral (title, text) body -> the version for `club`: first_match opens with the concept sentence, a side adds the title prefix and, outside analyst, the closing sentence."""
    persp, md = perspective(club, c["team"]), mood(c["kind"], c["subtype"])
    if lens == "first_match":
        text = CONCEPT[lang][c["kind"]] + " " + text
    if persp != "neutral":
        title = PREFIX[lang][lens][persp][md] + title
        if lens != "analyst":
            text += SUFFIX[lang][persp][md]
    return title, text


def template(c, names, lens, lang, club):
    """-> (title, text) for an insight dict (kind, subtype, team, metrics, claims), text lens, lang and club (neutral|home|away). Placeholders unresolved."""
    return perspective_text(c, *neutral_body(c, names, lens, lang, perspective(club, c["team"])), lens, lang, club)
