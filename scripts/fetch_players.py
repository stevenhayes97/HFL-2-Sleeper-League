import json
import urllib.request
import os
import sys

from championship_utils import find_championship

BASE = "https://api.sleeper.app/v1"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "league_history")
CACHE_PATH = os.path.join(OUT_DIR, "players_cache.json")

# Sleeper's full player list is a multi-MB file covering every NFL player
# ever, and their docs ask that it not be pulled on every load - so this
# only fetches it when a championship lineup references a player_id we
# don't already have cached, and only stores the small subset actually
# needed (not the whole file).

def load(season, name):
    with open(os.path.join(OUT_DIR, season, name)) as f:
        return json.load(f)

def needed_player_ids():
    ids = set()
    index = json.load(open(os.path.join(OUT_DIR, "index.json")))
    for entry in index:
        if entry["status"] != "complete":
            continue
        season = entry["season"]
        league = load(season, "league.json")
        bracket = load(season, "winners_bracket.json")
        matchups = load(season, "matchups.json")

        champ = find_championship(league, bracket)
        if champ is None:
            continue
        week_entries = matchups[str(champ["week"])]
        for roster_id in (champ["roster_a"], champ["roster_b"]):
            entry_for_roster = next((e for e in week_entries if e["roster_id"] == roster_id), None)
            if entry_for_roster is None:
                continue
            for pid in entry_for_roster.get("starters", []):
                if pid and pid != "0":
                    ids.add(pid)
    return ids

def main():
    needed = needed_player_ids()

    cache = {}
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))

    missing = sorted(needed - cache.keys())
    if not missing:
        print(f"No new players needed ({len(cache)} already cached).")
        return

    print(f"Fetching Sleeper's full player list to resolve {len(missing)} new player(s)...")
    with urllib.request.urlopen(f"{BASE}/players/nfl") as resp:
        all_players = json.loads(resp.read().decode())

    if not isinstance(all_players, dict):
        print("Unexpected response from /players/nfl (not an object) - Sleeper's API may have changed.", file=sys.stderr)
        sys.exit(1)

    still_missing = []
    for pid in missing:
        p = all_players.get(pid)
        if p is None:
            still_missing.append(pid)
            continue
        cache[pid] = {
            "full_name": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid,
            "position": p.get("position"),
            "team": p.get("team"),
        }

    with open(CACHE_PATH, "w") as f:
        json.dump(dict(sorted(cache.items())), f, indent=2)

    print(f"Cached {len(missing) - len(still_missing)} new player(s). Total cached: {len(cache)}.")
    if still_missing:
        print(f"Warning: {len(still_missing)} player_id(s) not found in Sleeper's player list: {still_missing}", file=sys.stderr)

if __name__ == "__main__":
    main()
