import json
import urllib.request
import os
import time

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
    while league_id and league_id != "0":
        league = fetch(f"{BASE}/league/{league_id}")
        season = league.get("season", league_id)
        season_dir = os.path.join(OUT_DIR, season)
        os.makedirs(season_dir, exist_ok=True)

        save(os.path.join(season_dir, "league.json"), league)
        chain.append({"season": season, "league_id": league_id, "status": league.get("status")})

        for endpoint, fname in [
            ("users", "users.json"),
            ("rosters", "rosters.json"),
            ("winners_bracket", "winners_bracket.json"),
            ("losers_bracket", "losers_bracket.json"),
            ("drafts", "drafts.json"),
            ("traded_picks", "traded_picks.json"),
        ]:
            try:
                data = fetch(f"{BASE}/league/{league_id}/{endpoint}")
                save(os.path.join(season_dir, fname), data)
            except Exception as e:
                print(f"  skip {endpoint} for {season} ({league_id}): {e}")
            time.sleep(0.3)

        print(f"Fetched season {season} (league_id={league_id})")
        league_id = league.get("previous_league_id")

    save(os.path.join(OUT_DIR, "index.json"), chain)
    print("\nChain:")
    for c in chain:
        print(c)

if __name__ == "__main__":
    main()
