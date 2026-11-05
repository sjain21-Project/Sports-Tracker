from sports_tracker.leagues import LEAGUES
from sports_tracker.models import GameState
from sports_tracker.providers.espn import (
    COLLEGE_RESULT_LIMIT,
    EspnProvider,
    parse_fight_cards,
    parse_games,
    parse_state,
)


def test_games_are_sorted_live_then_upcoming_then_final(fixture):
    games = parse_games(fixture("espn_nfl.json"), "nfl")

    assert [game.state for game in games] == [
        GameState.LIVE,
        GameState.SCHEDULED,
        GameState.FINAL,
        GameState.POSTPONED,
    ]


def test_final_game_marks_the_winner(fixture):
    final = next(g for g in parse_games(fixture("espn_nfl.json"), "nfl") if g.id == "401")

    assert final.home.name == "Chiefs"
    assert final.home.score == "27"
    assert final.home.winner is True
    assert final.away.winner is False
    assert final.away.record == "6-2"


def test_live_football_game_includes_possession_and_down(fixture):
    live = next(g for g in parse_games(fixture("espn_nfl.json"), "nfl") if g.id == "402")

    assert live.status == "8:12 - 3rd"
    assert live.situation == "GB ball, 3rd & 4"


def test_broadcast_names_are_joined(fixture):
    upcoming = next(g for g in parse_games(fixture("espn_nfl.json"), "nfl") if g.id == "403")

    assert upcoming.broadcast == "NBC, Peacock"
    assert upcoming.situation is None


def test_college_rankings_ignore_unranked_placeholder(fixture):
    game = parse_games(fixture("espn_ncaab.json"), "ncaab")[0]

    assert game.home.label == "3 Duke"
    assert game.away.rank is None
    assert game.away.label == "Kentucky"


def test_team_filter_matches_name_or_abbreviation(fixture):
    game = parse_games(fixture("espn_nfl.json"), "nfl")[0]

    assert game.involves("packers")
    assert game.involves("det")
    assert not game.involves("cowboys")


def test_fight_card_parses_bouts_and_results(fixture):
    card = parse_fight_cards(fixture("espn_ufc.json"))[0]

    assert card.venue == "T-Mobile Arena"
    assert card.state is GameState.LIVE
    assert len(card.bouts) == 2  # the malformed single-fighter bout is skipped

    finished, live = card.bouts
    assert finished.red.name == "Alex Moreno"
    assert finished.red.winner is True
    assert finished.result == "KO/TKO R2 3:41"
    assert finished.weight_class == "Lightweight"
    assert live.state is GameState.LIVE
    assert live.result is None


def test_fighters_are_ordered_by_corner(fixture):
    live = parse_fight_cards(fixture("espn_ufc.json"))[0].bouts[1]

    assert live.red.name == "Marcus Reed"
    assert live.blue.name == "Dmitri Volkov"


def test_parse_state_handles_canceled_and_missing_data():
    assert parse_state({"type": {"name": "STATUS_CANCELED", "state": "post"}}) is GameState.CANCELED
    assert parse_state({}) is GameState.SCHEDULED


def test_empty_payload_returns_no_games():
    assert parse_games({}, "nba") == []
    assert parse_fight_cards({"events": []}) == []


def test_scoreboard_request_for_full_college_slate(fake_client):
    client = fake_client({"/college-football/scoreboard": {"events": []}})
    EspnProvider(client).games(LEAGUES["ncaaf"], date="20261107", all_games=True)

    url, params = client.calls[0]
    assert url.endswith("/football/college-football/scoreboard")
    assert params == {"dates": "20261107", "groups": "80", "limit": COLLEGE_RESULT_LIMIT}


def test_pro_scoreboard_ignores_all_games_flag(fake_client):
    client = fake_client({"/nba/scoreboard": {"events": []}})
    EspnProvider(client).games(LEAGUES["nba"], all_games=True)

    assert client.calls[0][1] is None
