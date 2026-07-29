import json
import os

from championship_utils import find_championship

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "league_history")
ALIASES_PATH = os.path.join(SCRIPT_DIR, "user_aliases.json")
PLAYERS_CACHE_PATH = os.path.join(DATA_DIR, "players_cache.json")

NON_STARTING_SLOTS = ("BN", "TAXI", "IR")

def load(season, name):
    with open(os.path.join(DATA_DIR, season, name)) as f:
        return json.load(f)

def fpts_total(settings, prefix):
    return (settings.get(f"{prefix}") or 0) + (settings.get(f"{prefix}_decimal") or 0) / 100

def team_name_for(user_by_id, owner_id):
    u = user_by_id.get(owner_id) or {}
    return (u.get("metadata") or {}).get("team_name") or u.get("display_name", "Unknown")

def build_lineup(week_entry, roster_positions, players_cache):
    # No "team" field here deliberately - Sleeper's player list only has a
    # player's current team, not who they played for that historical
    # season, and showing a wrong team is worse than not showing one.
    # Position is included since it's far more stable over a career.
    starters = week_entry.get("starters", [])
    starters_points = week_entry.get("starters_points", [])
    lineup = []
    for slot, pid, pts in zip(roster_positions, starters, starters_points):
        if not pid or pid == "0":
            lineup.append({"slot": slot, "player_id": None, "player_name": "Empty", "position": None, "points": round(pts, 2)})
            continue
        p = players_cache.get(pid)
        if p:
            name, position = p["full_name"], p["position"]
        else:
            name, position = f"Unknown Player ({pid})", None
        lineup.append({"slot": slot, "player_id": pid, "player_name": name, "position": position, "points": round(pts, 2)})
    return lineup

def build_draft_board(draft_picks, teams, roster_to_owner, user_by_id, name_for):
    picks_out = []
    for pick in draft_picks:
        owner_id = roster_to_owner.get(pick["roster_id"])
        meta = pick.get("metadata") or {}
        pick_in_round = pick["pick_no"] - (pick["round"] - 1) * teams
        first, last = meta.get("first_name"), meta.get("last_name")
        player_name = f"{first} {last}".strip() if (first or last) else "Unknown Player"
        picks_out.append({
            "round": pick["round"],
            "pick_in_round": pick_in_round,
            "pick_no": pick["pick_no"],
            "label": f"{pick['round']}.{pick_in_round}",
            "team_name": team_name_for(user_by_id, owner_id) if owner_id else "Unknown",
            "name": name_for(owner_id) if owner_id else "Unknown",
            "player_name": player_name,
            "position": meta.get("position"),
        })
    picks_out.sort(key=lambda p: p["pick_no"])
    return picks_out


def load_aliases():
    with open(ALIASES_PATH) as f:
        aliases = json.load(f).get("aliases", {})
    alias_to_canonical = {}
    display_name_overrides = {}
    for canonical_id, info in aliases.items():
        for alias_id in info.get("aliases", []):
            alias_to_canonical[alias_id] = canonical_id
        if info.get("display_name"):
            display_name_overrides[canonical_id] = info["display_name"]
    return alias_to_canonical, display_name_overrides

def build_current_names(index, canonical, display_name_overrides):
    # Walk every season we know about, oldest to newest, regardless of
    # completion status, so each user_id ends up mapped to their most
    # recently-known Sleeper display_name. A season that's only
    # pre_draft/drafting still has a real users.json (Sleeper reports a
    # display_name as soon as someone joins the league), so an active
    # member's current name wins even before their season starts.
    names = {}
    for entry in sorted(index, key=lambda e: e["season"]):
        try:
            users = load(entry["season"], "users.json")
        except FileNotFoundError:
            continue
        for u in users:
            names[canonical(u["user_id"])] = u["display_name"]
    names.update(display_name_overrides)
    return names

def main():
    alias_to_canonical, display_name_overrides = load_aliases()

    def canonical(owner_id):
        return alias_to_canonical.get(owner_id, owner_id)

    index = json.load(open(os.path.join(DATA_DIR, "index.json")))
    current_names = build_current_names(index, canonical, display_name_overrides)

    players_cache = {}
    if os.path.exists(PLAYERS_CACHE_PATH):
        players_cache = json.load(open(PLAYERS_CACHE_PATH))

    def name_for(owner_id):
        return current_names.get(canonical(owner_id), "Unknown")

    completed = [e for e in index if e["status"] == "complete"]
    completed.sort(key=lambda e: e["season"])  # oldest -> newest

    all_time = {}  # canonical user_id -> stats accumulator
    season_points = {}  # canonical user_id -> {season: {"for": x, "against": y}}
    head_to_head = {}  # canonical user_id -> {opponent canonical user_id: [wins, losses]}
    years_out = []
    championships_out = []
    drafts_out = []

    for entry in completed:
        season = entry["season"]
        league = load(season, "league.json")
        users = load(season, "users.json")
        rosters = load(season, "rosters.json")
        bracket = load(season, "winners_bracket.json")
        matchups = load(season, "matchups.json")

        roster_to_owner = {r["roster_id"]: r["owner_id"] for r in rosters}
        user_by_id = {u["user_id"]: u for u in users}

        # --- season accumulation for all-time table ---
        for r in rosters:
            canonical_id = canonical(r["owner_id"])
            s = r.get("settings", {})
            acc = all_time.setdefault(canonical_id, {
                "user_id": canonical_id,
                "wins": 0, "losses": 0,
                "points_for": 0.0, "points_against": 0.0,
                "playoff_wins": 0, "seasons_played": 0,
            })
            pf = fpts_total(s, "fpts")
            pa = fpts_total(s, "fpts_against")
            acc["wins"] += s.get("wins", 0) or 0
            acc["losses"] += s.get("losses", 0) or 0
            acc["points_for"] += pf
            acc["points_against"] += pa
            acc["seasons_played"] += 1

            # A manager can only hold one roster per season, so this is a
            # straight assignment rather than an accumulation.
            season_points.setdefault(canonical_id, {})[season] = {
                "for": round(pf, 2),
                "against": round(pa, 2),
            }

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
            canonical_id = canonical(owner_id)
            acc = all_time.setdefault(canonical_id, {
                "user_id": canonical_id,
                "wins": 0, "losses": 0,
                "points_for": 0.0, "points_against": 0.0,
                "playoff_wins": 0, "seasons_played": 0,
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

        # --- head-to-head, regular season only (matches the other per-manager
        # stats), pairing rosters that share a matchup_id in the same week ---
        for week_str, week_matchups in matchups.items():
            week = int(week_str)
            if week >= playoff_week_start:
                continue
            by_matchup_id = {}
            for m in week_matchups:
                by_matchup_id.setdefault(m["matchup_id"], []).append(m)
            for pair in by_matchup_id.values():
                if len(pair) != 2:
                    continue
                p1, p2 = pair
                pts1, pts2 = p1.get("points"), p2.get("points")
                if pts1 is None or pts2 is None or pts1 == pts2:
                    continue
                id1 = canonical(roster_to_owner[p1["roster_id"]])
                id2 = canonical(roster_to_owner[p2["roster_id"]])
                winner_id, loser_id = (id1, id2) if pts1 > pts2 else (id2, id1)
                head_to_head.setdefault(winner_id, {}).setdefault(loser_id, [0, 0])[0] += 1
                head_to_head.setdefault(loser_id, {}).setdefault(winner_id, [0, 0])[1] += 1

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

        # --- championship matchup lineup ---
        champ = find_championship(league, bracket)
        if champ is not None:
            week_entries = matchups.get(str(champ["week"]), [])
            roster_positions = [p for p in league.get("roster_positions", []) if p not in NON_STARTING_SLOTS]

            def team_payload(roster_id, is_winner):
                owner_id = roster_to_owner[roster_id]
                week_entry = next((e for e in week_entries if e["roster_id"] == roster_id), {})
                return {
                    "user_id": canonical(owner_id),
                    "name": name_for(owner_id),
                    "team_name": team_name_for(user_by_id, owner_id),
                    "points": round(week_entry.get("points") or 0, 2),
                    "is_winner": is_winner,
                    "lineup": build_lineup(week_entry, roster_positions, players_cache),
                }

            championships_out.append({
                "season": season,
                "week": champ["week"],
                "teams": [
                    team_payload(champ["roster_a"], True),
                    team_payload(champ["roster_b"], False),
                ],
            })

        # --- draft board ---
        draft_picks_entries = load(season, "draft_picks.json")
        all_picks = [p for entry in draft_picks_entries for p in entry["picks"]]
        if all_picks:
            picks = build_draft_board(all_picks, league["total_rosters"], roster_to_owner, user_by_id, name_for)
            drafts_out.append({"season": season, "picks": picks})

    all_time_out = []
    for acc in all_time.values():
        wins, losses = acc["wins"], acc["losses"]
        total = wins + losses
        win_pct = int((wins / total) * 100 + 0.5) if total else 0
        all_time_out.append({
            "user_id": acc["user_id"],
            "name": current_names.get(acc["user_id"], "Unknown"),
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

    # Per-season points for/against grids. Seasons a manager didn't play are
    # left absent rather than zeroed, so the site can render them blank.
    season_list = [e["season"] for e in completed]
    season_points_out = []
    for canonical_id, per_season in season_points.items():
        season_points_out.append({
            "user_id": canonical_id,
            "name": current_names.get(canonical_id, "Unknown"),
            "seasons": per_season,
            "total_for": round(sum(v["for"] for v in per_season.values()), 2),
            "total_against": round(sum(v["against"] for v in per_season.values()), 2),
        })

    # Head-to-head grid, ordered to match the All-Time table so the two tabs
    # read consistently. A manager pair with no games together is simply
    # absent from records, rather than a zeroed [0, 0].
    h2h_order = [r["user_id"] for r in all_time_out]
    out = {
        "years": years_out,
        "all_time": all_time_out,
        "current_names": current_names,
        "season_points": {"seasons": season_list, "rows": season_points_out},
        "head_to_head": {"order": h2h_order, "records": head_to_head},
        "championships": championships_out,
        "drafts": drafts_out,
    }
    with open(os.path.join(DATA_DIR, "historical_overview.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote historical_overview.json ({len(years_out)} seasons, {len(all_time_out)} managers)")

if __name__ == "__main__":
    main()
