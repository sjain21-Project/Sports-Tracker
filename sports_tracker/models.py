"""Data models shared by the providers and the renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GameState(Enum):
    LIVE = "live"
    SCHEDULED = "scheduled"
    FINAL = "final"
    POSTPONED = "postponed"
    CANCELED = "canceled"

    @property
    def sort_order(self) -> int:
        """Live events first, then upcoming, then finished or called off."""
        return {
            GameState.LIVE: 0,
            GameState.SCHEDULED: 1,
            GameState.FINAL: 2,
            GameState.POSTPONED: 3,
            GameState.CANCELED: 4,
        }[self]


@dataclass(frozen=True)
class TeamScore:
    name: str
    abbreviation: str
    score: str | None = None
    record: str | None = None
    rank: int | None = None
    winner: bool = False

    @property
    def label(self) -> str:
        """Team name with its poll ranking, the way college scoreboards show it."""
        return f"{self.rank} {self.name}" if self.rank else self.name


@dataclass(frozen=True)
class Game:
    id: str
    league: str
    start: datetime | None
    state: GameState
    status: str
    away: TeamScore
    home: TeamScore
    broadcast: str | None = None
    situation: str | None = None

    def involves(self, query: str) -> bool:
        query = query.lower()
        return any(
            query in value.lower()
            for team in (self.away, self.home)
            for value in (team.name, team.abbreviation)
        )


@dataclass(frozen=True)
class Fighter:
    name: str
    record: str | None = None
    winner: bool = False


@dataclass(frozen=True)
class Bout:
    id: str
    red: Fighter
    blue: Fighter
    state: GameState
    status: str
    weight_class: str | None = None
    segment: str | None = None
    result: str | None = None

    def involves(self, query: str) -> bool:
        query = query.lower()
        return query in self.red.name.lower() or query in self.blue.name.lower()


@dataclass(frozen=True)
class FightCard:
    id: str
    name: str
    start: datetime | None
    state: GameState
    status: str
    venue: str | None = None
    bouts: tuple[Bout, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FantasyTeam:
    roster_id: int
    name: str
    owner: str
    points: float


@dataclass(frozen=True)
class FantasyMatchup:
    matchup_id: int | None
    teams: tuple[FantasyTeam, ...]

    @property
    def leader(self) -> FantasyTeam | None:
        if len(self.teams) != 2 or self.teams[0].points == self.teams[1].points:
            return None
        return max(self.teams, key=lambda team: team.points)

    def involves(self, query: str) -> bool:
        query = query.lower()
        return any(query in t.name.lower() or query in t.owner.lower() for t in self.teams)


@dataclass(frozen=True)
class FantasyScoreboard:
    league_name: str
    season: str
    week: int
    matchups: tuple[FantasyMatchup, ...]
