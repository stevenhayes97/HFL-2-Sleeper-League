import json
import urllib.request
import os
import time

BASE = "https://api.sleeper.app/v1"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "league_history")

def fetch(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode())

def main():
    index = json.load(open(os.path.join(OUT_DIR, "index.json")))
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
            weeks[str(week)] = fetch(f"{BASE}/league/{league_id}/matchups/{week}")
            time.sleep(0.2)
        with open(os.path.join(OUT_DIR, season, "matchups.json"), "w") as f:
            json.dump(weeks, f, indent=2)
        print(f"Fetched {leg} weeks of matchups for {season}")

if __name__ == "__main__":
    main()
