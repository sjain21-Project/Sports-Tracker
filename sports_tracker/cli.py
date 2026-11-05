"""Command line entry point."""

from __future__ import annotations

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.rule import Rule

from sports_tracker import __version__
from sports_tracker.client import ApiError
from sports_tracker.leagues import LEAGUES, League, LeagueKind, get_league
from sports_tracker.models import FantasyScoreboard, GameState
from sports_tracker.providers import EspnProvider, SleeperProvider
from sports_tracker.render import (
    empty_panel,
    error_panel,
    fantasy_table,
    fight_cards_view,
    format_time,
    games_table,
)

MIN_INTERVAL = 10
DEFAULT_INTERVAL = 30
LEAGUE_ENV_VAR = "SLEEPER_LEAGUE_ID"


@dataclass(frozen=True)
class Options:
    leagues: tuple[League, ...]
    date: str | None = None
    team: str | None = None
    all_games: bool = False
    live_only: bool = False
    league_id: str | None = None
    week: int | None = None


class Tracker:
    """Fetches every selected league and assembles one renderable view."""

    def __init__(
        self,
        options: Options,
        espn: EspnProvider | None = None,
        sleeper: SleeperProvider | None = None,
    ) -> None:
        self.options = options
        self.espn = espn or EspnProvider()
        self.sleeper = sleeper or SleeperProvider()

    def render(self) -> RenderableType:
        with ThreadPoolExecutor(max_workers=len(self.options.leagues)) as pool:
            sections = list(pool.map(self.render_league, self.options.leagues))
        return Group(*sections)

    def render_league(self, league: League) -> RenderableType:
        try:
            if league.kind is LeagueKind.TEAM:
                return games_table(league, self._games(league))
            if league.kind is LeagueKind.COMBAT:
                return fight_cards_view(league, self._fight_cards(league))
            return self._fantasy(league)
        except ApiError as exc:
            if exc.status_code == 404:
                return empty_panel(league.name, "No events are listed right now.")
            return error_panel(league.name, str(exc))

    def _games(self, league: League):
        games = self.espn.games(league, self.options.date, self.options.all_games)
        if self.options.team:
            games = [game for game in games if game.involves(self.options.team)]
        if self.options.live_only:
            games = [game for game in games if game.state is GameState.LIVE]
        return games

    def _fight_cards(self, league: League):
        cards = self.espn.fight_cards(league, self.options.date)
        if self.options.team:
            cards = [
                replace(card, bouts=tuple(b for b in card.bouts if b.involves(self.options.team)))
                for card in cards
            ]
            cards = [card for card in cards if card.bouts]
        if self.options.live_only:
            cards = [card for card in cards if card.state is GameState.LIVE]
        return cards

    def _fantasy(self, league: League) -> RenderableType:
        if not self.options.league_id:
            return empty_panel(
                league.name,
                f"Pass --league-id or set {LEAGUE_ENV_VAR} to follow a Sleeper league.",
            )
        scoreboard = self.sleeper.scoreboard(self.options.league_id, self.options.week)
        if self.options.team:
            matchups = tuple(m for m in scoreboard.matchups if m.involves(self.options.team))
            scoreboard = FantasyScoreboard(
                scoreboard.league_name, scoreboard.season, scoreboard.week, matchups
            )
        return fantasy_table(scoreboard)


def parse_date(value: str) -> str:
    """Accept YYYY-MM-DD or YYYYMMDD and return the YYYYMMDD form ESPN expects."""
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"invalid date '{value}', use YYYY-MM-DD")


def parse_interval(value: str) -> int:
    try:
        seconds = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be a whole number of seconds") from exc
    if seconds < MIN_INTERVAL:
        raise argparse.ArgumentTypeError(f"interval must be at least {MIN_INTERVAL} seconds")
    return seconds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sports-tracker",
        description="Live scores for the NFL, NBA, NCAA, UFC, boxing and Sleeper fantasy leagues.",
    )
    parser.add_argument(
        "leagues",
        nargs="*",
        metavar="LEAGUE",
        help=f"one or more of: {', '.join(LEAGUES)}, all (default: all)",
    )
    parser.add_argument("-l", "--live", action="store_true", help="keep refreshing the scores")
    parser.add_argument(
        "-i",
        "--interval",
        type=parse_interval,
        default=DEFAULT_INTERVAL,
        help=f"seconds between refreshes in live mode (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument("-d", "--date", type=parse_date, help="show a specific date (YYYY-MM-DD)")
    parser.add_argument("-t", "--team", help="only show games involving this team or fighter")
    parser.add_argument(
        "--in-progress",
        dest="live_only",
        action="store_true",
        help="only show events that are currently in progress",
    )
    parser.add_argument(
        "--all-games",
        action="store_true",
        help="show every Division I college game instead of ESPN's featured list",
    )
    parser.add_argument(
        "--league-id",
        default=os.environ.get(LEAGUE_ENV_VAR),
        help=f"Sleeper fantasy league ID (or set {LEAGUE_ENV_VAR})",
    )
    parser.add_argument("--week", type=int, help="fantasy week to show (default: current week)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def resolve_leagues(names: list[str], league_id: str | None) -> tuple[League, ...]:
    if not names or "all" in (name.lower() for name in names):
        selected = [league for league in LEAGUES.values() if league.kind is not LeagueKind.FANTASY]
        if league_id:
            selected.append(LEAGUES["fantasy"])
        return tuple(selected)
    return tuple(dict.fromkeys(get_league(name) for name in names))


def header(interval: int | None = None) -> RenderableType:
    updated = f"Updated {format_time(datetime.now().astimezone(), with_day=False)}"
    if interval:
        updated += f", refreshing every {interval}s (Ctrl+C to quit)"
    return Rule(updated, style="dim", align="right")


def run_live(tracker: Tracker, console: Console, interval: int) -> None:
    def frame() -> RenderableType:
        return Group(header(interval), tracker.render())

    with Live(frame(), console=console, auto_refresh=False, screen=False) as live:
        while True:
            time.sleep(interval)
            live.update(frame(), refresh=True)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        leagues = resolve_leagues(args.leagues, args.league_id)
    except ValueError as exc:
        parser.error(str(exc))

    options = Options(
        leagues=leagues,
        date=args.date,
        team=args.team,
        all_games=args.all_games,
        live_only=args.live_only,
        league_id=args.league_id,
        week=args.week,
    )
    console = Console()
    tracker = Tracker(options)

    try:
        if args.live:
            run_live(tracker, console, args.interval)
        else:
            console.print(header())
            console.print(tracker.render())
    except KeyboardInterrupt:
        console.print("[dim]Stopped.[/dim]")
    return 0
