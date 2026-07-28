const DATA_DIR = "league_history";

// ---------- Tabs ----------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- Home tab ----------

async function loadHomeStatus() {
  try {
    const index = await fetchJSON(`${DATA_DIR}/index.json`);
    const current = index[0];
    document.getElementById("home-status").textContent =
      `Current season: ${current.season} (${current.status.replace("_", " ")})`;
  } catch (e) {
    document.getElementById("home-status").textContent = "";
  }
}

// ---------- League History tab ----------

async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to fetch ${path}`);
  return res.json();
}

function teamName(user) {
  return (user && user.metadata && user.metadata.team_name) || (user && user.display_name) || "Unknown";
}

function managerName(user) {
  return (user && user.display_name) || "Unknown";
}

function buildStandings(rosters, usersByUserId) {
  const rows = rosters.map((r) => {
    const user = usersByUserId[r.owner_id];
    const s = r.settings || {};
    return {
      roster_id: r.roster_id,
      team: teamName(user),
      manager: managerName(user),
      wins: s.wins || 0,
      losses: s.losses || 0,
      ties: s.ties || 0,
      fpts: (s.fpts || 0) + (s.fpts_decimal || 0) / 100,
      fptsAgainst: (s.fpts_against || 0) + (s.fpts_against_decimal || 0) / 100,
    };
  });

  rows.sort((a, b) => b.wins - a.wins || b.fpts - a.fpts);
  return rows;
}

function buildPlayoffPlacements(bracket, rosters, usersByUserId) {
  const rosterById = {};
  rosters.forEach((r) => (rosterById[r.roster_id] = r));

  const placements = {};
  bracket.forEach((match) => {
    if (!match.p || match.w == null || match.l == null) return;
    placements[match.p] = match.w;
    placements[match.p + 1] = match.l;
  });

  const placedRosterIds = new Set(Object.values(placements));
  const maxPlace = Math.max(0, ...Object.keys(placements).map(Number));

  const rows = [];
  for (let place = 1; place <= maxPlace; place++) {
    const rosterId = placements[place];
    if (rosterId == null) continue;
    const user = usersByUserId[rosterById[rosterId] ? rosterById[rosterId].owner_id : null];
    rows.push({ place, team: teamName(user), manager: managerName(user) });
  }

  // Any playoff-eligible teams not resolved by the bracket (e.g. incomplete data)
  // are left out; non-playoff teams aren't ranked here since the bracket only
  // covers the playoff field.
  return rows;
}

async function renderSeason(season) {
  const loading = document.getElementById("history-loading");
  const notStarted = document.getElementById("history-not-started");
  const tables = document.getElementById("history-tables");

  loading.classList.remove("hidden");
  notStarted.classList.add("hidden");
  tables.classList.add("hidden");

  const dir = `${DATA_DIR}/${season}`;
  const [league, users, rosters, bracket] = await Promise.all([
    fetchJSON(`${dir}/league.json`),
    fetchJSON(`${dir}/users.json`),
    fetchJSON(`${dir}/rosters.json`),
    fetchJSON(`${dir}/winners_bracket.json`),
  ]);

  loading.classList.add("hidden");

  const seasonBegun = league.status !== "pre_draft" && league.status !== "drafting";
  if (!seasonBegun) {
    notStarted.classList.remove("hidden");
    return;
  }

  const usersByUserId = {};
  users.forEach((u) => (usersByUserId[u.user_id] = u));

  const standings = buildStandings(rosters, usersByUserId);
  const standingsBody = document.querySelector("#standings-table tbody");
  standingsBody.innerHTML = standings
    .map(
      (row, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${row.team}</td>
          <td>${row.manager}</td>
          <td>${row.wins}-${row.losses}${row.ties ? `-${row.ties}` : ""}</td>
          <td>${row.fpts.toFixed(2)}</td>
          <td>${row.fptsAgainst.toFixed(2)}</td>
        </tr>`
    )
    .join("");

  const placements = buildPlayoffPlacements(bracket, rosters, usersByUserId);
  const playoffNotStarted = document.getElementById("playoff-not-started");
  const playoffTableWrap = document.getElementById("playoff-table-wrap");

  if (placements.length === 0) {
    playoffNotStarted.classList.remove("hidden");
    playoffTableWrap.classList.add("hidden");
  } else {
    playoffNotStarted.classList.add("hidden");
    playoffTableWrap.classList.remove("hidden");

    const playoffBody = document.querySelector("#playoff-table tbody");
    playoffBody.innerHTML = placements
      .map(
        (row) => `
          <tr>
            <td>${row.place === 1 ? "1st (Champion)" : ordinal(row.place)}</td>
            <td>${row.team}</td>
            <td>${row.manager}</td>
          </tr>`
      )
      .join("");
  }

  tables.classList.remove("hidden");
}

function ordinal(n) {
  const suffixes = { 1: "st", 2: "nd", 3: "rd" };
  const suffix = suffixes[n % 100] || suffixes[n % 10] || "th";
  return `${n}${suffix}`;
}

async function initHistoryTab() {
  const index = await fetchJSON(`${DATA_DIR}/index.json`);
  const years = index.map((entry) => entry.season).sort((a, b) => b - a);

  // index.json is ordered newest-to-oldest, so the first entry whose draft
  // has completed is the most recent season worth defaulting to.
  const draftCompleted = (status) => status !== "pre_draft" && status !== "drafting";
  const defaultEntry = index.find((e) => draftCompleted(e.status)) || index[index.length - 1];
  const defaultYear = defaultEntry.season;

  const selector = document.getElementById("year-selector");
  selector.innerHTML = years
    .map((y) => `<button class="year-btn${y === defaultYear ? " active" : ""}" data-year="${y}">${y}</button>`)
    .join("");

  selector.querySelectorAll(".year-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      selector.querySelectorAll(".year-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderSeason(btn.dataset.year);
    });
  });

  renderSeason(defaultYear);
}

// ---------- Historical Overview tab ----------

function scoreCell(entry) {
  if (!entry || entry.points == null) return "&mdash;";
  return `${entry.name} (${entry.points})`;
}

async function initOverviewTab() {
  const overview = await fetchJSON(`${DATA_DIR}/historical_overview.json`);

  const yearsBody = document.querySelector("#overview-years-table tbody");
  yearsBody.innerHTML = overview.years
    .slice()
    .sort((a, b) => b.season - a.season)
    .map(
      (y) => `
        <tr>
          <td>${y.season}</td>
          <td>${y.champion.name || "&mdash;"}</td>
          <td>${scoreCell(y.highest_score)}</td>
          <td>${scoreCell(y.lowest_score)}</td>
          <td>${scoreCell(y.scoring_title)}</td>
        </tr>`
    )
    .join("");

  const allTimeBody = document.querySelector("#overview-alltime-table tbody");
  allTimeBody.innerHTML = overview.all_time
    .map(
      (r) => `
        <tr>
          <td>${r.name}</td>
          <td>${r.wins}</td>
          <td>${r.losses}</td>
          <td>${r.win_pct}%</td>
          <td>${r.points_for.toFixed(2)}</td>
          <td>${r.points_against.toFixed(2)}</td>
          <td>${r.differential.toFixed(2)}</td>
          <td>${r.playoff_wins}</td>
          <td>${r.seasons_played}</td>
        </tr>`
    )
    .join("");

  document.getElementById("overview-loading").classList.add("hidden");
  document.getElementById("overview-content").classList.remove("hidden");
}

loadHomeStatus();
initHistoryTab();
initOverviewTab();
