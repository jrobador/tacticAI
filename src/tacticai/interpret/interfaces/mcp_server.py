"""MCP server (stdio) exposing the Stats Tools over a matches root. Thin wrappers: all logic lives in application/stats_tools.py."""
from mcp.server.fastmcp import FastMCP

from ..application import stats_tools as t


def build(root):
    m = FastMCP("tacticai-stats")

    @m.tool()
    def list_matches() -> dict:
        """Matches under the root: ids, teams, score, quality level."""
        return t.list_matches(root)

    @m.tool()
    def match_summary(match_id: str, until_t_s: float | None = None) -> dict:
        """Score, possession %, xG, shots, open-play seconds as of until_t_s; quality/projection/calibration are full-match."""
        return t.match_summary(root, match_id, until_t_s)

    @m.tool()
    def team_stats(match_id: str, team: str, until_t_s: float | None = None) -> dict:
        """Team passes, completion, progressive passes, lines broken, shots, xG, goals, tackles, interceptions, sequences, mean pressure up to until_t_s."""
        return t.team_stats(root, match_id, team, until_t_s)

    @m.tool()
    def player_stats(match_id: str, player_id: str, until_t_s: float | None = None) -> dict:
        """Player counts up to until_t_s plus name/number/role; rating and physical are full-match only (flagged, relative when not absolute)."""
        return t.player_stats(root, match_id, player_id, until_t_s)

    @m.tool()
    def top_players(match_id: str, metric: str, n: int = 5, until_t_s: float | None = None) -> dict:
        """Top n players by metric (lines_broken, progressive_passes, xg, goals, tackles, interceptions, passes, completion_pct, rating, distance_rank, top_speed_rank)."""
        return t.top_players(root, match_id, metric, n, until_t_s)

    @m.tool()
    def events(match_id: str, type: str | None = None, team: str | None = None, player_id: str | None = None, from_t_s: float | None = None,
               until_t_s: float | None = None, limit: int = 50) -> dict:
        """Enriched events filtered by type/team/player/time range."""
        return t.events(root, match_id, type, team, player_id, from_t_s, until_t_s, limit)

    @m.tool()
    def sequences(match_id: str, team: str | None = None, end_cause: str | None = None, min_lines_broken: int | None = None,
                  until_t_s: float | None = None, limit: int = 50) -> dict:
        """Possession sequences that ended by until_t_s, filtered by team/end_cause/min lines broken."""
        return t.sequences(root, match_id, team, end_cause, min_lines_broken, until_t_s, limit)

    @m.tool()
    def timeline(match_id: str, from_t_s: float | None = None, until_t_s: float | None = None) -> dict:
        """Timeline windows overlapping [from_t_s, until_t_s]."""
        return t.timeline(root, match_id, from_t_s, until_t_s)

    @m.tool()
    def shot_map(match_id: str, team: str | None = None, until_t_s: float | None = None) -> dict:
        """Shots with x, y, xG, outcome and player."""
        return t.shot_map(root, match_id, team, until_t_s)

    @m.tool()
    def pressure_windows(match_id: str, team: str, until_t_s: float | None = None, top: int = 3) -> dict:
        """Windows sorted by the team's pressure, highest first."""
        return t.pressure_windows(root, match_id, team, until_t_s, top)

    @m.tool()
    def quality(match_id: str) -> dict:
        """Tracking quality summary (full match)."""
        return t.quality(root, match_id)

    return m


def run(root):
    build(root).run("stdio")
