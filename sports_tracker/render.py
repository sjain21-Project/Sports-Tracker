"""Turns parsed scoreboard data into Rich tables for the terminal."""

from __future__ import annotations

from datetime import datetime

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sports_tracker.leagues import League
from sports_tracker.models import (
    Bout,
    FantasyScoreboard,
    FantasyTeam,
    FightCard,
    Fighter,
    Game,
    GameState,
    TeamScore,
)

STATE_STYLES = {
    GameState.LIVE: "bold green",
    GameState.SCHEDULED: "cyan",
    GameState.FINAL: "dim",
    GameState.POSTPONED: "yellow",
    GameState.CANCELED: "red",
}


def format_time(value: datetime | None, with_day: bool = True) -> str:
    """Format a timestamp in the user's local time zone, e.g. ``Wed 7:30 PM``."""
    if value is None:
        return "TBD"
    local = value.astimezone()
    hour = local.hour % 12 or 12
    clock = f"{hour}:{local:%M} {local:%p}"
    return f"{local:%a} {clock}" if with_day else clock


def games_table(league: League, games: list[Game]) -> RenderableType:
    if not games:
        return empty_panel(league.name, "No games on the schedule.")

    table = Table(title=league.name, title_justify="left", box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Away", ratio=3)
    table.add_column("", justify="right", no_wrap=True)
    table.add_column("Home", ratio=3)
    table.add_column("", justify="right", no_wrap=True)
    table.add_column("Details", ratio=3, style="dim")

    for game in games:
        table.add_row(
            _status_cell(game.state, game.status),
            _team_cell(game.away),
            _score_cell(game.away, game.state),
            _team_cell(game.home),
            _score_cell(game.home, game.state),
            _game_details(game),
        )
    return table


def fight_cards_view(league: League, cards: list[FightCard]) -> RenderableType:
    if not cards:
        return empty_panel(league.name, "No fight cards on the schedule.")

    sections: list[RenderableType] = []
    for card in cards:
        details = " | ".join(
            part for part in (format_time(card.start), card.venue, card.status) if part
        )
        sections.append(Text(f"{league.name}: {card.name}", style="bold"))
        sections.append(Text(details, style="dim"))
        table = Table(box=box.SIMPLE_HEAD, expand=True)
        table.add_column("Card", style="dim", no_wrap=True)
        table.add_column("Division", style="dim")
        table.add_column("Fighter", ratio=3)
        table.add_column("Opponent", ratio=3)
        table.add_column("Result", ratio=2)

        for bout in card.bouts:
            table.add_row(
                bout.segment or "",
                bout.weight_class or "",
                _fighter_cell(bout.red),
                _fighter_cell(bout.blue),
                _bout_result(bout),
            )
        if not card.bouts:
            table.add_row("", "", Text("Bouts not announced yet.", style="dim"), "", "")
        sections.append(table)
    return Group(*sections)


def fantasy_table(scoreboard: FantasyScoreboard) -> RenderableType:
    title = f"Fantasy Football: {scoreboard.league_name}"
    if not scoreboard.matchups:
        return empty_panel(title, f"No matchups found for week {scoreboard.week}.")

    table = Table(
        title=f"{title} ({scoreboard.season} Week {scoreboard.week})",
        title_justify="left",
        box=box.SIMPLE_HEAD,
        expand=True,
    )
    table.add_column("Team", ratio=3)
    table.add_column("Pts", justify="right", no_wrap=True)
    table.add_column("Opponent", ratio=3)
    table.add_column("Pts", justify="right", no_wrap=True)
    table.add_column("Margin", justify="right", style="dim", no_wrap=True)

    for matchup in scoreboard.matchups:
        leader = matchup.leader
        if len(matchup.teams) == 1:
            team = matchup.teams[0]
            table.add_row(
                _fantasy_team_cell(team, False), f"{team.points:.2f}", Text("Bye", "dim"), "", ""
            )
            continue

        first, second = matchup.teams[:2]
        margin = f"{abs(first.points - second.points):.2f}" if leader else "Tied"
        table.add_row(
            _fantasy_team_cell(first, leader == first),
            _points_cell(first, leader == first),
            _fantasy_team_cell(second, leader == second),
            _points_cell(second, leader == second),
            margin,
        )
    return table


def error_panel(title: str, message: str) -> Panel:
    return Panel(Text(message, style="red"), title=title, title_align="left", border_style="red")


def empty_panel(title: str, message: str) -> Panel:
    return Panel(Text(message, style="dim"), title=title, title_align="left", border_style="dim")


def _status_cell(state: GameState, status: str) -> Text:
    label = status or state.value.title()
    if state is GameState.SCHEDULED:
        label = "Upcoming"
    return Text(label, style=STATE_STYLES[state])


def _team_cell(team: TeamScore) -> Text:
    text = Text(team.label, style="bold" if team.winner else "")
    if team.record:
        text.append(f" ({team.record})", style="dim")
    return text


def _score_cell(team: TeamScore, state: GameState) -> Text:
    if state not in (GameState.LIVE, GameState.FINAL) or team.score is None:
        return Text("-", style="dim")
    return Text(team.score, style="bold" if team.winner else "")


def _game_details(game: Game) -> str:
    if game.state is GameState.LIVE:
        return game.situation or game.broadcast or ""
    if game.state is GameState.SCHEDULED:
        parts = [format_time(game.start), game.broadcast]
        return " on ".join(part for part in parts if part)
    return ""


def _fighter_cell(fighter: Fighter) -> Text:
    text = Text(fighter.name, style="bold green" if fighter.winner else "")
    if fighter.record:
        text.append(f" ({fighter.record})", style="dim")
    return text


def _bout_result(bout: Bout) -> Text:
    if bout.state is GameState.FINAL:
        winner = bout.red if bout.red.winner else bout.blue if bout.blue.winner else None
        if winner is None:
            return Text(bout.result or bout.status or "Final", style="dim")
        detail = f" by {bout.result}" if bout.result else ""
        return Text(f"{winner.name.split()[-1]}{detail}", style="dim")
    return _status_cell(bout.state, bout.status)


def _fantasy_team_cell(team: FantasyTeam, leading: bool) -> Text:
    text = Text(team.name, style="bold" if leading else "")
    if team.owner and team.owner != team.name:
        text.append(f" ({team.owner})", style="dim")
    return text


def _points_cell(team: FantasyTeam, leading: bool) -> Text:
    return Text(f"{team.points:.2f}", style="bold green" if leading else "")
