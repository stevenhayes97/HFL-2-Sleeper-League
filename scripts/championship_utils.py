"""
Shared logic for locating a season's championship game, used by both
fetch_players.py (to know which players' names it needs) and
build_overview.py (to build the actual matchup data for the site).
"""


def find_championship(league, bracket):
    """Returns {"week": int, "roster_a": int, "roster_b": int} for the
    season's championship game, or None if the bracket has no decided
    champion yet (e.g. playoffs haven't been played).

    Computed from playoff round math rather than searching for a shared
    matchup_id, because the two finalists may have also played each other
    earlier in the regular season - matching on matchup_id alone could
    find that regular-season game instead of the actual championship.
    """
    championship_match = next((m for m in bracket if m.get("p") == 1 and m.get("w") is not None), None)
    if championship_match is None:
        return None

    max_round = max((m["r"] for m in bracket), default=None)
    if max_round is None:
        return None

    playoff_week_start = league["settings"]["playoff_week_start"]
    week = playoff_week_start + max_round - 1

    return {
        "week": week,
        "roster_a": championship_match["w"],
        "roster_b": championship_match["l"],
    }
