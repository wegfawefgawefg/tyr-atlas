// Maps page: line-of-sight layers per map (tools/maplos.py -> site/maps/<map>/).
// Canvas with base terrain + one overlay, zone/spawn/top-spot markers, wheel or pinch or button zoom, drag pan.
// Touch: at full view one finger scrolls the page (touch-action pan-y); once zoomed in, one finger pans the map.
(() => {
const TA = window.TA;
if (!TA) return;
// live: maps seen in real matches (match travel in our logs); the rest ship in the files but never came up
const MAPS = [['fields', 'Fields', 1], ['divide', 'Divide', 1], ['ravine', 'Ravine', 1], ['scorch', 'Scorch', 1], ['windvalley', 'Wind Valley', 1],
  ['core', 'Core', 1], ['dunes', 'Dunes', 0], ['ruins', 'Ruins', 0], ['glade', 'Glade', 0]];
const LAYERS = [['advantage', 'Spots more than it is spotted'], ['sees', 'Ground it can spot'], ['seen', 'How often it is spotted'], ['zone', 'Who spots a capture zone'], ['none', 'Terrain only']];
const LEVELS = [0, 10, 20, 30, 40, 50, 60, 70, 80];       // camo levels the sweep was run at (meta.camos)
let camo = 3;                                               // index into LEVELS
// camo rules from BP_TyrGameMode: cap 80; firing applies GunFireCamoAddition -15 and GunFireCamoScalar -0.4
const capC = c => Math.max(0, Math.min(80, c));
const fired = c => capC(c + (-15 + -0.4 * c));
const nearest = c => LEVELS.reduce((b, v, i) => Math.abs(v - c) < Math.abs(LEVELS[b] - c) ? i : b, 0);
const ZCOL = { CaptureZone: '#f2c200', HealZone: '#22c55e', AmmunitionZone: '#38bdf8', AbilityResourceZone: '#a78bfa' };
const ZNAME = { CaptureZone: 'Capture zone', HealZone: 'Heal zone', AmmunitionZone: 'Ammo zone', AbilityResourceZone: 'Energy zone' };
let cur = 'fields', layer = 'advantage', zoneIdx = 0, view = { s: 1, x: 0, y: 0 }, names = true;
const cache = {};
const $ = id => document.getElementById(id);

function load(name) {
  if (cache[name]) return cache[name];
  const p = fetch(`maps/${name}/meta.json`).then(r => r.ok ? r.json() : null).then(meta => {
    if (!meta) return null;
    const img = src => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = `maps/${name}/${src}`; });
    const files = { base: 'base.jpg', regions: 'regions.png' };
    for (let c = 0; c < meta.camos.length; c++) {
      for (const l of ['sees', 'seen', 'advantage']) files[`${l}_${c}`] = `${l}_${c}.png`;
      meta.zone_layers.forEach(k => { files[`zone${k}_${c}`] = `zone${k}_${c}.png`; });
    }
    const calls = fetch(`maps/${name}/callouts.json`).then(r => r.ok ? r.json() : { callouts: [] }).catch(() => ({ callouts: [] }));
    return Promise.all([calls, ...Object.entries(files).map(([k, f]) => img(f).then(i => [k, i]))])
      .then(([c, ...list]) => ({ meta, callouts: c.callouts, img: Object.fromEntries(list) }));
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
  if (cs) LEVELS.forEach((v, k) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = `${v}%`; b.setAttribute('aria-pressed', String(k === camo));
    b.onclick = () => setCamo(k); cs.append(b);
  });
  const cv = $('map-canvas');
  // zoom by factor f around a point given as a fraction of the canvas (mx, my)
  const zoomAt = (f, mx = 0.5, my = 0.5) => {
    const ns = Math.min(8, Math.max(1, view.s * f));
    view.x = mx - (mx - view.x) * ns / view.s; view.y = my - (my - view.y) * ns / view.s; view.s = ns; clamp(); paint();
  };
  cv.addEventListener('wheel', ev => {
    ev.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(ev.deltaY < 0 ? 1.2 : 1 / 1.2, (ev.clientX - r.left) / r.width, (ev.clientY - r.top) / r.height);
  }, { passive: false });
  const ptrs = new Map();   // active pointers: one pans, two pinch
  let drag = null, pinch = null;
  const startDrag = p => { drag = { x: p.x, y: p.y, vx: view.x, vy: view.y, moved: false }; };
  const pinchState = () => { const [a, b] = [...ptrs.values()]; return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 }; };
  cv.addEventListener('pointerdown', ev => {
    ptrs.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    try { cv.setPointerCapture(ev.pointerId); } catch {}
    if (ptrs.size === 2) { drag = null; pinch = { ...pinchState(), s: view.s, vx: view.x, vy: view.y }; TA.hideTip(true); }
    else if (ptrs.size === 1) startDrag(ptrs.get(ev.pointerId));
  });
  const up = ev => {
    ptrs.delete(ev.pointerId);
    if (ptrs.size < 2) pinch = null;
    if (ptrs.size === 1) startDrag([...ptrs.values()][0]); else if (!ptrs.size) drag = null;
  };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('pointermove', ev => {
    const r = cv.getBoundingClientRect();
    if (ptrs.has(ev.pointerId)) ptrs.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
    if (pinch && ptrs.size === 2) {
      const p = pinchState(), ns = Math.min(8, Math.max(1, pinch.s * p.d / pinch.d));
      const mx0 = (pinch.cx - r.left) / r.width, my0 = (pinch.cy - r.top) / r.height, mx = (p.cx - r.left) / r.width, my = (p.cy - r.top) / r.height;
      view.x = mx - (mx0 - pinch.vx) * ns / pinch.s; view.y = my - (my0 - pinch.vy) * ns / pinch.s; view.s = ns; clamp(); paint(); return;
    }
    if (drag && ptrs.has(ev.pointerId)) {
      if (!drag.moved && Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y) < 4) return;
      if (!drag.moved) { drag.moved = true; TA.hideTip(true); }
      view.x = drag.vx + (ev.clientX - drag.x) / r.width; view.y = drag.vy + (ev.clientY - drag.y) / r.height; clamp(); paint(); return;
    }
    hover(ev, r);
  });
  cv.addEventListener('pointerleave', TA.hideTip);
  $('map-zin').onclick = () => zoomAt(1.5);
  $('map-zout').onclick = () => zoomAt(1 / 1.5);
  $('map-reset').onclick = () => { view = { s: 1, x: 0, y: 0 }; paint(); };
  $('map-names') && ($('map-names').onclick = ev => { names = !names; ev.currentTarget.setAttribute('aria-pressed', String(names)); paint(); });
}
function setCamo(k) {
  camo = k;
  const cs = $('map-camo'); if (cs) [...cs.children].forEach((x, i) => x.setAttribute('aria-pressed', String(i === k)));
  if (data) { legend(); paint(); }
}
// selected tank: its camo before and after talents/components and after firing, as clickable chips
function tankCamo() {
  const host = $('map-tank'); if (!host) return; host.replaceChildren();
  const t = TA.tanks.find(x => x.id === TA.selected);
  if (!t) { const p = document.createElement('span'); p.className = 'note'; p.textContent = 'Pick a tank in the header to see its camo here.'; host.append(p); return; }
  const base = t.base.CamoPercentage, tal = t.ceiling.CamoPercentage;
  const comp = capC((tal + 6) * 1.25);
  const rows = [[`${t.name} base`, capC(base)], ['with camo talents', capC(tal)], ['+ Shift Cloak, Camo Web, standing still', comp],
    ['after firing (base)', fired(base)], ['after firing (best build)', fired(comp)]];
  const lab = document.createElement('span'); lab.className = 'note'; lab.textContent = `${t.name}'s camo:`; host.append(lab);
  for (const [l, v] of rows) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = `${l} ${Math.round(v)}%`;
    b.onclick = () => setCamo(nearest(v)); host.append(b);
  }
}
function clamp() { view.x = Math.min(0, Math.max(1 - view.s, view.x)); view.y = Math.min(0, Math.max(1 - view.s, view.y)); }

let data = null;
let lastTank = null;
function draw() {
  controls();
  tankCamo();
  if (TA.selected !== lastTank) { lastTank = TA.selected; const t = TA.tanks.find(x => x.id === TA.selected); if (t) camo = nearest(capC(t.base.CamoPercentage)), setCamo(camo); }
  load(cur).then(d => { data = d; if (!d) { $('map-note').textContent = 'No line-of-sight data for this map yet.'; return; } legend(); paint(); });
}

// map pixel (meta px) -> canvas px
const toC = (cv, p) => [(view.x + p[0] / data.meta.size[0] * view.s) * cv.width, (view.y + p[1] / data.meta.size[1] * view.s) * cv.height];

function paint() {
  const cv = $('map-canvas'); if (!cv || !data) return;
  const { meta, img } = data, w = Math.min($('map-wrap').clientWidth || 320, 1100);
  cv.style.touchAction = view.s > 1 ? 'none' : 'pan-y';   // full view: one finger scrolls the page; zoomed: it pans the map
  const ratio = meta.size[1] / meta.size[0], dpr = window.devicePixelRatio || 1;
  cv.style.width = `${w}px`; cv.style.height = `${w * ratio}px`; cv.width = Math.round(w * dpr); cv.height = Math.round(w * ratio * dpr);
  const ctx = cv.getContext('2d'); ctx.imageSmoothingEnabled = view.s < 2;
  const dx = view.x * cv.width, dy = view.y * cv.height, dw = cv.width * view.s, dh = cv.height * view.s;
  if (img.base) ctx.drawImage(img.base, dx, dy, dw, dh);
  const ov = layer === 'zone' ? img[`zone${meta.zone_layers[zoneIdx] ?? -1}_${camo}`] : layer !== 'none' ? img[`${layer}_${camo}`] : null;
  if (ov) ctx.drawImage(ov, dx, dy, dw, dh);
  if (names && img.regions) { ctx.globalAlpha = 0.55; ctx.imageSmoothingEnabled = false; ctx.drawImage(img.regions, dx, dy, dw, dh); ctx.globalAlpha = 1; ctx.imageSmoothingEnabled = view.s < 2; }
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
  if (names) {
    ctx.font = `700 ${Math.round(11 * dpr * Math.min(1.6, Math.sqrt(view.s)))}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round'; ctx.lineWidth = 3 * dpr; ctx.strokeStyle = 'rgba(0,0,0,.85)'; ctx.fillStyle = '#fff';
    for (const c of data.callouts) { const [x, y] = toC(cv, c.px); ctx.strokeText(c.name, x, y); ctx.fillText(c.name, x, y); }
  }
  // scale bar: 100 m
  const px100 = 100 / meta.m_per_px / meta.size[0] * cv.width * view.s;
  ctx.fillStyle = 'rgba(0,0,0,.55)'; ctx.fillRect(10 * dpr, cv.height - 26 * dpr, px100 + 16 * dpr, 18 * dpr);
  ctx.fillStyle = '#fff'; ctx.fillRect(18 * dpr, cv.height - 15 * dpr, px100, 3 * dpr);
  ctx.font = `${10 * dpr}px system-ui, sans-serif`; ctx.textAlign = 'left'; ctx.fillText('100 m', 18 * dpr, cv.height - 20 * dpr);
  const mm = MAPS.find(m => m[0] === cur);
  $('map-note').textContent = `${mm[1]}${mm[2] ? '' : ' (not seen in real matches)'} · ${meta.playable_km2.toFixed(2)} km² playable${meta.boundary === 'map' ? '' : ' (estimated boundary)'} · showing ${LEVELS[camo]}% camo · ${matchMedia('(pointer: coarse)').matches ? 'pinch or use + and − to zoom, then drag to pan' : 'scroll or use + and − to zoom, drag to pan'}`;
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
  const c = names && data.callouts.find(c => near(c.px, 28));
  if (c) { TA.showTip(ev, [c.name, c.why, `${(c.area_m2 / 1e4).toFixed(1)} ha${c.side && c.side !== 'mid' ? `, ${c.side} side` : ''}`]); return; }
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
