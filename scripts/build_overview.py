import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "league_history")

def load(season, name):
    with open(os.path.join(DATA_DIR, season, name)) as f:
        return json.load(f)

def fpts_total(settings, prefix):
    return (settings.get(f"{prefix}") or 0) + (settings.get(f"{prefix}_decimal") or 0) / 100

def main():
    index = json.load(open(os.path.join(DATA_DIR, "index.json")))
    completed = [e for e in index if e["status"] == "complete"]
    completed.sort(key=lambda e: e["season"])  # oldest -> newest

    all_time = {}  # user_id -> stats accumulator
    years_out = []

    for entry in completed:
        season = entry["season"]
        league = load(season, "league.json")
        users = load(season, "users.json")
        rosters = load(season, "rosters.json")
        bracket = load(season, "winners_bracket.json")
        matchups = load(season, "matchups.json")

        user_by_id = {u["user_id"]: u for u in users}
        roster_to_owner = {r["roster_id"]: r["owner_id"] for r in rosters}

        def name_for(owner_id):
            u = user_by_id.get(owner_id)
            return (u or {}).get("display_name", "Unknown")

        # --- season accumulation for all-time table ---
        for r in rosters:
            owner_id = r["owner_id"]
            s = r.get("settings", {})
            acc = all_time.setdefault(owner_id, {
                "user_id": owner_id,
                "wins": 0, "losses": 0,
                "points_for": 0.0, "points_against": 0.0,
                "playoff_wins": 0, "seasons_played": 0,
                "last_display_name": name_for(owner_id),
            })
            acc["wins"] += s.get("wins", 0) or 0
            acc["losses"] += s.get("losses", 0) or 0
            acc["points_for"] += fpts_total(s, "fpts")
            acc["points_against"] += fpts_total(s, "fpts_against")
            acc["seasons_played"] += 1
            acc["last_display_name"] = name_for(owner_id)  # newest season wins (processed oldest->newest)

        for match in bracket:
            winner_roster = match.get("w")
            if winner_roster is None:
                continue
            # Count bracket-advancement wins and the championship itself, but
            # not 3rd/5th-place consolation game wins.
            if match.get("p") not in (None, 1):
                continue
            owner_id = roster_to_owner.get(winner_roster)
            if owner_id is None:
                continue
            acc = all_time.setdefault(owner_id, {
                "user_id": owner_id,
                "wins": 0, "losses": 0,
                "points_for": 0.0, "points_against": 0.0,
                "playoff_wins": 0, "seasons_played": 0,
                "last_display_name": name_for(owner_id),
            })
            acc["playoff_wins"] += 1

        # --- per-year highlights ---
        champion_roster = None
        for match in bracket:
            if match.get("p") == 1 and match.get("w") is not None:
                champion_roster = match["w"]
                break
        champion_owner = roster_to_owner.get(champion_roster) if champion_roster else None

        playoff_week_start = league["settings"]["playoff_week_start"]

        best_week = {"points": None, "roster_id": None, "week": None}
        worst_week = {"points": None, "roster_id": None, "week": None}
        for week_str, week_matchups in matchups.items():
            week = int(week_str)
            if week >= playoff_week_start:
                continue
            for m in week_matchups:
                pts = m.get("points")
                if pts is None:
                    continue
                if best_week["points"] is None or pts > best_week["points"]:
                    best_week = {"points": pts, "roster_id": m["roster_id"], "week": week}
                if worst_week["points"] is None or pts < worst_week["points"]:
                    worst_week = {"points": pts, "roster_id": m["roster_id"], "week": week}

        scoring_title = None
        for r in rosters:
            pf = fpts_total(r.get("settings", {}), "fpts")
            if scoring_title is None or pf > scoring_title["points"]:
                scoring_title = {"points": pf, "owner_id": r["owner_id"]}

        years_out.append({
            "season": season,
            "champion": {
                "user_id": champion_owner,
                "name": name_for(champion_owner) if champion_owner else None,
            },
            "highest_score": {
                "user_id": roster_to_owner.get(best_week["roster_id"]),
                "name": name_for(roster_to_owner.get(best_week["roster_id"])),
                "points": round(best_week["points"], 2),
                "week": best_week["week"],
            },
            "lowest_score": {
                "user_id": roster_to_owner.get(worst_week["roster_id"]),
                "name": name_for(roster_to_owner.get(worst_week["roster_id"])),
                "points": round(worst_week["points"], 2),
                "week": worst_week["week"],
            },
            "scoring_title": {
                "user_id": scoring_title["owner_id"],
                "name": name_for(scoring_title["owner_id"]),
                "points": round(scoring_title["points"], 2),
            },
        })

    all_time_out = []
    for acc in all_time.values():
        wins, losses = acc["wins"], acc["losses"]
        total = wins + losses
        win_pct = int((wins / total) * 100 + 0.5) if total else 0
        all_time_out.append({
            "user_id": acc["user_id"],
            "name": acc["last_display_name"],
            "wins": wins,
            "losses": losses,
            "win_pct": win_pct,
            "points_for": round(acc["points_for"], 2),
            "points_against": round(acc["points_against"], 2),
            "differential": round(acc["points_for"] - acc["points_against"], 2),
            "playoff_wins": acc["playoff_wins"],
            "seasons_played": acc["seasons_played"],
        })

    all_time_out.sort(key=lambda r: (-r["wins"], -r["points_for"]))

    out = {"years": years_out, "all_time": all_time_out}
    with open(os.path.join(DATA_DIR, "historical_overview.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote historical_overview.json ({len(years_out)} seasons, {len(all_time_out)} managers)")

if __name__ == "__main__":
    main()
