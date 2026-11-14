// Maps page: line-of-sight layers per map (tools/maplos.py -> site/maps/<map>/).
// Canvas with base terrain + one overlay, zone/spawn/top-spot markers, wheel zoom and drag pan.
(() => {
const TA = window.TA;
if (!TA) return;
// live: maps seen in real matches (match travel in our logs); the rest ship in the files but never came up
const MAPS = [['fields', 'Fields', 1], ['divide', 'Divide', 1], ['ravine', 'Ravine', 1], ['scorch', 'Scorch', 1], ['windvalley', 'Wind Valley', 1],
  ['core', 'Core', 1], ['dunes', 'Dunes', 0], ['ruins', 'Ruins', 0], ['glade', 'Glade', 0]];
const LAYERS = [['advantage', 'Spots more than it is spotted'], ['sees', 'Ground it can spot'], ['seen', 'How often it is spotted'], ['zone', 'Who spots a capture zone'], ['none', 'Terrain only']];
const CAMOS = [[0, 'Camo 0% (most heavies)'], [1, 'Camo 25% (mediums)'], [2, 'Camo 40% (scouts)']];
let camo = 1;
const ZCOL = { CaptureZone: '#f2c200', HealZone: '#22c55e', AmmunitionZone: '#38bdf8', AbilityResourceZone: '#a78bfa' };
const ZNAME = { CaptureZone: 'Capture zone', HealZone: 'Heal zone', AmmunitionZone: 'Ammo zone', AbilityResourceZone: 'Energy zone' };
let cur = 'fields', layer = 'advantage', zoneIdx = 0, view = { s: 1, x: 0, y: 0 };
const cache = {};
const $ = id => document.getElementById(id);

function load(name) {
  if (cache[name]) return cache[name];
  const p = fetch(`maps/${name}/meta.json`).then(r => r.ok ? r.json() : null).then(meta => {
    if (!meta) return null;
    const img = src => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = `maps/${name}/${src}`; });
    const files = { base: 'base.jpg' };
    for (let c = 0; c < meta.camos.length; c++) {
      for (const l of ['sees', 'seen', 'advantage']) files[`${l}_${c}`] = `${l}_${c}.png`;
      meta.zone_layers.forEach(k => { files[`zone${k}_${c}`] = `zone${k}_${c}.png`; });
    }
    return Promise.all(Object.entries(files).map(([k, f]) => img(f).then(i => [k, i]))).then(list => ({ meta, img: Object.fromEntries(list) }));
  });
  cache[name] = p; return p;
}

function controls() {
  const ms = $('map-pick'); if (!ms || ms.childElementCount) return;
  const groups = [['In rotation', 1], ['In the files, not seen in matches', 0]];
  for (const [gl, live] of groups) { const og = document.createElement('optgroup'); og.label = gl;
    for (const [k, l, lv] of MAPS) if (lv === live) { const o = document.createElement('option'); o.value = k; o.textContent = l; og.append(o); }
    ms.append(og); }
  ms.value = cur; ms.onchange = () => { cur = ms.value; zoneIdx = 0; view = { s: 1, x: 0, y: 0 }; draw(); };
  const seg = $('map-layer');
  for (const [k, l] of LAYERS) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = l; b.setAttribute('aria-pressed', String(k === layer));
    b.onclick = () => { layer = k; for (const x of seg.children) x.setAttribute('aria-pressed', String(x === b)); draw(); };
    seg.append(b);
  }
  const cs = $('map-camo');
  if (cs) for (const [k, l] of CAMOS) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = l; b.setAttribute('aria-pressed', String(k === camo));
    b.onclick = () => { camo = k; for (const x of cs.children) x.setAttribute('aria-pressed', String(x === b)); legend(); paint(); };
    cs.append(b);
  }
  const cv = $('map-canvas');
  cv.addEventListener('wheel', ev => {
    ev.preventDefault();
    const r = cv.getBoundingClientRect(), mx = (ev.clientX - r.left) / r.width, my = (ev.clientY - r.top) / r.height;
    const ns = Math.min(8, Math.max(1, view.s * (ev.deltaY < 0 ? 1.2 : 1 / 1.2)));
    view.x = mx - (mx - view.x) * ns / view.s; view.y = my - (my - view.y) * ns / view.s; view.s = ns; clamp(); paint();
  }, { passive: false });
  let drag = null;
  cv.addEventListener('pointerdown', ev => { drag = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y }; cv.setPointerCapture(ev.pointerId); });
  cv.addEventListener('pointerup', () => { drag = null; });
  cv.addEventListener('pointermove', ev => {
    const r = cv.getBoundingClientRect();
    if (drag) { view.x = drag.vx + (ev.clientX - drag.x) / r.width; view.y = drag.vy + (ev.clientY - drag.y) / r.height; clamp(); paint(); return; }
    hover(ev, r);
  });
  cv.addEventListener('pointerleave', TA.hideTip);
  $('map-reset') && ($('map-reset').onclick = () => { view = { s: 1, x: 0, y: 0 }; paint(); });
}
function clamp() { view.x = Math.min(0, Math.max(1 - view.s, view.x)); view.y = Math.min(0, Math.max(1 - view.s, view.y)); }

let data = null;
function draw() {
  controls();
  load(cur).then(d => { data = d; if (!d) { $('map-note').textContent = 'No line-of-sight data for this map yet.'; return; } legend(); paint(); });
}

// map pixel (meta px) -> canvas px
const toC = (cv, p) => [(view.x + p[0] / data.meta.size[0] * view.s) * cv.width, (view.y + p[1] / data.meta.size[1] * view.s) * cv.height];

function paint() {
  const cv = $('map-canvas'); if (!cv || !data) return;
  const { meta, img } = data, w = Math.min(TA.width('map-wrap'), 1100);
  const ratio = meta.size[1] / meta.size[0], dpr = window.devicePixelRatio || 1;
  cv.style.width = `${w}px`; cv.style.height = `${w * ratio}px`; cv.width = Math.round(w * dpr); cv.height = Math.round(w * ratio * dpr);
  const ctx = cv.getContext('2d'); ctx.imageSmoothingEnabled = view.s < 2;
  const dx = view.x * cv.width, dy = view.y * cv.height, dw = cv.width * view.s, dh = cv.height * view.s;
  if (img.base) ctx.drawImage(img.base, dx, dy, dw, dh);
  const ov = layer === 'zone' ? img[`zone${meta.zone_layers[zoneIdx] ?? -1}_${camo}`] : layer !== 'none' ? img[`${layer}_${camo}`] : null;
  if (ov) ctx.drawImage(ov, dx, dy, dw, dh);
  const R = 7 * dpr;
  meta.zones.forEach((z, i) => {
    const [x, y] = toC(cv, z.px); ctx.lineWidth = 3 * dpr; ctx.strokeStyle = ZCOL[z.kind] || '#fff';
    ctx.beginPath(); ctx.arc(x, y, z.kind === 'CaptureZone' ? R * 1.8 : R, 0, 7); ctx.stroke();
    if (layer === 'zone' && meta.zone_layers[zoneIdx] === i) { ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = '#fff'; ctx.beginPath(); ctx.arc(x, y, R * 2.6, 0, 7); ctx.stroke(); }
  });
  ctx.fillStyle = '#fff';
  for (const s of meta.spawns) { const [x, y] = toC(cv, s); ctx.fillRect(x - 2 * dpr, y - 2 * dpr, 4 * dpr, 4 * dpr); }
  if (layer === 'advantage' || layer === 'sees') spotList().filter(({ s }) => layer === 'sees' ? s.kind === 'open' : true).forEach(({ s, label }) => {
    const [x, y] = toC(cv, s.px);
    ctx.fillStyle = s.kind === 'bush' ? '#166534' : '#0b0b0b'; ctx.beginPath(); ctx.arc(x, y, 9 * dpr, 0, 7); ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5 * dpr; ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = `600 ${10 * dpr}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(label, x, y + 0.5 * dpr);
  });
  // scale bar: 100 m
  const px100 = 100 / meta.m_per_px / meta.size[0] * cv.width * view.s;
  ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(10 * dpr, cv.height - 26 * dpr, px100 + 16 * dpr, 18 * dpr);
  ctx.fillStyle = '#fff'; ctx.fillRect(18 * dpr, cv.height - 15 * dpr, px100, 3 * dpr);
  ctx.font = `${10 * dpr}px system-ui, sans-serif`; ctx.textAlign = 'left'; ctx.fillText('100 m', 18 * dpr, cv.height - 20 * dpr);
  const mm = MAPS.find(m => m[0] === cur);
  $('map-note').textContent = `${mm[1]}${mm[2] ? '' : ' (not seen in real matches)'} · ${meta.playable_km2.toFixed(2)} km² playable · scroll to zoom, drag to pan`;
}

function spotList() {
  let o = 0, b = 0;
  return (data.meta.spots[String(camo)] || []).map(s => ({ s, label: s.kind === 'bush' ? `B${++b}` : `O${++o}` }));
}
function hover(ev, r) {
  if (!data) return;
  const cv = $('map-canvas'), dpr = window.devicePixelRatio || 1;
  const mx = (ev.clientX - r.left) * dpr * cv.width / (r.width * dpr), my = (ev.clientY - r.top) * dpr * cv.height / (r.height * dpr);
  const near = (p, rad) => { const [x, y] = toC(cv, p); return Math.hypot(x - mx, y - my) < rad * dpr; };
  if (layer === 'advantage' || layer === 'sees') { const hit = spotList().find(({ s }) => near(s.px, 11)); if (hit) { const { s, label } = hit;
    TA.showTip(ev, [s.kind === 'bush' ? `spots ${s.ratio}× more than it is spotted` : `spots ${(s.sees_m2 / 1e4).toFixed(1)} ha of ground`,
      `${s.kind === 'bush' ? 'Behind-bush spot' : 'Overlook'} ${label}: spots ${(s.sees_m2 / 1e4).toFixed(1)} ha, spotted from ${(s.seen_m2 / 1e4).toFixed(1)} ha`,
      `${s.height_m >= 0 ? '+' : ''}${s.height_m} m against the map's median ground`]); return; } }
  const z = data.meta.zones.find(z => near(z.px, z.kind === 'CaptureZone' ? 14 : 9));
  if (z) { TA.showTip(ev, [ZNAME[z.kind] || z.kind, 'Pick a capture zone above the map when the coverage layer is on']); return; }
  TA.hideTip();
}

function legend() {
  const lg = $('map-legend'); if (!lg) return; lg.replaceChildren();
  const add = (col, label, ring) => { const s = document.createElement('span'); const k = document.createElement('i'); k.className = 'key';
    if (ring) { k.style.background = 'transparent'; k.style.border = `2px solid ${col}`; } else k.style.background = col; s.append(k, label); lg.append(s); };
  if (layer === 'advantage') { add('#3d99d6', 'sees more than it is seen'); add('#9e9e9e', 'even'); add('#d14d40', 'seen more than it sees'); add('#166534', 'best behind-bush spots (B1, B2...)'); add('#0b0b0b', 'best overlooks (O1, O2...)'); }
  else if (layer === 'sees' || layer === 'seen') { add('#cde2fb', 'little'); add('#0d366b', 'a lot'); }
  else if (layer === 'zone') add('#f2c200', 'can see the selected capture zone');
  for (const [k, c] of Object.entries(ZCOL)) add(c, ZNAME[k], true);
  add('#ffffff', 'spawn');
  const zs = $('map-zone'); if (!zs) return; zs.replaceChildren(); zs.hidden = layer !== 'zone';
  data.meta.zone_layers.forEach((k, i) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = `Capture zone ${i + 1}`;
    b.setAttribute('aria-pressed', String(i === zoneIdx)); b.onclick = () => { zoneIdx = i; legend(); paint(); }; zs.append(b); });
}

if (TA.chart) { TA.chart('maps', draw); TA.redraw && TA.redraw(); } else TA.onDraw.push(draw);
})();
