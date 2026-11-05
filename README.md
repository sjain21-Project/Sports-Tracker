# Sports Tracker

A command line scoreboard that follows live games for the leagues I actually watch: the NFL, NBA, NCAA football, NCAA men's basketball, UFC, boxing, and my Sleeper fantasy football league. It pulls data from ESPN and Sleeper, both of which have public endpoints that don't need an API key, and refreshes in place in the terminal.

```
──────────────────────────────────────────────────────────────── Updated 10:50 PM
NFL

  Status       Away                     Home                    Details
 ─────────────────────────────────────────────────────────────────────────────────
  8:12 - 3rd   Packers (5-3)       14   Lions (6-2)        17   GB ball, 3rd & 4
  Upcoming     Cowboys (5-2)        -   Eagles (5-2)        -   Sun 7:20 PM on NBC
  Final        Bills (6-2)         24   Chiefs (7-1)       27

UFC: UFC 330
Sat 9:00 PM | T-Mobile Arena | In Progress

  Card        Division      Fighter                Opponent                Result
 ─────────────────────────────────────────────────────────────────────────────────
  Prelims     Lightweight   Alex Moreno (14-2-0)   Ben Carter (11-4-0)     Moreno by KO/TKO R2 3:41
  Main Card   Heavyweight   Marcus Reed (18-1-0)   Dmitri Volkov (20-3-0)  R1, 2:10

Fantasy Football: Office League (2026 Week 9)

  Team                         Pts   Opponent                Pts   Margin
 ─────────────────────────────────────────────────────────────────────────────────
  Fourth and Long (samyak)  112.46   rival                 98.10    14.36
```

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/<your-username>/sports-tracker.git
cd sports-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

This installs a `sports-tracker` command. You can also run it with `python -m sports_tracker`.

## Usage

Running it with no arguments prints today's scores for every league once:

```bash
sports-tracker
```

Pick specific leagues and keep the board updating:

```bash
sports-tracker nfl ncaaf --live
sports-tracker nba --live --interval 15
```

League keys are `nfl`, `nba`, `ncaaf`, `ncaab`, `ufc`, `boxing`, `fantasy` and `all`.

Some other options:

```bash
sports-tracker nba --team lakers           # one team (matches name or abbreviation)
sports-tracker ufc --team pereira          # works for fighters too
sports-tracker nfl --date 2026-11-08       # a specific day
sports-tracker all --in-progress --live    # only games happening right now
sports-tracker ncaab --all-games           # full Division I slate
```

By default ESPN only returns featured and ranked games for college sports. `--all-games` asks for the full FBS or Division I list instead, which can be a long table on a Saturday.

Refreshes are limited to one every 10 seconds at the fastest. Press Ctrl+C to stop.

## Fantasy football

Fantasy scores come from [Sleeper](https://sleeper.com). You need your league ID, which is the number in the URL when you open the league in a browser (`sleeper.com/leagues/<league_id>`).

```bash
sports-tracker fantasy --league-id 1048211345678901234
sports-tracker fantasy --league-id 1048211345678901234 --week 6
```

If you set it as an environment variable, the fantasy table is included automatically whenever you run `sports-tracker` or `sports-tracker all`:

```bash
export SLEEPER_LEAGUE_ID=1048211345678901234
```

The table shows each matchup for the week, who is leading, and by how much. Commissioner score overrides are respected.

## How it works

```
sports_tracker/
  cli.py              argument parsing, the Tracker class, live refresh loop
  client.py           requests session with timeouts and retries
  leagues.py          league definitions and their ESPN paths
  models.py           dataclasses for games, fight cards and fantasy matchups
  render.py           Rich tables for each kind of league
  providers/
    espn.py           ESPN scoreboard requests and parsing
    sleeper.py        Sleeper league, roster and matchup requests
tests/
  fixtures/           saved API responses used by the tests
```

Each selected league is fetched in parallel, so one slow endpoint does not hold up the rest. If a league fails, it shows an error in its own section and the other leagues still display. Games are sorted so that anything live comes first, then upcoming games, then finals.

ESPN does not document these endpoints, so the parsers read every field defensively. A missing field shows up as a blank cell rather than a crash.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

The tests run against saved JSON fixtures and never hit the network. GitHub Actions runs them on Python 3.10 through 3.13 for every push and pull request.

## Known limitations

- ESPN's boxing coverage is thinner than its UFC coverage. Smaller cards often aren't listed, and in those cases the boxing section just reports that nothing is scheduled.
- Fantasy support is Sleeper only. ESPN and Yahoo fantasy leagues require logging in, which this project avoids.
- The data comes from unofficial endpoints, so a change on ESPN's side could break parsing until the code is updated.

## Contact

Samyak Jain
21jsamyak@gmail.com

## License

MIT. See [LICENSE](LICENSE).
