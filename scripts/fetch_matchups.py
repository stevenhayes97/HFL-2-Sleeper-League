import json
import urllib.request
import os
import sys
import time

from sleeper_schema import SchemaError, check_matchups_week

BASE = "https://api.sleeper.app/v1"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "league_history")

def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())

def main():
    index = json.load(open(os.path.join(OUT_DIR, "index.json")))
    # Fetch and validate every season's full set of weeks before writing
    # anything, so a Sleeper API change aborts the whole refresh instead of
    # leaving some seasons updated and others not.
    pending = []  # list of (season, weeks_dict)

    for entry in index:
        season = entry["season"]
        league_id = entry["league_id"]
        league = json.load(open(os.path.join(OUT_DIR, season, "league.json")))
        if league.get("status") != "complete":
            print(f"Skipping {season} (status={league.get('status')})")
            continue
        leg = league["settings"].get("last_scored_leg") or league["settings"].get("leg")
        weeks = {}
        for week in range(1, leg + 1):
            data = fetch(f"{BASE}/league/{league_id}/matchups/{week}")
            check_matchups_week(data, f"season {season} week {week}")
            weeks[str(week)] = data
            time.sleep(0.2)
        pending.append((season, leg, weeks))
        print(f"Fetched and validated {leg} weeks of matchups for {season}")

    for season, leg, weeks in pending:
        with open(os.path.join(OUT_DIR, season, "matchups.json"), "w") as f:
            json.dump(weeks, f, indent=2)
        print(f"Wrote matchups.json for {season} ({leg} weeks)")

if __name__ == "__main__":
    try:
        main()
    except SchemaError as e:
        print(f"\nSleeper API validation FAILED - nothing was written: {e}", file=sys.stderr)
        print("This usually means Sleeper changed their API. Check the endpoint manually before retrying.", file=sys.stderr)
        sys.exit(1)
