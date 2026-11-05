"""Fantasy football matchups from the Sleeper public API (no API key required)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sports_tracker.client import HttpClient
from sports_tracker.models import FantasyMatchup, FantasyScoreboard, FantasyTeam

BASE_URL = "https://api.sleeper.app/v1"


class SleeperProvider:
    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient()

    def _get(self, path: str) -> Any:
        return self.client.get_json(f"{BASE_URL}/{path}")

    def current_week(self) -> int:
        state = self._get("state/nfl") or {}
        return int(state.get("display_week") or state.get("week") or 1)

    def scoreboard(self, league_id: str, week: int | None = None) -> FantasyScoreboard:
        league = self._get(f"league/{league_id}") or {}
        week = week or self.current_week()
        matchups = self._get(f"league/{league_id}/matchups/{week}") or []
        rosters = self._get(f"league/{league_id}/rosters") or []
        users = self._get(f"league/{league_id}/users") or []

        return FantasyScoreboard(
            league_name=league.get("name") or "Fantasy League",
            season=str(league.get("season") or ""),
            week=week,
            matchups=build_matchups(matchups, rosters, users),
        )


def build_matchups(
    matchups: list[dict[str, Any]],
    rosters: list[dict[str, Any]],
    users: list[dict[str, Any]],
) -> tuple[FantasyMatchup, ...]:
    """Pair each roster with its weekly opponent using the shared ``matchup_id``."""
    users_by_id = {user.get("user_id"): user for user in users}
    owners_by_roster = {roster.get("roster_id"): roster.get("owner_id") for roster in rosters}

    grouped: dict[int | None, list[FantasyTeam]] = defaultdict(list)
    for entry in matchups:
        roster_id = entry.get("roster_id")
        user = users_by_id.get(owners_by_roster.get(roster_id)) or {}
        grouped[entry.get("matchup_id")].append(
            FantasyTeam(
                roster_id=roster_id,
                name=_team_name(user, roster_id),
                owner=user.get("display_name") or "Unclaimed",
                points=_points(entry),
            )
        )

    paired = [
        FantasyMatchup(matchup_id, tuple(teams))
        for matchup_id, teams in sorted(
            ((k, v) for k, v in grouped.items() if k is not None), key=lambda item: item[0]
        )
    ]
    # Teams without a matchup_id are on a bye or in a median-only week.
    unpaired = [FantasyMatchup(None, (team,)) for team in grouped.get(None, [])]
    return tuple(paired + unpaired)


def _team_name(user: dict[str, Any], roster_id: int | None) -> str:
    metadata = user.get("metadata") or {}
    return metadata.get("team_name") or user.get("display_name") or f"Team {roster_id}"


def _points(entry: dict[str, Any]) -> float:
    # Commissioners can override a score; Sleeper stores that in custom_points.
    value = entry.get("custom_points")
    if value is None:
        value = entry.get("points")
    return round(float(value or 0), 2)
