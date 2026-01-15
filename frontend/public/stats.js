/* =========================
   GLOBAL STATE
========================= */
const events = [];
const MAX_EVENTS = 5000;

const byWiki = {};
const byPage = {};
let botCount = 0;
let humanCount = 0;
let anonCount = 0;
let accountCount = 0;

/* =========================
   CHARTS
========================= */
const wikiChart = new Chart(document.getElementById("wikiChart"), {
  type: "doughnut",
  data: { labels: [], datasets: [{ data: [] }] },
  options: { plugins: { legend: { position: "bottom" } } }
});

const botChart = new Chart(document.getElementById("botChart"), {
  type: "pie",
  data: {
    labels: ["Bots", "Humains"],
    datasets: [{ data: [0, 0] }]
  }
});

const anonChart = new Chart(document.getElementById("anonChart"), {
  type: "pie",
  data: {
    labels: ["Anonymes (IP)", "Comptes"],
    datasets: [{ data: [0, 0] }]
  }
});

const pagesChart = new Chart(document.getElementById("pagesChart"), {
  type: "bar",
  data: { labels: [], datasets: [{ label: "Éditions", data: [] }] },
  options: { indexAxis: "y" }
});

/* =========================
   WEBSOCKET
========================= */
function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.host}`);
  const statusEl = document.getElementById("status");

  ws.onopen = () => {
    statusEl.textContent = "LIVE";
  };

  ws.onmessage = (msg) => {
    const e = JSON.parse(msg.data);
    handleEvent(e);
  };

  ws.onclose = () => {
    statusEl.textContent = "DISCONNECTED";
    setTimeout(connectWebSocket, 3000);
  };
}

/* =========================
   EVENT HANDLING
========================= */
function isIP(user) {
  return /^(?:\d{1,3}\.){3}\d{1,3}$/.test(user || "");
}

function handleEvent(e) {
  events.push(e);
  if (events.length > MAX_EVENTS) events.shift();

  // Wiki
  if (e.wiki) {
    byWiki[e.wiki] = (byWiki[e.wiki] || 0) + 1;
  }

  // Page
  if (e.title) {
    byPage[e.title] = (byPage[e.title] || 0) + 1;
  }

  // Bot / Human
  if (e.bot) botCount++;
  else humanCount++;

  // Anon / Account
  if (isIP(e.user)) anonCount++;
  else accountCount++;

  recomputeCharts();
}

/* =========================
   RECOMPUTE
========================= */
function recomputeCharts() {
  // Wikis
  const topWikis = Object.entries(byWiki)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  wikiChart.data.labels = topWikis.map(w => w[0]);
  wikiChart.data.datasets[0].data = topWikis.map(w => w[1]);
  wikiChart.update();

  // Bots
  botChart.data.datasets[0].data = [botCount, humanCount];
  botChart.update();

  // Anon
  anonChart.data.datasets[0].data = [anonCount, accountCount];
  anonChart.update();

  // Pages
  const topPages = Object.entries(byPage)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  pagesChart.data.labels = topPages.map(p => p[0]);
  pagesChart.data.datasets[0].data = topPages.map(p => p[1]);
  pagesChart.update();
}

/* =========================
   START
========================= */
connectWebSocket();
