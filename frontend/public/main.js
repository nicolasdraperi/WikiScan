const map = L.map("map").setView([20, 0], 2);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "© OpenStreetMap"
}).addTo(map);

/* =========================
   LÉGENDE
========================= */
const legend = L.control({ position: "bottomright" });

legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = `
    <h4>Activité</h4>
    <div><span style="background: green"></span> 1–5 événements</div>
    <div><span style="background: orange"></span> 6–15 événements</div>
    <div><span style="background: red"></span> +15 événements</div>
  `;
  return div;
};

legend.addTo(map);

/* =========================
   WIKI → COORDONNÉES
========================= */
const wikiLocations = {
  // 🌍 Wikipédia par langue
  arwiki: [31.8, 35.2],          // Monde arabe
  arywiki: [31.8, -7.1],         // Maroc
  cywiki: [52.1, -3.8],          // Pays de Galles
  dewiki: [51.1, 10.4],          // Allemagne
  elwiki: [39.1, 21.8],          // Grèce
  enwiki: [51.5, -0.09],         // Monde anglophone (UK)
  eswiki: [40.4, -3.7],          // Espagne
  frwiki: [46.6, 2.2],           // France
  hewiki: [31.0, 35.0],          // Israël
  hiwiki: [22.9, 78.9],          // Inde (Hindi)
  huwiki: [47.1, 19.5],          // Hongrie
  idwiki: [-2.5, 118.0],         // Indonésie
  itwiki: [42.8, 12.5],          // Italie
  jawiki: [36.2, 138.2],         // Japon
  ltwiki: [55.2, 23.9],          // Lituanie
  nlwiki: [52.1, 5.3],           // Pays-Bas
  papwiki: [12.2, -69.0],        // Papiamento (Caraïbes)
  rowiki: [45.9, 24.9],          // Roumanie
  ruwiki: [61.5, 105.3],         // Russie
  tawiki: [10.8, 78.7],          // Tamil (Inde)
  trwiki: [39.0, 35.2],          // Turquie
  ttwiki: [55.8, 49.1],          // Tatarstan
  ukwiki: [49.0, 31.4],          // Ukraine
  urwiki: [30.3, 69.3],          // Pakistan (Ourdou)
  viwiki: [14.1, 108.3],         // Vietnam
  zhwiki: [35.8, 104.1],         // Monde sinophone (Chine)
/*
  // 📚 Wiktionary
  dewiktionary: [51.1, 10.4],
  enwiktionary: [51.5, -0.09],
  frwiktionary: [46.6, 2.2],
  idwiktionary: [-2.5, 118.0],
  kuwiktionary: [36.5, 44.0],    // Kurdistan
  mgwiktionary: [-18.8, 47.5],   // Madagascar
  swwiktionary: [-6.4, 35.5],    // Swahili
  trwiktionary: [39.0, 35.2],

  // Wikiquote / Wikisource / Wikinews
  enwikiquote: [51.5, -0.09],
  plwikisource: [52.2, 21.0],
  ptwikinews: [-14.2, -51.9],
  ukwikisource: [49.0, 31.4],

  // Projets transverses
  commonswiki: [0, 0],           // Wikimedia Commons (global)
  metawiki: [0, 0],              // Meta-Wiki
  labswiki: [0, 0],              // Wikitech
  wikidatawiki: [0, 0]           // Wikidata (global)
*/
};


/* =========================
   ÉTAT GLOBAL
========================= */
let RAW_EVENTS = [];
let FILTERED_EVENTS = [];

const wikiMarkers = {};
const counterEl = document.getElementById("counter");

let showBots = true;
let showHumans = true;

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
   DATA LOAD
========================= */
fetch("/data/recentchange_15s.json")
  .then(res => res.json())
  .then(events => {
    RAW_EVENTS = events;
    replayEvents(events);
  });

/* =========================
   UTILS
========================= */
function getColor(count) {
  if (count < 5) return "green";
  if (count < 15) return "orange";
  return "red";
}

/* =========================
   REPLAY (1 seule fois)
========================= */
function replayEvents(events) {
  let index = 0;
  const SPEED_MS = 30;

  const interval = setInterval(() => {
    if (index >= events.length) {
      clearInterval(interval);
      return;
    }

    RAW_EVENTS[index].__played = true;
    index++;

    recompute();
  }, SPEED_MS);
}

/* =========================
   RECOMPUTE (LE CŒUR)
========================= */
function recompute() {
  // Nettoyage
  for (const key in wikiMarkers) {
    map.removeLayer(wikiMarkers[key]);
    delete wikiMarkers[key];
  }

  const wikiStats = {};
  let total = 0;

  FILTERED_EVENTS = RAW_EVENTS.filter(e => {
    if (!e.__played) return false;
    if (e.bot && !showBots) return false;
    if (!e.bot && !showHumans) return false;
    if (!wikiLocations[e.wiki]) return false;
    return true;
  });

  FILTERED_EVENTS.forEach(event => {
    const wiki = event.wiki;
    wikiStats[wiki] = (wikiStats[wiki] || 0) + 1;
    total++;
  });

  counterEl.textContent = total;

  for (const wiki in wikiStats) {
    const count = wikiStats[wiki];
    const coords = wikiLocations[wiki];

    wikiMarkers[wiki] = L.circleMarker(coords, {
      radius: 6 + Math.log(count + 1) * 6,
      color: getColor(count),
      fillOpacity: 0.7
    }).addTo(map);

    wikiMarkers[wiki].bindPopup(`
      <b>${wiki}</b><br>
      Total événements : ${count}
    `);
  }
}
