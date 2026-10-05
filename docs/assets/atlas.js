const DATA = window.ATLAS_DATA;
const state = { scene: "tengeh", layer: "pre", opacity: 0.92 };
let map;

const metricLabels = {
  land_bias_px: "land bias (x, y)", injected_m: "injected motion", recovered_east_m: "recovered east",
  recovered_south_m: "recovered south", ecc: "ECC coefficient", accepted: "quality accepted",
  damage_sector_channels: "damage-sector change", whole_array_translation_channels: "rigid translation",
  pre: "pre-event date", post: "post-event date", dates_screened: "dates screened",
  temporal_pairs: "temporal pairs", maximum_apparent_shift_m: "maximum apparent shift", screen_threshold_m: "screen threshold"
};

const metricUnits = {
  injected_m: " m", recovered_east_m: " m", recovered_south_m: " m",
  maximum_apparent_shift_m: " m", screen_threshold_m: " m"
};

function boundsFromCoordinates(coordinates) {
  const west = Math.min(...coordinates.map(point => point[0]));
  const east = Math.max(...coordinates.map(point => point[0]));
  const south = Math.min(...coordinates.map(point => point[1]));
  const north = Math.max(...coordinates.map(point => point[1]));
  return [[west, south], [east, north]];
}

function removeLayer(id) { if (map.getLayer(id)) map.removeLayer(id); }
function removeSource(id) { if (map.getSource(id)) map.removeSource(id); }

function clearDynamicMap() {
  ["vector-lines", "vector-endpoints", "overlay-control-line", "overlay-control-fill", "overlay-target-line", "overlay-target-fill", "overview-labels", "overview-l", "overview-c", "raster-evidence"].forEach(removeLayer);
  ["vectors", "overlays", "overview", "raster"].forEach(removeSource);
}

function fitScene(sceneKey) {
  const padding = window.innerWidth > 860 ? { left: 440, right: 55, top: 55, bottom: 55 } : 45;
  if (sceneKey === "overview") {
    map.fitBounds([[-15, -7], [119, 52]], { padding, duration: 850 });
    return;
  }
  map.fitBounds(boundsFromCoordinates(DATA.scenes[sceneKey].bounds), { padding, duration: 850, maxZoom: 15.7 });
}

function setRasterLayer(scene, layerId) {
  removeLayer("raster-evidence");
  removeSource("raster");
  const layer = scene.layers.find(item => item.id === layerId) || scene.layers[0];
  state.layer = layer.id;
  map.addSource("raster", { type: "image", url: layer.url, coordinates: scene.bounds });
  map.addLayer({ id: "raster-evidence", type: "raster", source: "raster", paint: { "raster-opacity": state.opacity, "raster-resampling": "linear" } });
  document.getElementById("active-layer-kind").textContent = layer.kind;
  document.getElementById("map-layer-title").textContent = layer.label;
  document.querySelectorAll("#layer-list button").forEach(button => {
    const active = button.dataset.layer === layer.id;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function addOverlayLayers(scene) {
  map.addSource("overlays", { type: "geojson", data: scene.overlays });
  map.addLayer({
    id: "overlay-target-fill", type: "fill", source: "overlays",
    filter: ["in", ["get", "kind"], ["literal", ["target", "footprint"]]],
    paint: { "fill-color": "#f0c95d", "fill-opacity": 0.12 }
  });
  map.addLayer({
    id: "overlay-target-line", type: "line", source: "overlays",
    filter: ["in", ["get", "kind"], ["literal", ["target", "footprint"]]],
    paint: { "line-color": "#f0c95d", "line-width": 2.6 }
  });
  map.addLayer({
    id: "overlay-control-fill", type: "fill", source: "overlays",
    filter: ["==", ["get", "kind"], "control"],
    paint: { "fill-color": "#68b58a", "fill-opacity": 0.08 }
  });
  map.addLayer({
    id: "overlay-control-line", type: "line", source: "overlays",
    filter: ["==", ["get", "kind"], "control"],
    paint: { "line-color": "#68b58a", "line-width": 1.8, "line-dasharray": [2, 2] }
  });
  if (scene.vectors) {
    map.addSource("vectors", { type: "geojson", data: scene.vectors });
    map.addLayer({
      id: "vector-lines", type: "line", source: "vectors",
      paint: { "line-color": ["match", ["get", "kind"], "injected", "#ee554f", "#35d1c6"], "line-width": 5, "line-opacity": 0.95 }
    });
    const endpoints = {
      type: "FeatureCollection",
      features: scene.vectors.features.map(feature => ({
        type: "Feature", properties: feature.properties,
        geometry: { type: "Point", coordinates: feature.geometry.coordinates[feature.geometry.coordinates.length - 1] }
      }))
    };
    map.addSource("vector-endpoints-source", { type: "geojson", data: endpoints });
    map.addLayer({
      id: "vector-endpoints", type: "circle", source: "vector-endpoints-source",
      paint: { "circle-radius": 5, "circle-color": ["match", ["get", "kind"], "injected", "#ee554f", "#35d1c6"], "circle-stroke-color": "#08151d", "circle-stroke-width": 1 }
    });
  }
  applyOverlayVisibility();
}

function clearVectorEndpointSource() {
  removeLayer("vector-endpoints");
  removeSource("vector-endpoints-source");
}

function applyOverlayVisibility() {
  const target = document.getElementById("show-targets").checked ? "visible" : "none";
  const controls = document.getElementById("show-controls").checked ? "visible" : "none";
  const vectors = document.getElementById("show-vectors").checked ? "visible" : "none";
  ["overlay-target-fill", "overlay-target-line"].forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", target); });
  ["overlay-control-fill", "overlay-control-line"].forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", controls); });
  ["vector-lines", "vector-endpoints"].forEach(id => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vectors); });
}

function overviewData() {
  return {
    type: "FeatureCollection",
    features: DATA.overview.sites.features.map(feature => ({
      ...feature,
      properties: {
        ...feature.properties,
        L50: feature.properties.L[0], L80: feature.properties.L[1], L95: feature.properties.L[2],
        C50: feature.properties.C[0], C80: feature.properties.C[1], C95: feature.properties.C[2]
      }
    }))
  };
}

function addOverview() {
  map.addSource("overview", { type: "geojson", data: overviewData() });
  map.addLayer({
    id: "overview-c", type: "circle", source: "overview",
    paint: { "circle-radius": ["interpolate", ["linear"], ["get", "C95"], 20, 8, 40, 15], "circle-color": "#3489bd", "circle-opacity": 0.82, "circle-stroke-color": "#dfe9ed", "circle-stroke-width": 1 }
  });
  map.addLayer({
    id: "overview-l", type: "circle", source: "overview",
    paint: { "circle-radius": ["interpolate", ["linear"], ["get", "L95"], 20, 6, 40, 13], "circle-color": "#ee554f", "circle-opacity": 0.86, "circle-stroke-color": "#08151d", "circle-stroke-width": 1, "circle-translate": [-13, 0] }
  });
  map.addLayer({
    id: "overview-labels", type: "symbol", source: "overview",
    layout: { "text-field": ["get", "site"], "text-size": 13, "text-offset": [0, 1.8], "text-anchor": "top", "text-allow-overlap": true },
    paint: { "text-color": "#eff4f5", "text-halo-color": "#08151d", "text-halo-width": 1.5 }
  });
}

function formatMetric(key, value) {
  if (Array.isArray(value)) return `(${value.join(", ")}) px`;
  if (typeof value === "boolean") return value ? "YES" : "NO";
  return `${value}${metricUnits[key] || ""}`;
}

function renderMetrics(metrics) {
  document.getElementById("metric-readout").innerHTML = Object.entries(metrics).map(([key, value]) =>
    `<div><dt>${metricLabels[key] || key.replaceAll("_", " ")}</dt><dd>${formatMetric(key, value)}</dd></div>`
  ).join("");
}

function renderLayerButtons(scene) {
  const list = document.getElementById("layer-list");
  list.innerHTML = scene.layers.map((layer, index) =>
    `<button type="button" data-layer="${layer.id}" class="${index === 0 ? "active" : ""}" aria-pressed="${index === 0}">${layer.label}</button>`
  ).join("");
  list.querySelectorAll("button").forEach(button => button.addEventListener("click", () => setRasterLayer(scene, button.dataset.layer)));
}

function setScene(sceneKey, shouldFit = true) {
  state.scene = sceneKey;
  document.querySelectorAll("[data-scene]").forEach(button => {
    const active = button.dataset.scene === sceneKey;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  clearVectorEndpointSource();
  clearDynamicMap();

  const layerControls = document.getElementById("layer-controls");
  const opacityControl = document.querySelector(".opacity-control");
  const overlayControls = document.getElementById("overlay-controls");
  const vectorToggle = document.getElementById("vector-toggle");
  const legend = document.getElementById("map-legend");

  if (sceneKey === "overview") {
    document.getElementById("scene-index").textContent = "CHAPTER 04 · GEOGRAPHIC REPLICATION";
    document.getElementById("scene-title").textContent = "Harmonized site comparison";
    document.getElementById("scene-subtitle").textContent = "Co-polarized MD95 at 20 m · circle size encodes the site-specific boundary";
    document.getElementById("scene-interpretation").textContent = "The three sites do not preserve one sensor ordering. Piolenc and Sirindhorn favour the initial L-band point estimates; Tengeh favours C-band at MD95.";
    document.getElementById("provenance-copy").textContent = "Values come from data/derived/site_md_summary.csv. NISAR strata remain underpowered and are displayed as initial site bounds, not a global mission ranking.";
    document.getElementById("map-mode").textContent = "SPATIAL RESULT";
    document.getElementById("map-layer-title").textContent = "Co-pol MD95 by study site";
    renderMetrics({sites: 3, nisar_test_pairs: 15, sentinel1_test_pairs: 270, split_leakage: 0});
    layerControls.hidden = true; opacityControl.hidden = true; overlayControls.hidden = true;
    legend.innerHTML = '<span><i class="legend-injected"></i>NISAR L-band MD95</span><span><i style="background:#3489bd"></i>Sentinel-1 C-band MD95</span>';
    addOverview();
  } else {
    const scene = DATA.scenes[sceneKey];
    const chapters = {
      tengeh: "CHAPTER 01 · CONTROLLED GROUND TRUTH",
      yamakura: "CHAPTER 02 · EVENT LOCALIZATION",
      omkareshwar: "CHAPTER 03 · PRODUCT BOUNDARY"
    };
    document.getElementById("scene-index").textContent = chapters[sceneKey];
    document.getElementById("scene-title").textContent = scene.title;
    document.getElementById("scene-subtitle").textContent = scene.subtitle;
    document.getElementById("scene-interpretation").textContent = scene.interpretation;
    document.getElementById("provenance-copy").textContent = sceneKey === "omkareshwar"
      ? "Source: tracked NISAR Worldview RGB GeoTIFF. This rendered public layer is used only for visibility and ROI auditing; it is not part of the Level-2 GCOV inference benchmark."
      : "Source: tracked GeoTIFFs in qgis/rasters. Display PNGs preserve their EPSG:4326 extents. Processed Tengeh stages call the same frozen functions as src/cross_sensor_inference.py.";
    document.getElementById("map-mode").textContent = "RASTER EVIDENCE";
    renderMetrics(scene.metrics);
    renderLayerButtons(scene);
    layerControls.hidden = false; opacityControl.hidden = false; overlayControls.hidden = false;
    vectorToggle.hidden = !scene.vectors;
    legend.innerHTML = '<span><i class="legend-target"></i>FPV target</span><span><i class="legend-control"></i>stable control</span>' + (scene.vectors ? '<span class="legend-vector"><i class="legend-injected"></i>injected 40 m</span><span class="legend-vector"><i class="legend-recovered"></i>recovered vector</span>' : '');
    state.layer = scene.layers[0].id;
    setRasterLayer(scene, state.layer);
    addOverlayLayers(scene);
  }
  if (shouldFit) fitScene(sceneKey);
  updateExtentReadout();
}

function updateExtentReadout() {
  if (state.scene === "overview") {
    document.getElementById("extent-readout").textContent = "3 geographic validation sites";
    return;
  }
  const bounds = boundsFromCoordinates(DATA.scenes[state.scene].bounds);
  document.getElementById("extent-readout").textContent = `${bounds[0][0].toFixed(4)}, ${bounds[0][1].toFixed(4)} — ${bounds[1][0].toFixed(4)}, ${bounds[1][1].toFixed(4)}`;
}

function popupHTML(properties) {
  if (properties.site) {
    return `<b>${properties.site}</b>L-band MD95: ${properties.L95} m (${properties.L_pairs} pairs)<br>Sentinel-1 MD95: ${properties.C95} m (${properties.C_pairs} pairs)`;
  }
  const name = properties.roi || properties.name || properties.kind || "Evidence region";
  return `<b>${name.replaceAll("_", " ")}</b>${properties.kind || "region"}`;
}

function initMap() {
  map = new maplibregl.Map({
    container: "atlas-map",
    style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    center: [103.643, 1.35], zoom: 13.4, attributionControl: false
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.FullscreenControl(), "top-right");
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 130, unit: "metric" }), "bottom-right");
  map.on("load", () => setScene("tengeh", true));
  map.on("mousemove", event => {
    document.getElementById("cursor-coordinate").textContent = `${event.lngLat.lng.toFixed(6)}° E · ${event.lngLat.lat.toFixed(6)}° N · z${map.getZoom().toFixed(1)}`;
  });
  map.on("click", event => {
    const layers = ["overview-l", "overview-c", "overlay-target-fill", "overlay-control-fill", "vector-lines"].filter(id => map.getLayer(id));
    const features = map.queryRenderedFeatures(event.point, { layers });
    if (!features.length) return;
    new maplibregl.Popup({ closeButton: true, maxWidth: "270px" }).setLngLat(event.lngLat).setHTML(popupHTML(features[0].properties)).addTo(map);
  });
  map.on("mouseenter", () => { map.getCanvas().style.cursor = "crosshair"; });
  map.on("mouseleave", () => { map.getCanvas().style.cursor = ""; });
}

document.querySelectorAll("[data-scene]").forEach(button => button.addEventListener("click", () => setScene(button.dataset.scene, true)));
document.getElementById("raster-opacity").addEventListener("input", event => {
  state.opacity = Number(event.target.value) / 100;
  document.getElementById("opacity-value").textContent = `${event.target.value}%`;
  if (map.getLayer("raster-evidence")) map.setPaintProperty("raster-evidence", "raster-opacity", state.opacity);
});
["show-targets", "show-controls", "show-vectors"].forEach(id => document.getElementById(id).addEventListener("change", applyOverlayVisibility));
document.getElementById("reset-view").addEventListener("click", () => fitScene(state.scene));
document.querySelectorAll("[data-overview-site]").forEach(row => row.addEventListener("click", () => {
  const site = row.dataset.overviewSite;
  if (state.scene !== "overview") setScene("overview", false);
  const feature = DATA.overview.sites.features.find(item => item.properties.site === site);
  map.flyTo({ center: feature.geometry.coordinates, zoom: 5.2, duration: 900 });
}));

initMap();
