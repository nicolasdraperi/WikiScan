/* =========================
   MAP INIT
========================= */
const map = L.map("map").setView([20, 0], 2);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

/* =========================
   LEGENDE
========================= */
const legend = L.control({ position: "bottomright" });

legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = `
    <h4>Activite relative</h4>
    <div><span style="background:#e5f5e0"></span> Faible</div>
    <div><span style="background:#a1d99b"></span> Moyenne</div>
    <div><span style="background:#41ab5d"></span> Elevee</div>
    <div><span style="background:#006d2c"></span> Tres elevee</div>
  `;
  return div;
};

legend.addTo(map);

/* =========================
   WIKI -> PAYS (ISO_A2_EH)
========================= */
const wikiToCountry = {
  arwiki: "EG",
  arywiki: "MA",
  cywiki: "GB",
  dewiki: "DE",
  elwiki: "GR",
  enwiki: "GB",
  eswiki: "ES",
  frwiki: "FR",
  hewiki: "IL",
  hiwiki: "IN",
  huwiki: "HU",
  idwiki: "ID",
  itwiki: "IT",
  jawiki: "JP",
  kowiki: "KR",
  ltwiki: "LT",
  nlwiki: "NL",
  papwiki: "NL",
  plwiki: "PL",
  ptwiki: "PT",
  rowiki: "RO",
  ruwiki: "RU",
  svwiki: "SE",
  tawiki: "IN",
  thwiki: "TH",
  trwiki: "TR",
  ttwiki: "RU",
  ukwiki: "UA",
  urwiki: "PK",
  viwiki: "VN",
  zhwiki: "CN"
};

/* =========================
   ETAT GLOBAL
========================= */
let RAW_EVENTS = [];
let countryStats = {};
let countryWikis = {};
let countryLayer = null;

const counterEl = document.getElementById("counter");
const statusEl = document.getElementById("status");
const rateEl = document.getElementById("rate");

let showBots = true;
let showHumans = true;

// Stats pour le debit
let eventCount = 0;
let lastCountTime = Date.now();
let currentRate = 0;

/* =========================
   CONTROLS
========================= */
document.getElementById("showBots").addEventListener("change", e => {
  showBots = e.target.checked;
  recompute();
});

document.getElementById("showHumans").addEventListener("change", e => {
  showHumans = e.target.checked;
  recompute();
});

/* =========================
   UTILS
========================= */
function getCountryColor(count, thresholds) {
  if (count === 0) return "#eeeeee";
  if (count <= thresholds.q1) return "#e5f5e0";
  if (count <= thresholds.q2) return "#a1d99b";
  if (count <= thresholds.q3) return "#41ab5d";
  return "#006d2c";
}

function getCountryName(props) {
  return props.name || "Pays inconnu";
}

/* =========================
   LOAD GEOJSON
========================= */
fetch("/data/countries.geo.json")
  .then(res => res.json())
  .then(geojson => {
    countryLayer = L.geoJSON(geojson, {
      style: () => ({
        fillColor: "#eeeeee",
        weight: 1,
        color: "#555",
        fillOpacity: 0.7
      }),
      onEachFeature: (feature, layer) => {
        const name = getCountryName(feature.properties);
        layer.bindTooltip(
          `<b>${name}</b><br>Evenements : 0`,
          { sticky: true }
        );
      }
    }).addTo(map);
  });

/* =========================
   WEBSOCKET LIVE
========================= */
function connectWebSocket() {
  const wsUrl = `ws://${window.location.host}`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log("[WS] Connecte au serveur");
    if (statusEl) statusEl.textContent = "LIVE";
    if (statusEl) statusEl.classList.add("live");
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleEvent(data);
    } catch (err) {
      console.error("[WS] Erreur parsing:", err);
    }
  };

  ws.onclose = () => {
    console.log("[WS] Deconnecte, reconnexion dans 3s...");
    if (statusEl) statusEl.textContent = "DECONNECTE";
    if (statusEl) statusEl.classList.remove("live");
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = (err) => {
    console.error("[WS] Erreur:", err);
    ws.close();
  };
}

/* =========================
   HANDLE EVENT (LIVE)
========================= */
function handleEvent(e) {
  // Ajouter aux evenements bruts
  RAW_EVENTS.push(e);
  
  // Limiter la taille du buffer (garder les 5000 derniers)
  if (RAW_EVENTS.length > 5000) {
    RAW_EVENTS = RAW_EVENTS.slice(-5000);
  }
  
  // Marquer comme joue
  e.__played = true;
  
  // Incrementer le compteur
  eventCount++;
  
  // Recalculer le debit toutes les secondes
  const now = Date.now();
  if (now - lastCountTime >= 1000) {
    currentRate = eventCount;
    eventCount = 0;
    lastCountTime = now;
    if (rateEl) rateEl.textContent = currentRate;
  }
  
  // Mettre a jour la carte
  recompute();
}

/* =========================
   RECOMPUTE (COEUR DATA-VIZ)
========================= */
function recompute() {
  countryStats = {};
  countryWikis = {};

  RAW_EVENTS.forEach(e => {
    if (!e.__played) return;
    if (e.bot && !showBots) return;
    if (!e.bot && !showHumans) return;

    const country = wikiToCountry[e.wiki];
    if (!country) return;

    countryStats[country] = (countryStats[country] || 0) + 1;

    if (!countryWikis[country]) {
      countryWikis[country] = new Set();
    }
    countryWikis[country].add(e.wiki);
  });

  const values = Object.values(countryStats).sort((a, b) => a - b);

  function quantile(arr, q) {
    if (!arr.length) return 0;
    const pos = (arr.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    return arr[base + 1] !== undefined
      ? arr[base] + rest * (arr[base + 1] - arr[base])
      : arr[base];
  }

  const thresholds = values.length
    ? {
        q1: quantile(values, 0.25),
        q2: quantile(values, 0.50),
        q3: quantile(values, 0.75)
      }
    : { q1: 0, q2: 0, q3: 0 };

  counterEl.textContent = values.reduce((a, b) => a + b, 0);

  if (!countryLayer) return;

  countryLayer.eachLayer(layer => {
    const code = layer.feature.properties.iso_a2_eh;
    const count = countryStats[code] || 0;
    const name = getCountryName(layer.feature.properties);

    const wikis = countryWikis[code]
      ? [...countryWikis[code]].join(", ")
      : "Aucun";

    layer.setStyle({
      fillColor: getCountryColor(count, thresholds)
    });

    layer.setTooltipContent(
      `<b>${name}</b><br>
       Evenements : ${count}<br>
       Wikis : ${wikis}`
    );
  });
}

/* =========================
   DEMARRAGE
========================= */
connectWebSocket();
