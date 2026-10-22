# Scenario Agent

The Scenario Agent lets a person ask for a football match or a single play in plain language ("a Wexmoor counter-attack down the left that ends in a shot") and returns that play as video plus data. It does not script the play: it writes a **recipe** that sets how the teams play and where the play starts, then searches many simulated outcomes and keeps the one that matches the request.

**Status (2026-10-22):** the code behind every tool is built and tested (recipe, validation, search, evaluation, rendering). Still to build: the agent itself (the LLM layer in Microsoft Foundry), the thin tool wrappers it calls, the MCP server and the API. The agent is waiting for the Foundry project details.

## Layers

```
 ┌──────────────────────────────────────────────────────────────┐
 │ 1. Entry points     UI (text, later voice) · REST API · MCP    │
 └───────────────────────────────┬──────────────────────────────┘
                                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 2. Agent (LLM)      Microsoft Agent Framework + a Foundry model│
 │                     request → recipe, edits, explains results  │
 └───────────────────────────────┬──────────────────────────────┘
                                 ▼  tool calls
 ┌──────────────────────────────────────────────────────────────┐
 │ 3. Tools (code)     catalog · validate · search · result      │
 │                     deterministic, no LLM                      │
 └───────────────────────────────┬──────────────────────────────┘
                                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 4. Match factory    engine in Docker: headless simulation,     │
 │                     evaluation, render of the winner           │
 └───────────────────────────────┬──────────────────────────────┘
                                 ▼
 ┌──────────────────────────────────────────────────────────────┐
 │ 5. Output           match package (data contract) + recipe +   │
 │                     search report + a short answer to the user │
 └──────────────────────────────────────────────────────────────┘
```

### 1. Entry points

- **UI:** a text box (voice with Azure AI Speech later). The recipe is shown as editable buttons (formation, style and level per team) and a mini pitch with the starting positions.
- **REST API:** the UI and any client call the agent and follow the job's progress ("seed 23 of 50", "rendering").
- **MCP server:** the same tools are exposed over MCP, so other agents (and judges) can drive the match factory directly.

### 2. Agent

An LLM agent built with Microsoft Agent Framework on a model deployed in Microsoft Foundry. It does three things:

- **Translate** the request into a recipe, using structured output against the recipe schema.
- **Edit** the current recipe on follow-ups ("more pressure", "make it end in a goal") instead of starting over.
- **Explain** the result in one or two sentences, using only what the search report says.

It never invents an outcome: if no seed met the request, it says what was missing and proposes a change (more seeds, another template). The person decides. If the model fails, the error is reported and the current recipe stays intact; there are no automatic retries.

### 3. Tools

Deterministic code. The logic already exists in `src/tacticai/ingest/`; the tools are thin wrappers over it (to build with the agent):

| Tool | What it does | Code |
|---|---|---|
| `get_catalog` | Lists what a recipe can use: 8 formations, 4 styles, 4 situation templates, end conditions, wanted outcomes | `domain/formations.py`, `domain/styles.py`, `domain/situations.py`, `domain/recipe.py` |
| `validate_recipe` | Checks a recipe and returns readable errors (11 players, one goalkeeper, valid formation, players on the pitch...) | `domain/recipe.py` |
| `run_search` | Simulates N seeds without video, evaluates each against the request, picks the winner and renders it | `application/search.py`, `domain/evaluate.py` |
| `get_result` | Returns the search report and the paths of the winning match package | `search_report.json` |

### 4. Match factory

The engine runs in the `tai-engine` Docker image (locally, and as an Azure Container Apps Job in the cloud). For each seed it simulates the play **without video**, writes tracking in the data contract, infers events from positions, and scores it. Only the winning seed is simulated again **with video**; the engine is deterministic, so it is the same play.

## The recipe

The recipe sets how the play is played, never what happens:

```json
{
  "mode": "situation",
  "home": {"formation": "4-3-3", "style": "counter", "level": 1.0},
  "away": {"formation": "4-4-2", "style": "balanced", "level": 1.0},
  "situation": {
    "start": "home counter-attack",
    "template": "counter",
    "ball_owner": "home",
    "ends_when": "possession_change",
    "wanted": ["ends_in_shot"]
  },
  "seeds": 50
}
```

- `mode`: `situation` (one play) or `full_match`.
- `home` / `away`: formation (4-4-2, 4-3-3, 4-2-3-1, 4-1-4-1, 3-5-2, 3-4-3, 5-3-2, 5-4-1), style (`high_press`, `counter`, `possession`, `balanced`) and AI level (0 to 1).
- `template`: where the 22 players and the ball start (`counter`, `wing_attack_right`, `wing_attack_left`, `build_up`).
- `ends_when`: `goal`, `possession_change`, `out_of_play` or `steps`.
- `wanted`: filters (`ends_in_shot`, `ends_in_goal`, `goal_by:<name>`, `goal_by_team:<side>`) and rankings (`more_pressure:<side>`, `more_possession:<side>`).

## End-to-end flow

1. The person writes: "a home counter-attack that ends in a shot".
2. The agent calls `get_catalog`, drafts the recipe above and calls `validate_recipe`.
3. The UI shows the recipe; the person can tweak it or ask for changes.
4. The agent calls `run_search`: 50 seeds without video, ~25 s with 4 processes.
5. Each seed is evaluated: did it end in a shot? Seeds that pass are ranked; ties go to the lowest seed.
6. The winner is rendered with video (~80 s) and checked: its tracking must be byte-identical to the run without video.
7. The agent answers from the report, e.g.: "Seed 13: Brackenford broke from their own half and shot twice. 4 of 50 attempts ended in a shot." (This matches a real run of this recipe: winner seed 13, 4 of 50 seeds with a shot, 2 shots by the home team.)

Measured outcome rates per situation: a shot in 8–18 % of seeds, a goal in 1–4 %. A goal therefore needs ~200 seeds (~80 s of search).

## Output

The winning match is published as a **match package** in the data contract (`docs/contracts.md`), which every later stage reads:

```
recipe_situation_13/
  video.mp4            the play, 10 fps, 1280×720
  tracking.jsonl       positions and velocities of the 22 players and the ball, per frame
  events.jsonl         passes, tackles, shots, goals, set pieces (inferred from positions)
  events_summary.json  totals per team
  roster.json          players: id, name, shirt number, role
  meta.json            teams, pitch size, source, formations
  recipe.json          the recipe that produced it
  search_report.json   how it was chosen
```

`search_report.json` records the whole search, so every answer is traceable (shape shown, values illustrative):

```json
{
  "recipe": {"...": "..."},
  "seeds": [0, 1, 2, "..."],
  "results": [
    {"seed": 13, "rows": 98, "shots": 2, "goals": 0, "ok": true, "missing": [], "score": 0.0,
     "tracking_sha256": "..."}
  ],
  "winner": 13,
  "elapsed_s": 79.4,
  "render_matches_headless": true
}
```

## What it can and cannot do

| Request | Supported | How |
|---|---|---|
| "End in a shot / a goal" | Yes | Pick the seed by its events |
| "A goal by Mossvane", "a home goal" | Yes | Filter by scorer or team |
| "More pressure", "more possession" | Yes | Style preset, plus ranking seeds by the measured metric |
| "Away side comes back", "goal in the 88th" (full match) | Yes, slower | Search over full matches without video (~32 s each) |
| "A headed goal", "a bicycle kick" | Not yet | Shot type is not detected |
| "Mossvane dribbles past three and scores" | No | That would script the play, which the agent never does |

## Connections

- **Microsoft Foundry:** hosts the model the agent reasons with.
- **Microsoft Agent Framework:** runs the agent and its tool calls.
- **MCP:** exposes the tools to other agents and clients.
- **Azure Container Apps Job:** runs the match factory on demand and scales to zero.
- **Azure Blob Storage:** stores the match packages that the API serves.
- **Later stages (Interpret, Explain, Render, Personalize):** read only the match package, never the agent or the engine.
