from sports_tracker.providers.sleeper import SleeperProvider, build_matchups


def test_matchups_pair_teams_and_resolve_names(fixture):
    data = fixture("sleeper.json")
    matchups = build_matchups(data["matchups"], data["rosters"], data["users"])

    first = matchups[0]
    assert [team.name for team in first.teams] == ["Fourth and Long", "rival"]
    assert first.teams[0].owner == "samyak"
    assert first.leader.name == "Fourth and Long"


def test_custom_points_override_and_ties(fixture):
    data = fixture("sleeper.json")
    second = build_matchups(data["matchups"], data["rosters"], data["users"])[1]

    assert [team.points for team in second.teams] == [101.5, 101.5]
    assert second.leader is None
    assert second.teams[1].name == "Team 4"
    assert second.teams[1].owner == "Unclaimed"


def test_teams_without_matchup_are_listed_last(fixture):
    data = fixture("sleeper.json")
    matchups = build_matchups(data["matchups"], data["rosters"], data["users"])

    assert matchups[-1].matchup_id is None
    assert len(matchups[-1].teams) == 1


def test_scoreboard_uses_current_week_when_not_given(fixture, fake_client):
    data = fixture("sleeper.json")
    client = fake_client(
        {
            "/state/nfl": data["state"],
            "/league/123": data["league"],
            "/league/123/matchups/9": data["matchups"],
            "/league/123/rosters": data["rosters"],
            "/league/123/users": data["users"],
        }
    )
    scoreboard = SleeperProvider(client).scoreboard("123")

    assert scoreboard.week == 9
    assert scoreboard.league_name == "Office League"
    assert len(scoreboard.matchups) == 3
