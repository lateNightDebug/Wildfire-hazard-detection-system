/* Shared console helpers: top nav, fetch wrapper, formatting, severity map. */

const SEV = {
  high:   { label: "High",   color: "#E05555" },
  medium: { label: "Medium", color: "#F0A500" },
  low:    { label: "Low",    color: "#3A9A3A" },
};

const REVIEW_URL_FALLBACK = "http://127.0.0.1:7860";

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* keep statusText */ }
    throw new Error(msg);
  }
  return res.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function sevBadge(sev) {
  if (!sev) return '<span class="badge none">&mdash;</span>';
  return `<span class="badge ${sev}">${SEV[sev].label}</span>`;
}

function countsLine(counts) {
  const parts = Object.entries(counts || {}).map(([k, v]) => `${v} ${esc(k)}`);
  return parts.length ? parts.join(" · ") : "no detections";
}

function toast(msg, ms = 5000) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

/* Top navigation, shared by all pages. `active`: dashboard | scans | review | map */
function renderNav(active) {
  const tab = (id, label, href) => {
    const cls = "nav-tab" + (active === id ? " active" : "");
    return `<a class="${cls}" href="${href}">${label}</a>`;
  };
  const soon = label =>
    `<div class="nav-tab soon">${label}<span class="soon-pill">SOON</span></div>`;
  document.getElementById("topnav").innerHTML = `
    <div class="brand">
      <div class="brand-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2c1.5 3.5-1.5 5-1.5 7.5 0 1 .6 1.8 1.5 1.8s1.5-.8 1.5-1.8c0-.7-.2-1.3-.4-1.8 1.7 1.1 3.4 3 3.4 5.8a4.5 4.5 0 1 1-9 0C7 13 9.5 11 9.5 8.5c0-2 1-4.5 2.5-6.5z" fill="#fff"></path></svg>
      </div>
      <div style="display:flex; flex-direction:column; line-height:1.15;">
        <span class="brand-name">Wildfire Hazard Detection System</span>
        <span class="brand-sub">Operations Console · Offline</span>
      </div>
    </div>
    <div class="nav-tabs">
      ${tab("dashboard", "Dashboard", "/")}
      ${tab("scans", "Scans", "/scans")}
      ${tab("review", "Review", "/review")}
      ${tab("map", "Map", "/map")}
      ${tab("reports", "Reports", "/reports")}
      ${soon("Alerts")}
      ${tab("settings", "Settings", "/settings")}
    </div>
    <div class="nav-right">
      <div class="live"><span class="live-dot"></span><span class="mono">Local</span></div>
      <div class="user-chip">
        <div style="display:flex; flex-direction:column; align-items:flex-end; line-height:1.2;">
          <span class="name">Operator</span><span class="role">FIELD OPS</span>
        </div>
        <div class="avatar">OP</div>
      </div>
    </div>`;
}

/* Stylized terrain backdrop for the hazard map (from the design mockup).
   It is a decorative canvas — pins are placed by real GPS, normalized to the
   bounding box of all scan coordinates. */
function terrainSvg(idPrefix) {
  const p = idPrefix;
  return `
  <svg style="position:absolute; inset:0; width:100%; height:100%;" viewBox="0 0 800 500" preserveAspectRatio="xMidYMid slice">
    <defs>
      <filter id="${p}-terr" x="0" y="0" width="100%" height="100%">
        <feTurbulence type="fractalNoise" baseFrequency="0.009 0.014" numOctaves="5" seed="11" stitchTiles="stitch" result="n"></feTurbulence>
        <feComponentTransfer in="n">
          <feFuncR type="table" tableValues="0.05 0.10 0.17 0.27 0.40 0.48"></feFuncR>
          <feFuncG type="table" tableValues="0.11 0.19 0.26 0.32 0.37 0.41"></feFuncG>
          <feFuncB type="table" tableValues="0.05 0.08 0.11 0.13 0.17 0.19"></feFuncB>
          <feFuncA type="table" tableValues="1 1"></feFuncA>
        </feComponentTransfer>
      </filter>
      <filter id="${p}-veg" x="0" y="0" width="100%" height="100%">
        <feTurbulence type="fractalNoise" baseFrequency="0.045 0.055" numOctaves="3" seed="4" result="vn"></feTurbulence>
        <feColorMatrix in="vn" type="matrix" values="0 0 0 0 0.07 0 0 0 0 0.19 0 0 0 0 0.06 0 0 0 1.1 -0.45"></feColorMatrix>
      </filter>
      <radialGradient id="${p}-vig" cx="50%" cy="44%" r="72%">
        <stop offset="52%" stop-color="#000" stop-opacity="0"></stop>
        <stop offset="100%" stop-color="#0a0d09" stop-opacity="0.6"></stop>
      </radialGradient>
    </defs>
    <rect width="800" height="500" fill="#18220f"></rect>
    <rect width="800" height="500" filter="url(#${p}-terr)"></rect>
    <rect width="800" height="500" filter="url(#${p}-veg)" opacity="0.55"></rect>
    <path d="M90 -20 C 150 70, 90 150, 200 230 C 290 296, 360 340, 470 520" stroke="#1f3d4a" stroke-width="9" fill="none" stroke-linecap="round" opacity="0.85"></path>
    <path d="M90 -20 C 150 70, 90 150, 200 230 C 290 296, 360 340, 470 520" stroke="#356a7e" stroke-width="3" fill="none" stroke-linecap="round" opacity="0.7"></path>
    <path d="M-20 372 C 150 340, 330 360, 486 304 C 620 256, 740 244, 820 262" stroke="#0d0f0a" stroke-width="5.5" fill="none" opacity="0.5"></path>
    <path d="M-20 372 C 150 340, 330 360, 486 304 C 620 256, 740 244, 820 262" stroke="#d9cda6" stroke-width="2.4" fill="none" opacity="0.65"></path>
    <rect width="800" height="500" fill="url(#${p}-vig)"></rect>
  </svg>`;
}

/* GPS list -> percentage positions inside the map box (padded bounding box). */
function gpsToPercent(pins) {
  const pts = pins.filter(p => p.lat != null && p.lon != null);
  if (!pts.length) return [];
  let minLat = Math.min(...pts.map(p => p.lat)), maxLat = Math.max(...pts.map(p => p.lat));
  let minLon = Math.min(...pts.map(p => p.lon)), maxLon = Math.max(...pts.map(p => p.lon));
  const latSpan = Math.max(maxLat - minLat, 1e-4), lonSpan = Math.max(maxLon - minLon, 1e-4);
  const PAD = 14; // % padding so edge pins stay inside
  return pts.map(p => ({
    ...p,
    x: PAD + ((p.lon - minLon) / lonSpan) * (100 - 2 * PAD),
    y: PAD + ((maxLat - p.lat) / latSpan) * (100 - 2 * PAD), // north = up
  }));
}

function fmtCoord(lat, lon) {
  if (lat == null) return "no GPS";
  const ns = lat >= 0 ? "N" : "S", ew = lon >= 0 ? "E" : "W";
  return `${Math.abs(lat).toFixed(3)}°${ns}, ${Math.abs(lon).toFixed(3)}°${ew}`;
}
