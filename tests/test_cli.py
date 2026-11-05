import argparse

import pytest
from rich.console import Console

from sports_tracker.cli import Options, Tracker, build_parser, parse_date, resolve_leagues
from sports_tracker.client import ApiError
from sports_tracker.leagues import LEAGUES
from sports_tracker.providers import EspnProvider, SleeperProvider


def render_text(renderable) -> str:
    console = Console(record=True, width=140, color_system=None)
    console.print(renderable)
    return console.export_text()


def test_parse_date_accepts_both_formats():
    assert parse_date("2026-11-04") == "20261104"
    assert parse_date("20261104") == "20261104"
    with pytest.raises(argparse.ArgumentTypeError):
        parse_date("11/04/2026")


def test_interval_has_a_floor():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--interval", "2"])


def test_default_selection_skips_fantasy_without_league_id():
    keys = [league.key for league in resolve_leagues([], None)]
    assert "fantasy" not in keys
    assert {"nfl", "nba", "ncaaf", "ncaab", "ufc", "boxing"} <= set(keys)


def test_default_selection_adds_fantasy_with_league_id():
    keys = [league.key for league in resolve_leagues(["all"], "123")]
    assert keys[-1] == "fantasy"


def test_explicit_leagues_are_deduplicated():
    assert resolve_leagues(["NBA", "nba", "ufc"], None) == (LEAGUES["nba"], LEAGUES["ufc"])


def test_unknown_league_is_rejected():
    with pytest.raises(ValueError):
        resolve_leagues(["mlb"], None)


def test_tracker_renders_scoreboard_and_filters_by_team(fixture, fake_client):
    client = fake_client({"/nfl/scoreboard": fixture("espn_nfl.json")})
    options = Options(leagues=(LEAGUES["nfl"],), team="lions")
    output = render_text(Tracker(options, espn=EspnProvider(client)).render())

    assert "Packers" in output
    assert "GB ball, 3rd & 4" in output
    assert "Chiefs" not in output


def test_tracker_in_progress_only(fixture, fake_client):
    client = fake_client({"/nfl/scoreboard": fixture("espn_nfl.json")})
    options = Options(leagues=(LEAGUES["nfl"],), live_only=True)
    output = render_text(Tracker(options, espn=EspnProvider(client)).render())

    assert "Lions" in output
    assert "Eagles" not in output


def test_tracker_shows_fight_results(fixture, fake_client):
    client = fake_client({"/ufc/scoreboard": fixture("espn_ufc.json")})
    options = Options(leagues=(LEAGUES["ufc"],))
    output = render_text(Tracker(options, espn=EspnProvider(client)).render())

    assert "UFC 330" in output
    assert "Moreno by KO/TKO R2 3:41" in output


def test_one_failing_league_does_not_break_the_others(fixture, fake_client):
    client = fake_client(
        {
            "/nba/scoreboard": ApiError("Request failed with status 503.", 503),
            "/boxing/scoreboard": ApiError("No data", 404),
            "/nfl/scoreboard": fixture("espn_nfl.json"),
        }
    )
    options = Options(leagues=(LEAGUES["nba"], LEAGUES["boxing"], LEAGUES["nfl"]))
    output = render_text(Tracker(options, espn=EspnProvider(client)).render())

    assert "status 503" in output
    assert "No events are listed right now." in output
    assert "Chiefs" in output


def test_fantasy_without_league_id_explains_setup():
    options = Options(leagues=(LEAGUES["fantasy"],))
    output = render_text(Tracker(options).render())

    assert "--league-id" in output


def test_fantasy_scoreboard_renders(fixture, fake_client):
    data = fixture("sleeper.json")
    client = fake_client(
        {
            "/league/42": data["league"],
            "/league/42/matchups/9": data["matchups"],
            "/league/42/rosters": data["rosters"],
            "/league/42/users": data["users"],
        }
    )
    options = Options(leagues=(LEAGUES["fantasy"],), league_id="42", week=9)
    output = render_text(Tracker(options, sleeper=SleeperProvider(client)).render())

    assert "Office League (2026 Week 9)" in output
    assert "Fourth and Long" in output
    assert "14.36" in output
    assert "Tied" in output
    assert "Bye" in output
