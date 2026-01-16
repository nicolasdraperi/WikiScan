/* =========================
   MAP INIT
========================= */
const map = L.map("map").setView([0, 0], 2);

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
    <h4>Activité relative</h4>
    <div><span style="background:#e5f5e0"></span> Faible</div>
    <div><span style="background:#a1d99b"></span> Moyenne</div>
    <div><span style="background:#41ab5d"></span> Élevée</div>
    <div><span style="background:#006d2c"></span> Très élevée</div>
  `;
  return div;
};

legend.addTo(map);

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

let selectedEventType = "recentchange"; // par défaut
let MODE = "live"; // "live" | "offline"


// Stats débit
let eventCount = 0;
let lastCountTime = Date.now();

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

document.querySelectorAll('input[name="eventType"]').forEach(input => {
  input.addEventListener("change", e => {
    selectedEventType = e.target.value;

    if (MODE === "offline") {
      loadOfflineData();
    } else {
      recompute();
    }
  });
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
          `<b>${name}</b><br>Événements : 0`,
          { sticky: true }
        );
      }
    }).addTo(map);
  });

/* =========================
   WEBSOCKET LIVE
========================= */
function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.host}`);

  ws.onopen = () => {
    console.log("[WS] Connecté");
    statusEl.textContent = "LIVE";
    statusEl.classList.add("live");
  };

  ws.onmessage = (event) => {
    try {
      handleEvent(JSON.parse(event.data));
    } catch {
      /* ignore */
    }
  };

  ws.onclose = () => {
    statusEl.textContent = "DÉCONNECTÉ";
    statusEl.classList.remove("live");
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => ws.close();
}

/* =========================
   HANDLE EVENT
========================= */
function handleEvent(e) {
  if (MODE === "offline") return;

  console.log("EVENT:", e.event_source, e.wiki, e.country_code);
  RAW_EVENTS.push(e);
  if (RAW_EVENTS.length > 5000) RAW_EVENTS.shift();

  eventCount++;
  const now = Date.now();
  if (now - lastCountTime >= 1000) {
    rateEl.textContent = eventCount;
    eventCount = 0;
    lastCountTime = now;
  }

  recompute();
}


/* =========================
   RECOMPUTE (CORE DATA-VIZ)
========================= */
function recompute() {
  countryStats = {};
  countryWikis = {};

RAW_EVENTS.forEach(e => {
  if (e.event_source !== selectedEventType) return;

  if (MODE === "live") {
    if (e.bot && !showBots) return;
    if (!e.bot && !showHumans) return;
  }

  const country = e.country_code;
  if (!country) return;

  countryStats[country] = (countryStats[country] || 0) + 1;

  if (!countryWikis[country]) {
    countryWikis[country] = new Set();
  }
  countryWikis[country].add(e.wiki || "offline");
});


  const values = Object.values(countryStats)
  .filter(v => v > 0)
  .sort((a, b) => a - b);


  const quantile = (arr, q) => {
    if (!arr.length) return 0;
    const pos = (arr.length - 1) * q;
    const base = Math.floor(pos);
    const rest = pos - base;
    return arr[base + 1] !== undefined
      ? arr[base] + rest * (arr[base + 1] - arr[base])
      : arr[base];
  };

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

    layer.setStyle({
      fillColor: getCountryColor(count, thresholds)
    });

    const wikis = countryWikis[code]
      ? [...countryWikis[code]].join(", ")
      : "Aucun";

    layer.setTooltipContent(
      `<b>${getCountryName(layer.feature.properties)}</b><br>
       Événements : ${count}<br>
       Wikis : ${wikis}`
    );
  });
}

/* =========================
   START
========================= */
connectWebSocket();

/* =========================
    OFFLINE DATA
========================= */
async function loadOfflineData() {
  const res = await fetch(`/api/offline/${selectedEventType}/by_country`);
  const data = await res.json();

  RAW_EVENTS = [];

  data.forEach(row => {
    for (let i = 0; i < row.count; i++) {
      RAW_EVENTS.push({
        country_code: row.country_code,
        wiki: "offline",
        bot: false,
        event_source: selectedEventType
      });
    }
  });

  recompute();
}
function switchMode(mode) {
  MODE = mode;

  if (MODE === "offline") {
    statusEl.textContent = "OFFLINE";
    statusEl.classList.remove("live");
    rateEl.textContent = "-";

    document.getElementById("showBots").disabled = true;
    document.getElementById("showHumans").disabled = true;

    loadOfflineData();
  } else {
    statusEl.textContent = "LIVE";
    statusEl.classList.add("live");

    document.getElementById("showBots").disabled = false;
    document.getElementById("showHumans").disabled = false;

    RAW_EVENTS = [];
  }
}


