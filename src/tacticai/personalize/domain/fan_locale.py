"""Fixed strings of the fan view (labels of the interface) and the minimal fallback used when the Supporter agent's text does not pass.
The fallback is a line of data, never prose: it cannot take the wrong side, mix languages or invent anything."""

KIND = {
    "en": {"goal": "Goal", "miss": "Shot", "save": "Save", "mistake": "Ball lost", "pinned": "Pinned back", "turn": "The game turns",
           "move": "Passing move", "pass": "Pass", "carry": "Run with the ball", "tackle": "Ball won", "sprint": "Sprint"},
    "es": {"goal": "Gol", "miss": "Remate", "save": "Atajada", "mistake": "Pelota perdida", "pinned": "Encierro", "turn": "Cambia el partido",
           "move": "Toque", "pass": "Pase", "carry": "Conducción", "tackle": "Recuperación", "sprint": "Pique"},
}
#: Where a shot came from, in words (the agent gets meaning, never an internal code).
SHOT_FROM = {"en": {"outside_box": "from outside the box", "close_range": "from close range", "in_the_box": "inside the box"},
             "es": {"outside_box": "de afuera del área", "close_range": "debajo del arco", "in_the_box": "adentro del área"}}
#: How a metric reads in a data line: the number always with its unit or noun.
METRIC = {
    "en": {"run_m": "{run_m} m", "top_kmh": "{top_kmh} km/h", "run_kmh": "{run_kmh} km/h", "shot_kmh": "{shot_kmh} km/h", "shot_m": "{shot_m} m out",
           "passes": "{passes} {passes|pass|passes}", "move_passes": "{move_passes} {move_passes|pass|passes}",
           "lines_broken": "{lines_broken} {lines_broken|line|lines} broken", "gain_m": "{gain_m} m forward", "carry_m": "{carry_m} m", "carry_kmh": "{carry_kmh} km/h"},
    "es": {"run_m": "{run_m} m", "top_kmh": "{top_kmh} km/h", "run_kmh": "{run_kmh} km/h", "shot_kmh": "{shot_kmh} km/h", "shot_m": "a {shot_m} m",
           "passes": "{passes} {passes|pase|pases}", "move_passes": "{move_passes} {move_passes|pase|pases}",
           "lines_broken": "{lines_broken} {lines_broken|línea rota|líneas rotas}", "gain_m": "{gain_m} m adelante", "carry_m": "{carry_m} m", "carry_kmh": "{carry_kmh} km/h"},
}
SCORE = "{home_short} {home_goals}–{away_goals} {away_short}"
RESULT = {"en": {"win": "We won", "loss": "We lost", "draw": "A draw", "decided": "{winner} win"},
          "es": {"win": "Ganamos", "loss": "Perdimos", "draw": "Empate", "decided": "Ganó {winner}"}}
FIGURE = {"en": "Star: {figure}", "es": "Figura: {figure}"}
BAND = {"en": ["Off day", "Steady", "Good game", "Outstanding"], "es": ["No fue su partido", "Cumplió", "Buen partido", "Partidazo"]}
AWARD = {
    "en": {"engine": ("The engine", "{distance_m} metres covered"), "fastest": ("Fastest on the pitch", "{top_kmh} km/h"),
           "sprinter": ("Never stopped running", "{sprints} {sprints|sprint|sprints}"), "playmaker": ("Ran the show", "{passes_completed} passes completed"),
           "rocket": ("Hardest hit", "{shot_kmh} km/h")},
    "es": {"engine": ("El motorcito", "{distance_m} metros recorridos"), "fastest": ("El más rápido", "{top_kmh} km/h"),
           "sprinter": ("No paró de correr", "{sprints} {sprints|pique|piques}"), "playmaker": ("El que la movió", "{passes_completed} pases buenos"),
           "rocket": ("El cañonazo", "{shot_kmh} km/h")},
}
#: Questions the Q&A tools can answer, when the agent's own suggestions do not pass.
ASK = {"en": ["Who scored?", "Every shot of the match", "Who lost the ball?"],
       "es": ["¿Quién hizo los goles?", "Todos los remates del partido", "¿Quién perdió la pelota?"]}


def moment(f, names, lang):
    """-> (title, text): the kind, the names in the fact and its numbers, e.g. ("Goal", "Dunmorrow · Corlune · BKA 1–0 WXC")."""
    bits = list(names) or []
    if f["kind"] == "goal":
        bits.append(SCORE)
    bits += [METRIC[lang][k] for k in f["metrics"] if k in METRIC[lang]]
    return KIND[lang][f["kind"]], " · ".join(bits)


def verdict(result, winner_name, figure_name, lang):
    head = RESULT[lang][result].format(winner=winner_name)
    return head, SCORE + (" · " + FIGURE[lang].format(figure=figure_name) if figure_name else "")


def rating(r, lang):
    """A player's plain counts through placeholders."""
    m, es = r["metrics"], lang == "es"
    bits = []
    if m["goals"]["value"]:
        bits.append("{goals} {goals|gol|goles}" if es else "{goals} {goals|goal|goals}")
    if m["assists"]["value"]:
        bits.append("{assists} {assists|asistencia|asistencias}" if es else "{assists} {assists|assist|assists}")
    if m["shots"]["value"] and not m["goals"]["value"]:
        bits.append("{shots} {shots|remate|remates}" if es else "{shots} {shots|shot|shots}")
    if m["passes"]["value"]:
        bits.append("{passes_completed}/{passes} pases" if es else "{passes_completed}/{passes} passes")
    if m["tackles"]["value"]:
        bits.append("{tackles} {tackles|recuperación|recuperaciones}" if es else "{tackles} {tackles|tackle|tackles} won")
    return " · ".join(bits) or ("Poca participación" if es else "Little involvement")
