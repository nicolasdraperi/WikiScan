/* =========================
   CONFIG
========================= */
const MAX_EVENTS = 5000;
const TOP_N = 10;
const N_EDITS_INSTABLE = 5;

const EDITORIAL_TYPES = new Set(["edit", "new", "categorize"]);

const NS_LABELS = {
  0: "Article",
  1: "Discussion (article)",
  2: "Utilisateur",
  3: "Discussion (utilisateur)",
  4: "Projet",
  5: "Discussion (projet)",
  6: "Fichier",
  10: "Modèle",
  14: "Catégorie"
};

const REVERT_HINTS = [
  "revert", "rv", "rvv", "undo", "undid",
  "rollback", "révocation", "annulation"
];

/* =========================
   GLOBAL STATE
========================= */
const events = [];

const byWiki = {};
const byPage = {};
const byNamespace = {};
const revertsByPage = {};

let botCount = 0;
let humanCount = 0;
let anonCount = 0;
let accountCount = 0;

let editorialTotal = 0;
let editorialReverts = 0;

/* =========================
   CHARTS
========================= */
const wikiChart = new Chart(document.getElementById("wikiChart"), {
  type: "doughnut",
  data: {
    labels: [],
    datasets: [{
      data: [],
      backgroundColor: [
        "#e94560", "#4fc3f7", "#00c853", "#ffb300",
        "#ab47bc", "#26a69a", "#ef5350", "#5c6bc0",
        "#8d6e63", "#78909c"
      ]
    }]
  },
options: {
  plugins: {
    legend: {
      position: "bottom",
      labels: {
        boxWidth: 12,
        padding: 15,
        color: "#e5e7eb",
        font: {
          size: 11
        }
      }
    }
  }
}
});

const botChart = new Chart(document.getElementById("botChart"), {
  type: "pie",
  data: { labels: ["Bots", "Humains"], datasets: [{ data: [0, 0] }] }
});

const anonChart = new Chart(document.getElementById("anonChart"), {
  type: "pie",
  data: { labels: ["Anonymes", "Comptes"], datasets: [{ data: [0, 0] }] }
});

const pagesChart = new Chart(document.getElementById("pagesChart"), {
  type: "bar",
  data: { labels: [], datasets: [{ label: "Éditions", data: [] }] },
  options: { indexAxis: "y" }
});

const namespaceChart = new Chart(document.getElementById("namespaceChart"), {
  type: "bar",
  data: { labels: [], datasets: [{ label: "Événements", data: [] }] }
});

/* =========================
   WEBSOCKET
========================= */
function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.host}`);
  const statusEl = document.getElementById("status");

  ws.onopen = () => statusEl.textContent = "LIVE";
  ws.onmessage = msg => handleEvent(JSON.parse(msg.data));
  ws.onclose = () => {
    statusEl.textContent = "DISCONNECTED";
    setTimeout(connectWebSocket, 3000);
  };
}

/* =========================
   UTILS
========================= */
function isIP(user) {
  return /^(?:\d{1,3}\.){3}\d{1,3}$/.test(user || "");
}

function looksLikeRevert(e) {
  const comment = (e.comment || "").toLowerCase();
  if (REVERT_HINTS.some(k => comment.includes(k))) return true;

  const tags = e.tags || [];
  return tags.some(t =>
    String(t).toLowerCase().includes("revert") ||
    String(t).toLowerCase().includes("undo") ||
    String(t).toLowerCase().includes("rollback")
  );
}

/* =========================
   EVENT HANDLING
========================= */
function handleEvent(e) {
  events.push(e);
  if (events.length > MAX_EVENTS) events.shift();

  // Wiki
  if (e.wiki) byWiki[e.wiki] = (byWiki[e.wiki] || 0) + 1;

  // Page
  if (e.title) byPage[e.title] = (byPage[e.title] || 0) + 1;

  // Namespace
  if (typeof e.namespace === "number") {
    byNamespace[e.namespace] = (byNamespace[e.namespace] || 0) + 1;
  }

  // Bot / Human
  e.bot ? botCount++ : humanCount++;

  // Anon / Account
  isIP(e.user) ? anonCount++ : accountCount++;

  // Reverts
  const isEditorial = EDITORIAL_TYPES.has(e.type);
  if (isEditorial) {
    editorialTotal++;
    if (looksLikeRevert(e)) {
      editorialReverts++;
      revertsByPage[e.title] = (revertsByPage[e.title] || 0) + 1;
    }
  }

  recomputeCharts();
}

/* =========================
   RECOMPUTE
========================= */
function recomputeCharts() {
  // Wikis
  const topWikis = Object.entries(byWiki).sort((a,b)=>b[1]-a[1]).slice(0, TOP_N);
  wikiChart.data.labels = topWikis.map(w=>w[0]);
  wikiChart.data.datasets[0].data = topWikis.map(w=>w[1]);
  wikiChart.update();

  // Bots
  botChart.data.datasets[0].data = [botCount, humanCount];
  botChart.update();

  // Anon
  anonChart.data.datasets[0].data = [anonCount, accountCount];
  anonChart.update();

  // Pages
  const topPages = Object.entries(byPage).sort((a,b)=>b[1]-a[1]).slice(0, TOP_N);
  pagesChart.data.labels = topPages.map(p=>p[0]);
  pagesChart.data.datasets[0].data = topPages.map(p=>p[1]);
  pagesChart.update();

  // Namespace
  const topNS = Object.entries(byNamespace)
    .sort((a,b)=>b[1]-a[1])
    .slice(0, TOP_N);

  namespaceChart.data.labels = topNS.map(
    ([ns]) => NS_LABELS[ns] || `NS ${ns}`
  );
  namespaceChart.data.datasets[0].data = topNS.map(n=>n[1]);
  namespaceChart.update();

  // % revertés (affichage texte)
  const pct = editorialTotal
    ? ((editorialReverts / editorialTotal) * 100).toFixed(2)
    : "0.00";

  document.getElementById("revertRate").textContent = `${pct} %`;
}

/* =========================
   START
========================= */
connectWebSocket();
