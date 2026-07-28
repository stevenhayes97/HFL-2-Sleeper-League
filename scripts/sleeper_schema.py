"""
Validates that Sleeper API responses still look like what build_overview.py
and the site expect, before any fetch script writes them to disk. Catches
a Sleeper API change (renamed/missing field, different shape) as a loud
failure instead of silently overwriting good historical data with broken
data - most likely to matter on the first pull after a draft, when
placeholder pre_draft data turns into real rosters/matchups for the first
time in a season.

Only checks the fields this project actually reads. Doesn't validate
every field Sleeper returns - an unrelated new field appearing is not a
problem, a field we depend on disappearing or changing type is.
"""


class SchemaError(Exception):
    """Raised when a Sleeper API response doesn't match what we depend on."""


def require(condition, message):
    if not condition:
        raise SchemaError(message)


def check_league(league, label):
    require(isinstance(league, dict), f"{label}: league response is not a JSON object")
    for key in ("league_id", "season", "status", "settings", "total_rosters"):
        require(key in league, f"{label}: league response missing '{key}' - check if Sleeper's API changed")
    require(isinstance(league["season"], str), f"{label}: league.season is not a string")
    require(isinstance(league["settings"], dict), f"{label}: league.settings is not an object")
    for key in ("playoff_week_start", "leg"):
        require(key in league["settings"], f"{label}: league.settings missing '{key}'")
    # previous_league_id drives the season chain walk - must be present as a
    # key even when its value is null (no earlier season).
    require("previous_league_id" in league, f"{label}: league response missing 'previous_league_id'")


def check_users(users, label):
    require(isinstance(users, list), f"{label}: users response is not a list")
    for u in users:
        require(isinstance(u, dict), f"{label}: a users entry is not an object")
        require("user_id" in u and isinstance(u["user_id"], str), f"{label}: a users entry missing string 'user_id'")
        require("display_name" in u, f"{label}: a users entry missing 'display_name'")


def check_rosters(rosters, label):
    # Only checks fields the site actually requires unconditionally
    # (roster_id, owner_id, settings-as-an-object). Individual stat fields
    # inside settings (wins, fpts, fpts_against, ...) are read defensively
    # via .get() downstream and are legitimately absent - not just zero -
    # before a season has played any games, so they aren't checked here.
    require(isinstance(rosters, list), f"{label}: rosters response is not a list")
    for r in rosters:
        require(isinstance(r, dict), f"{label}: a rosters entry is not an object")
        require("roster_id" in r, f"{label}: a rosters entry missing 'roster_id'")
        require("owner_id" in r, f"{label}: a rosters entry missing 'owner_id'")
        require("settings" in r and isinstance(r["settings"], dict), f"{label}: a rosters entry missing 'settings'")


def check_bracket(bracket, label):
    require(isinstance(bracket, list), f"{label}: bracket response is not a list")
    for m in bracket:
        require(isinstance(m, dict), f"{label}: a bracket entry is not an object")
        for key in ("m", "r", "t1", "t2", "w", "l"):
            require(key in m, f"{label}: a bracket entry missing '{key}'")


def check_matchups_week(entries, label):
    require(isinstance(entries, list), f"{label}: matchups response is not a list")
    for m in entries:
        require(isinstance(m, dict), f"{label}: a matchups entry is not an object")
        for key in ("roster_id", "matchup_id", "points"):
            require(key in m, f"{label}: a matchups entry missing '{key}'")
