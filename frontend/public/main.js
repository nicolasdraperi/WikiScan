/* =========================
   MAP INIT
========================= */
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
    <h4>Activité Wikipédia</h4>
    <div><span style="background:#e5f5e0"></span> 1–4</div>
    <div><span style="background:#a1d99b"></span> 5–14</div>
    <div><span style="background:#41ab5d"></span> 15–29</div>
    <div><span style="background:#006d2c"></span> 30+</div>
  `;
  return div;
};

legend.addTo(map);

/* =========================
   WIKI → PAYS (ISO_A2_EH)
========================= */
const wikiToCountry = {
  arwiki: "EG",      // Égypte (monde arabe, symbolique)
  arywiki: "MA",     // Maroc
  cywiki: "GB",      // Pays de Galles → Royaume-Uni
  dewiki: "DE",      // Allemagne
  elwiki: "GR",      // Grèce
  enwiki: "GB",      // Communauté anglophone (symbolique UK)
  eswiki: "ES",      // Espagne
  frwiki: "FR",      // France
  hewiki: "IL",      // Israël
  hiwiki: "IN",      // Inde
  huwiki: "HU",      // Hongrie
  idwiki: "ID",      // Indonésie
  itwiki: "IT",      // Italie
  jawiki: "JP",      // Japon
  ltwiki: "LT",      // Lituanie
  nlwiki: "NL",      // Pays-Bas
  papwiki: "NL",     // Curaçao → Pays-Bas (symbolique)
  rowiki: "RO",      // Roumanie
  ruwiki: "RU",      // Russie
  tawiki: "IN",      // Tamil → Inde
  trwiki: "TR",      // Turquie
  ttwiki: "RU",      // Tatar → Russie (symbolique)
  ukwiki: "UA",      // Ukraine
  urwiki: "PK",      // Pakistan
  viwiki: "VN",      // Vietnam
  zhwiki: "CN"       // Chine
};


/* =========================
   ÉTAT GLOBAL
========================= */
let RAW_EVENTS = [];
let countryStats = {};
let countryWikis = {};
let countryLayer = null;

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
   UTILS
========================= */
function getCountryColor(count) {
  if (count === 0) return "#eeeeee";
  if (count < 5) return "#e5f5e0";
  if (count < 15) return "#a1d99b";
  if (count < 30) return "#41ab5d";
  return "#006d2c";
}

function getCountryName(props) {
  return (
    props.name ||
    "Pays inconnu"
  );
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
   LOAD DATA
========================= */
fetch("/data/recentchange_180s.json")
  .then(res => res.json())
  .then(events => {
    RAW_EVENTS = events;
    replayEvents(events);
  });

/* =========================
   REPLAY (SIMULATION LIVE)
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
   RECOMPUTE (CŒUR DATA-VIZ)
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

  counterEl.textContent = Object.values(countryStats)
    .reduce((a, b) => a + b, 0);

  if (!countryLayer) return;

  countryLayer.eachLayer(layer => {
    const code = layer.feature.properties.iso_a2_eh;
    const count = countryStats[code] || 0;
    const name = getCountryName(layer.feature.properties);

    const wikis = countryWikis[code]
      ? [...countryWikis[code]].join(", ")
      : "Aucun";

    layer.setStyle({
      fillColor: getCountryColor(count)
    });

    layer.setTooltipContent(
      `<b>${name}</b><br>
       Événements : ${count}<br>
       Wikis : ${wikis}`
    );
  });
}
