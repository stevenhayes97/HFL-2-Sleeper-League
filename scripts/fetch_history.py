import json
import urllib.request
import os
import sys
import time

from sleeper_schema import SchemaError, check_league, check_users, check_rosters, check_bracket

BASE = "https://api.sleeper.app/v1"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "league_history")
START_LEAGUE_ID = "1382788768955641856"

def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def main():
    league_id = START_LEAGUE_ID
    chain = []
    # Fetch and validate every season fully before writing anything to disk,
    # so a Sleeper API change (a field renamed, missing, or reshaped) aborts
    # the whole refresh instead of partially overwriting good historical
    # data with broken data.
    pending = []  # list of (season_dir, {filename: data})

    while league_id and league_id != "0":
        league = fetch(f"{BASE}/league/{league_id}")
        season = league.get("season", league_id)
        label = f"season {season} (league_id={league_id})"
        check_league(league, label)

        season_dir = os.path.join(OUT_DIR, season)
        files = {"league.json": league}
        chain.append({"season": season, "league_id": league_id, "status": league.get("status")})

        for endpoint, fname, checker in [
            ("users", "users.json", check_users),
            ("rosters", "rosters.json", check_rosters),
            ("winners_bracket", "winners_bracket.json", check_bracket),
            ("losers_bracket", "losers_bracket.json", check_bracket),
        ]:
            data = fetch(f"{BASE}/league/{league_id}/{endpoint}")
            checker(data, f"{label} {endpoint}")
            files[fname] = data
            time.sleep(0.3)

        # drafts/traded_picks aren't read anywhere downstream (build_overview.py,
        # the site) - kept as raw archival data, so only a basic type check.
        for endpoint, fname in [("drafts", "drafts.json"), ("traded_picks", "traded_picks.json")]:
            data = fetch(f"{BASE}/league/{league_id}/{endpoint}")
            if not isinstance(data, list):
                raise SchemaError(f"{label} {endpoint}: expected a list, got {type(data).__name__}")
            files[fname] = data
            time.sleep(0.3)

        pending.append((season_dir, files))
        print(f"Fetched and validated season {season} (league_id={league_id})")
        league_id = league.get("previous_league_id")

    for season_dir, files in pending:
        os.makedirs(season_dir, exist_ok=True)
        for fname, data in files.items():
            save(os.path.join(season_dir, fname), data)

    save(os.path.join(OUT_DIR, "index.json"), chain)
    print(f"\nWrote {len(pending)} seasons. Chain:")
    for c in chain:
        print(c)

if __name__ == "__main__":
    try:
        main()
    except SchemaError as e:
        print(f"\nSleeper API validation FAILED - nothing was written: {e}", file=sys.stderr)
        print("This usually means Sleeper changed their API. Check the endpoint manually before retrying.", file=sys.stderr)
        sys.exit(1)
