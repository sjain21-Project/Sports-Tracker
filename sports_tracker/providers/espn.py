"""Scoreboard data from ESPN's public site API.

ESPN does not publish documentation for these endpoints, so every field is
read defensively: a missing key degrades the display rather than crashing it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sports_tracker.client import HttpClient
from sports_tracker.leagues import League, LeagueKind
from sports_tracker.models import Bout, FightCard, Fighter, Game, GameState, TeamScore

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
COLLEGE_RESULT_LIMIT = 400

_CANCELED = {"STATUS_CANCELED", "STATUS_FORFEIT"}
_POSTPONED = {"STATUS_POSTPONED", "STATUS_SUSPENDED"}


class EspnProvider:
    def __init__(self, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient()

    def scoreboard(
        self, league: League, date: str | None = None, all_games: bool = False
    ) -> dict[str, Any]:
        if league.kind is LeagueKind.FANTASY:
            raise ValueError("Fantasy leagues are served by the Sleeper provider.")

        params: dict[str, Any] = {}
        if date:
            params["dates"] = date
        if all_games and league.is_college:
            params["groups"] = league.groups
            params["limit"] = COLLEGE_RESULT_LIMIT

        url = f"{BASE_URL}/{league.sport}/{league.slug}/scoreboard"
        return self.client.get_json(url, params=params or None)

    def games(self, league: League, date: str | None = None, all_games: bool = False) -> list[Game]:
        return parse_games(self.scoreboard(league, date, all_games), league.key)

    def fight_cards(self, league: League, date: str | None = None) -> list[FightCard]:
        return parse_fight_cards(self.scoreboard(league, date))


def parse_games(payload: dict[str, Any], league_key: str) -> list[Game]:
    games = []
    for event in payload.get("events", []):
        competition = _first(event.get("competitions"))
        if competition is None:
            continue

        teams = {c.get("homeAway"): _parse_team(c) for c in competition.get("competitors", [])}
        if "home" not in teams or "away" not in teams:
            continue

        status = competition.get("status") or event.get("status") or {}
        state = parse_state(status)
        games.append(
            Game(
                id=str(event.get("id", "")),
                league=league_key,
                start=parse_datetime(event.get("date")),
                state=state,
                status=status_text(status),
                away=teams["away"],
                home=teams["home"],
                broadcast=_parse_broadcast(competition),
                situation=_parse_situation(competition) if state is GameState.LIVE else None,
            )
        )

    return sorted(games, key=_event_sort_key)


def parse_fight_cards(payload: dict[str, Any]) -> list[FightCard]:
    cards = []
    for event in payload.get("events", []):
        status = event.get("status") or {}
        bouts = tuple(
            bout
            for competition in event.get("competitions", [])
            if (bout := _parse_bout(competition, status)) is not None
        )
        venue = _first(event.get("venues")) or _first(
            [c.get("venue") for c in event.get("competitions", []) if c.get("venue")]
        )
        cards.append(
            FightCard(
                id=str(event.get("id", "")),
                name=event.get("name") or event.get("shortName") or "Fight Card",
                start=parse_datetime(event.get("date")),
                state=parse_state(status),
                status=status_text(status),
                venue=(venue or {}).get("fullName"),
                bouts=bouts,
            )
        )

    return sorted(cards, key=_event_sort_key)


def parse_state(status: dict[str, Any]) -> GameState:
    status_type = status.get("type") or {}
    name = status_type.get("name", "")
    if name in _CANCELED:
        return GameState.CANCELED
    if name in _POSTPONED:
        return GameState.POSTPONED

    state = status_type.get("state")
    if state == "in":
        return GameState.LIVE
    if state == "post" or status_type.get("completed"):
        return GameState.FINAL
    return GameState.SCHEDULED


def status_text(status: dict[str, Any]) -> str:
    status_type = status.get("type") or {}
    return (
        status_type.get("shortDetail")
        or status_type.get("detail")
        or status_type.get("description")
        or ""
    )


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ESPN timestamps such as ``2026-11-05T00:30Z``."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_team(competitor: dict[str, Any]) -> TeamScore:
    team = competitor.get("team") or {}
    record = _first(competitor.get("records")) or {}
    rank = (competitor.get("curatedRank") or {}).get("current")
    return TeamScore(
        name=team.get("shortDisplayName") or team.get("displayName") or "TBD",
        abbreviation=team.get("abbreviation") or "",
        score=competitor.get("score"),
        record=record.get("summary"),
        # ESPN reports unranked college teams as rank 99.
        rank=rank if isinstance(rank, int) and 0 < rank <= 25 else None,
        winner=bool(competitor.get("winner")),
    )


def _parse_bout(competition: dict[str, Any], card_status: dict[str, Any]) -> Bout | None:
    competitors = sorted(competition.get("competitors", []), key=lambda c: c.get("order", 0))
    if len(competitors) != 2:
        return None

    status = competition.get("status") or card_status
    state = parse_state(status)
    bout_type = competition.get("type") or {}
    segment = competition.get("cardSegment") or {}
    return Bout(
        id=str(competition.get("id", "")),
        red=_parse_fighter(competitors[0]),
        blue=_parse_fighter(competitors[1]),
        state=state,
        status=status_text(status),
        weight_class=bout_type.get("text") or bout_type.get("abbreviation"),
        segment=segment.get("description") or segment.get("name"),
        result=_parse_result(status) if state is GameState.FINAL else None,
    )


def _parse_fighter(competitor: dict[str, Any]) -> Fighter:
    athlete = competitor.get("athlete") or {}
    record = _first(competitor.get("records")) or {}
    return Fighter(
        name=athlete.get("displayName") or athlete.get("fullName") or "TBD",
        record=record.get("summary"),
        winner=bool(competitor.get("winner")),
    )


def _parse_result(status: dict[str, Any]) -> str | None:
    """Build a result line such as ``KO/TKO R2 3:41`` from a finished bout."""
    result = status.get("result") or {}
    method = result.get("shortDisplayName") or result.get("displayName")
    if not method:
        return None

    parts = [method]
    if status.get("period"):
        parts.append(f"R{status['period']}")
    if status.get("displayClock"):
        parts.append(status["displayClock"])
    return " ".join(parts)


def _parse_broadcast(competition: dict[str, Any]) -> str | None:
    names = [
        name
        for broadcast in competition.get("broadcasts", [])
        for name in broadcast.get("names", [])
    ]
    return ", ".join(dict.fromkeys(names)) or None


def _parse_situation(competition: dict[str, Any]) -> str | None:
    """Down and distance with the team in possession, for live football."""
    situation = competition.get("situation") or {}
    down_distance = situation.get("shortDownDistanceText") or situation.get("downDistanceText")
    if not down_distance:
        return None

    possession_id = situation.get("possession")
    for competitor in competition.get("competitors", []):
        team = competitor.get("team") or {}
        if possession_id and str(team.get("id")) == str(possession_id):
            return f"{team.get('abbreviation', '')} ball, {down_distance}".strip(", ")
    return down_distance


def _event_sort_key(event: Game | FightCard) -> tuple[int, float]:
    timestamp = event.start.timestamp() if event.start else float("inf")
    return event.state.sort_order, timestamp


def _first(items: list[Any] | None) -> Any:
    return items[0] if items else None
