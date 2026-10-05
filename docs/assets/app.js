const SITE_DATA = {
  Piolenc: {
    label: "Piolenc, France", coordinates: [4.7280, 44.1555], pairs: { l: 6, c: 129 },
    copol: { l: [11, 17, 25], c: [19, 26, 32] },
    dual: { l: [13, 18, 24], c: [23, 30, 38] },
    reading: {
      dual: "The largest observed separation: the preliminary L-band MD95 is 14 m lower than C-band.",
      copol: "The co-pol boundary also favours L-band here, with a 7 m MD95 separation."
    }
  },
  Sirindhorn: {
    label: "Sirindhorn, Thailand", coordinates: [105.4440, 15.1980], pairs: { l: 3, c: 92 },
    copol: { l: [15, 21, 24], c: [16, 21, 30] },
    dual: { l: [16, 21, 25], c: [17, 22, 30] },
    reading: {
      dual: "L-band lowers the point MD95 by 5 m, but only three NISAR test pairs support this site estimate.",
      copol: "MD50 and MD80 are similar; separation appears only near the 95% boundary."
    }
  },
  Tengeh: {
    label: "Tengeh, Singapore", coordinates: [103.6430, 1.3500], pairs: { l: 6, c: 49 },
    copol: { l: [12, 18, 25], c: [12, 17, 21] },
    dual: { l: [16, 26, 32], c: [18, 24, 32] },
    reading: {
      dual: "Both sensors reach the same 32 m MD95; intermediate boundaries differ only slightly.",
      copol: "C-band reaches MD95 4 m earlier, rejecting a universal L-band advantage."
    }
  }
};

const PLOT_DATA = {
  copol: {
    src: "assets/research/cross_sensor_copol_20m.png",
    alt: "Pooled co-polarized NISAR L-band and Sentinel-1 C-band detection curves at 20 metre support",
    rows: [
      ["NISAR L", [11, "11–15"], [20, "16–23"], [25, "22–26"]],
      ["Sentinel-1 C", [17, "16–17"], [23, "22–23"], [30, "29–32"]]
    ]
  },
  dual: {
    src: "assets/research/cross_sensor_dual_20m.png",
    alt: "Pooled dual-polarization consensus NISAR L-band and Sentinel-1 C-band detection curves at 20 metre support",
    rows: [
      ["NISAR L", [14, "12–17"], [21, "18–26"], [27, "23–32"]],
      ["Sentinel-1 C", [20, "20–21"], [27, "26–28"], [36, "34–38"]]
    ]
  }
};

let detector = "dual";
let selectedSite = "Piolenc";
let map;

function mdPointGeoJSON() {
  const features = [];
  Object.entries(SITE_DATA).forEach(([site, record]) => {
    const [lon, lat] = record.coordinates;
    const values = record[detector];
    [
      { sensor: "NISAR L-band", code: "L", md95: values.l[2], offset: -1.05 },
      { sensor: "Sentinel-1 C-band", code: "C", md95: values.c[2], offset: 1.05 }
    ].forEach(item => features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon + item.offset, lat] },
      properties: { site, sensor: item.sensor, code: item.code, md95: item.md95 }
    }));
  });
  return { type: "FeatureCollection", features };
}

function pointGeoJSON() {
  return {
    type: "FeatureCollection",
    features: Object.entries(SITE_DATA).map(([site, record]) => ({
      type: "Feature", geometry: { type: "Point", coordinates: record.coordinates },
      properties: { site, label: record.label }
    }))
  };
}

function initMap() {
  const mapNode = document.getElementById("map");
  if (!mapNode || !window.maplibregl) {
    if (mapNode) mapNode.innerHTML = "Interactive map unavailable. The exact site values remain in the adjacent chart.";
    return;
  }
  map = new maplibregl.Map({
    container: "map", style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    center: [69, 22], zoom: 1.35, pitch: 0, bearing: 0,
    attributionControl: false, antialias: true
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
  map.on("load", () => {
    map.addSource("md-points", { type: "geojson", data: mdPointGeoJSON() });
    map.addLayer({
      id: "md-points", type: "circle", source: "md-points",
      paint: {
        "circle-color": ["match", ["get", "code"], "L", "#d94b43", "#2579b5"],
        "circle-radius": ["interpolate", ["linear"], ["get", "md95"], 15, 7, 40, 15],
        "circle-opacity": 0.88, "circle-stroke-color": "#f7f1e4", "circle-stroke-width": 1
      }
    });
    map.addSource("sites", { type: "geojson", data: pointGeoJSON() });
    map.addLayer({
      id: "site-halos", type: "circle", source: "sites",
      paint: { "circle-radius": 8, "circle-color": "#121b26", "circle-stroke-width": 2, "circle-stroke-color": "#f0d479" }
    });
    map.addLayer({
      id: "site-labels", type: "symbol", source: "sites",
      layout: { "text-field": ["get", "site"], "text-size": 12, "text-offset": [0, 1.35], "text-anchor": "top", "text-allow-overlap": true },
      paint: { "text-color": "#f7f1e4", "text-halo-color": "#121b26", "text-halo-width": 1.5 }
    });
    map.on("click", "md-points", event => {
      const site = event.features?.[0]?.properties?.site;
      if (site) selectSite(site, true);
    });
    map.on("mouseenter", "md-points", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "md-points", () => { map.getCanvas().style.cursor = ""; });
  });
}

function updateMap() {
  const source = map && map.getSource("md-points");
  if (source) source.setData(mdPointGeoJSON());
}

function renderBars() {
  const values = SITE_DATA[selectedSite][detector];
  const labels = ["MD50", "MD80", "MD95"];
  const max = 40;
  const html = labels.map((label, index) => `
    <div class="bar-group">
      <div class="bar-label"><span>${label}</span><strong>${values.l[index]} m · ${values.c[index]} m</strong></div>
      <div class="bar-track" aria-label="NISAR ${label} ${values.l[index]} metres"><div class="bar-fill l" style="width:${values.l[index] / max * 100}%"></div></div>
      <div class="bar-track" aria-label="Sentinel-1 ${label} ${values.c[index]} metres"><div class="bar-fill c" style="width:${values.c[index] / max * 100}%"></div></div>
    </div>`).join("");
  document.getElementById("site-bars").innerHTML = `${html}<div class="bar-axis"><span>0 m</span><span>40 m</span></div>`;
}

function renderPanel() {
  const record = SITE_DATA[selectedSite];
  document.getElementById("site-name").textContent = record.label;
  document.getElementById("site-context").textContent = `${record.pairs.l} NISAR and ${record.pairs.c} Sentinel-1 held-out test pairs at 20 m.`;
  document.getElementById("site-reading").textContent = record.reading[detector];
  renderBars();
  document.querySelectorAll("[data-site]").forEach(button => {
    const active = button.dataset.site === selectedSite;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function selectSite(site, fly = false) {
  selectedSite = site;
  renderPanel();
  updateMap();
  if (fly && map) map.flyTo({ center: SITE_DATA[site].coordinates, zoom: 3.9, pitch: 58, duration: 1100 });
}

document.querySelectorAll("[data-detector]").forEach(button => button.addEventListener("click", () => {
  detector = button.dataset.detector;
  document.querySelectorAll("[data-detector]").forEach(peer => {
    const active = peer === button;
    peer.classList.toggle("active", active);
    peer.setAttribute("aria-pressed", String(active));
  });
  renderPanel();
  updateMap();
}));

document.querySelectorAll("[data-site]").forEach(button => button.addEventListener("click", () => selectSite(button.dataset.site, true)));

document.querySelectorAll(".lab-button").forEach(button => button.addEventListener("click", () => {
  document.getElementById("lab-image").src = button.dataset.image;
  document.getElementById("lab-image").alt = button.dataset.alt;
  document.getElementById("lab-caption").innerHTML = button.dataset.caption;
  document.querySelectorAll(".lab-button").forEach(peer => peer.classList.toggle("active", peer === button));
}));

document.querySelectorAll(".plot-button").forEach(button => button.addEventListener("click", () => {
  const plot = PLOT_DATA[button.dataset.plot];
  const image = document.getElementById("result-plot");
  image.src = plot.src;
  image.alt = plot.alt;
  document.getElementById("pooled-values").innerHTML = plot.rows.map((row, index) =>
    `<tr class="${index === 0 ? "l-row" : "c-row"}"><th>${row[0]}</th>${row.slice(1).map(cell => `<td>${cell[0]} m<br><small>${cell[1]}</small></td>`).join("")}</tr>`
  ).join("");
  document.querySelectorAll(".plot-button").forEach(peer => {
    const active = peer === button;
    peer.classList.toggle("active", active);
    peer.setAttribute("aria-pressed", String(active));
  });
}));

const modal = document.getElementById("evidence-modal");
document.querySelectorAll(".evidence-open").forEach(button => button.addEventListener("click", () => {
  document.getElementById("modal-title").textContent = button.dataset.modalTitle;
  const image = document.getElementById("modal-image");
  image.src = button.dataset.modalImage;
  image.alt = button.dataset.modalTitle;
  modal.showModal();
}));
document.querySelector("#evidence-modal .modal-close")?.addEventListener("click", () => modal.close());
modal?.addEventListener("click", event => { if (event.target === modal) modal.close(); });

renderPanel();
initMap();
