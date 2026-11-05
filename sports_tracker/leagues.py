"""Definitions for every league the tracker supports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LeagueKind(Enum):
    TEAM = "team"
    COMBAT = "combat"
    FANTASY = "fantasy"


@dataclass(frozen=True)
class League:
    """A league and the ESPN path segments used to query it.

    ``groups`` is the ESPN conference group that widens a college scoreboard
    from the featured games to the full division (80 = FBS, 50 = Division I).
    """

    key: str
    name: str
    kind: LeagueKind
    sport: str | None = None
    slug: str | None = None
    groups: str | None = None

    @property
    def is_college(self) -> bool:
        return self.groups is not None


LEAGUES: dict[str, League] = {
    "nfl": League("nfl", "NFL", LeagueKind.TEAM, "football", "nfl"),
    "nba": League("nba", "NBA", LeagueKind.TEAM, "basketball", "nba"),
    "ncaaf": League(
        "ncaaf", "NCAA Football", LeagueKind.TEAM, "football", "college-football", groups="80"
    ),
    "ncaab": League(
        "ncaab",
        "NCAA Men's Basketball",
        LeagueKind.TEAM,
        "basketball",
        "mens-college-basketball",
        groups="50",
    ),
    "ufc": League("ufc", "UFC", LeagueKind.COMBAT, "mma", "ufc"),
    "boxing": League("boxing", "Boxing", LeagueKind.COMBAT, "boxing", "boxing"),
    "fantasy": League("fantasy", "Fantasy Football", LeagueKind.FANTASY),
}


def get_league(key: str) -> League:
    try:
        return LEAGUES[key.lower()]
    except KeyError as exc:
        valid = ", ".join(LEAGUES)
        raise ValueError(f"Unknown league '{key}'. Choose from: {valid}") from exc
