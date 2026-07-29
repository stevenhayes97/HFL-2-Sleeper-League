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

let currentNames = {};
let overviewPromise = null;

// Several tabs read this same file; fetch it once and share the result.
// On failure, the cached promise is cleared so the next caller gets a fresh
// attempt instead of a permanently-rejected promise from one bad request.
function loadOverview() {
  if (!overviewPromise) {
    overviewPromise = fetchJSON(`${DATA_DIR}/historical_overview.json`).catch((err) => {
      overviewPromise = null;
      throw err;
    });
  }
  return overviewPromise;
}

async function loadCurrentNames() {
  try {
    const overview = await loadOverview();
    currentNames = overview.current_names || {};
  } catch (e) {
    currentNames = {};
  }
}

function teamName(user) {
  return (user && user.metadata && user.metadata.team_name) || (user && user.display_name) || "Unknown";
}

// Always shows a manager's most current known Sleeper display_name, not
// whatever name they had in the season being viewed, so someone who's
// renamed is recognizable everywhere on the site.
function managerName(user) {
  if (!user) return "Unknown";
  return currentNames[user.user_id] || user.display_name || "Unknown";
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
  loading.textContent = "Loading season data…";
  notStarted.classList.add("hidden");
  tables.classList.add("hidden");

  try {
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
  } catch (e) {
    loading.classList.remove("hidden");
    loading.textContent = `Couldn't load ${season} data: ${e.message}. Check your connection and reload.`;
    return;
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
  const loading = document.getElementById("overview-loading");
  try {
    const overview = await loadOverview();

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

    loading.classList.add("hidden");
    document.getElementById("overview-content").classList.remove("hidden");
  } catch (e) {
    loading.textContent = `Couldn't load data: ${e.message}. Check your connection and reload.`;
  }
}

// ---------- Points For / Points Against tabs ----------

// Both tabs are the same grid over the same rows, differing only in which
// per-season value they read, so they share one renderer.
function renderPointsTable(tableId, seasonPoints, key, totalKey) {
  const { seasons, rows } = seasonPoints;

  const headRow = document.querySelector(`#${tableId} thead tr`);
  headRow.innerHTML =
    "<th>Name</th>" +
    seasons.map((s) => `<th>${s}</th>`).join("") +
    "<th>Total</th>";

  const sorted = rows.slice().sort((a, b) => b[totalKey] - a[totalKey]);

  const body = document.querySelector(`#${tableId} tbody`);
  body.innerHTML = sorted
    .map((row) => {
      const cells = seasons
        .map((s) => {
          const entry = row.seasons[s];
          return `<td>${entry ? entry[key].toFixed(2) : ""}</td>`;
        })
        .join("");
      return `<tr><td>${row.name}</td>${cells}<td class="total-col">${row[totalKey].toFixed(2)}</td></tr>`;
    })
    .join("");
}

async function initPointsTabs() {
  const forStatus = document.getElementById("points-for-status");
  const againstStatus = document.getElementById("points-against-status");

  try {
    const overview = await loadOverview();

    const seasonPoints = overview.season_points;
    if (!seasonPoints) {
      forStatus.textContent = "No points data available yet.";
      againstStatus.textContent = "No points data available yet.";
      return;
    }

    renderPointsTable("points-for-table", seasonPoints, "for", "total_for");
    renderPointsTable("points-against-table", seasonPoints, "against", "total_against");
    forStatus.classList.add("hidden");
    againstStatus.classList.add("hidden");
  } catch (e) {
    const message = `Couldn't load data: ${e.message}. Check your connection and reload.`;
    forStatus.textContent = message;
    againstStatus.textContent = message;
  }
}

// ---------- Head-to-Head tab ----------

function renderHeadToHead(headToHead, currentNamesMap) {
  const { order, records } = headToHead;

  const headRow = document.querySelector("#head-to-head-table thead tr");
  headRow.innerHTML =
    "<th>Name</th>" + order.map((id) => `<th>${currentNamesMap[id] || "Unknown"}</th>`).join("");

  const body = document.querySelector("#head-to-head-table tbody");
  body.innerHTML = order
    .map((rowId) => {
      const rowRecord = records[rowId] || {};
      const cells = order
        .map((colId) => {
          if (colId === rowId) return `<td class="diagonal-cell">&mdash;</td>`;
          const rec = rowRecord[colId];
          return `<td>${rec ? `${rec[0]}-${rec[1]}` : ""}</td>`;
        })
        .join("");
      return `<tr><td class="row-label">${currentNamesMap[rowId] || "Unknown"}</td>${cells}</tr>`;
    })
    .join("");
}

async function initHeadToHeadTab() {
  const status = document.getElementById("head-to-head-status");
  try {
    const overview = await loadOverview();

    const headToHead = overview.head_to_head;
    if (!headToHead) {
      status.textContent = "No head-to-head data available yet.";
      return;
    }

    renderHeadToHead(headToHead, overview.current_names || {});
    status.classList.add("hidden");
  } catch (e) {
    status.textContent = `Couldn't load data: ${e.message}. Check your connection and reload.`;
  }
}

// ---------- Championship Matchup tab ----------

function playerLabel(p) {
  if (p.player_id == null) return p.player_name;
  return p.position ? `${p.player_name} (${p.position})` : p.player_name;
}

function renderChampionshipTeamHeader(el, team) {
  el.classList.toggle("matchup-team-winner", team.is_winner);
  el.innerHTML = `
    <div class="matchup-team-name">${team.team_name}${team.is_winner ? " &#127942;" : ""}</div>
    <div class="matchup-team-manager">${team.name}</div>
    <div class="matchup-team-points">${team.points.toFixed(2)}</div>
  `;
}

function renderChampionship(champ) {
  const [teamA, teamB] = champ.teams;

  renderChampionshipTeamHeader(document.getElementById("championship-team-a"), teamA);
  renderChampionshipTeamHeader(document.getElementById("championship-team-b"), teamB);

  document.getElementById("championship-lineup-head-a").textContent = teamA.team_name;
  document.getElementById("championship-lineup-head-b").textContent = teamB.team_name;

  const body = document.querySelector("#championship-lineup-table tbody");
  body.innerHTML = teamA.lineup
    .map((playerA, i) => {
      const playerB = teamB.lineup[i];
      return `
        <tr>
          <td>${playerLabel(playerA)}</td>
          <td class="lineup-pts">${playerA.points.toFixed(2)}</td>
          <td class="slot-label">${playerA.slot}</td>
          <td class="lineup-pts">${playerB.points.toFixed(2)}</td>
          <td>${playerLabel(playerB)}</td>
        </tr>`;
    })
    .join("");
}

async function initChampionshipTab() {
  const status = document.getElementById("championship-status");
  const content = document.getElementById("championship-content");
  const selector = document.getElementById("championship-year-selector");

  let championships;
  try {
    const overview = await loadOverview();
    championships = overview.championships;
  } catch (e) {
    status.textContent = `Couldn't load data: ${e.message}. Check your connection and reload.`;
    return;
  }

  if (!championships || championships.length === 0) {
    status.textContent = "No championship data available yet.";
    return;
  }

  const bySeason = {};
  championships.forEach((c) => (bySeason[c.season] = c));
  const years = Object.keys(bySeason).sort((a, b) => b - a);
  const defaultYear = years[0];

  selector.innerHTML = years
    .map((y) => `<button class="year-btn${y === defaultYear ? " active" : ""}" data-year="${y}">${y}</button>`)
    .join("");

  const showYear = (year) => {
    try {
      renderChampionship(bySeason[year]);
      status.classList.add("hidden");
      content.classList.remove("hidden");
    } catch (e) {
      content.classList.add("hidden");
      status.classList.remove("hidden");
      status.textContent = `Couldn't render ${year}: ${e.message}.`;
    }
  };

  selector.querySelectorAll(".year-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      selector.querySelectorAll(".year-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      showYear(btn.dataset.year);
    });
  });

  showYear(defaultYear);
}

// ---------- Draft History tab ----------

function draftPickRow(pick) {
  return `
    <tr>
      <td class="draft-pick-label">${pick.label}</td>
      <td>${pick.team_name}</td>
      <td>${pick.name}</td>
      <td>${pick.player_name}</td>
      <td>${pick.position || "&mdash;"}</td>
    </tr>`;
}

function renderDraft(draft) {
  const round1 = draft.picks.filter((p) => p.round === 1);
  const round1and2 = draft.picks.filter((p) => p.round === 1 || p.round === 2);

  document.querySelector("#draft-round1-table tbody").innerHTML = round1.map(draftPickRow).join("");
  document.querySelector("#draft-round1-2-table tbody").innerHTML = round1and2.map(draftPickRow).join("");
}

async function initDraftTab() {
  const status = document.getElementById("draft-status");
  const content = document.getElementById("draft-content");
  const selector = document.getElementById("draft-year-selector");

  let drafts;
  try {
    const overview = await loadOverview();
    drafts = overview.drafts;
  } catch (e) {
    status.textContent = `Couldn't load data: ${e.message}. Check your connection and reload.`;
    return;
  }

  if (!drafts || drafts.length === 0) {
    status.textContent = "No draft data available yet.";
    return;
  }

  const bySeason = {};
  drafts.forEach((d) => (bySeason[d.season] = d));
  const years = Object.keys(bySeason).sort((a, b) => b - a);
  const defaultYear = years[0];

  selector.innerHTML = years
    .map((y) => `<button class="year-btn${y === defaultYear ? " active" : ""}" data-year="${y}">${y}</button>`)
    .join("");

  const showYear = (year) => {
    try {
      renderDraft(bySeason[year]);
      status.classList.add("hidden");
      content.classList.remove("hidden");
    } catch (e) {
      content.classList.add("hidden");
      status.classList.remove("hidden");
      status.textContent = `Couldn't render ${year}: ${e.message}.`;
    }
  };

  selector.querySelectorAll(".year-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      selector.querySelectorAll(".year-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      showYear(btn.dataset.year);
    });
  });

  showYear(defaultYear);
}

async function init() {
  await loadCurrentNames();
  loadHomeStatus();
  initHistoryTab();
  initOverviewTab();
  initPointsTabs();
  initHeadToHeadTab();
  initChampionshipTab();
  initDraftTab();
}

init();
