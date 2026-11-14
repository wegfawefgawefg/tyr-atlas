// Armor charts: roses, hemisphere map, x-ray views, frontal duel matrix.
// Data: window.TYR_ARMOR (tools/site_data.py from tools/armor.py), window.TYR.duel.
(() => {
const TA = window.TA, AR = window.TYR_ARMOR, T = window.TYR;
if (!TA || !AR) return;
const { el, txt, tanks, sortedTanks, showTip, hideTip, width } = TA;
const AUTO = 80, FIFTY = 1.25, OVER = 4;
let pen = 70, duelMode = 'front';
const anyA = AR[tanks[0].name];
const pens = anyA.pen;

// controls
// the armor page and the tank page each have a penetration picker; they share one value
const penSels = ['arm-pen', 't-pen'].map(id => document.getElementById(id)).filter(Boolean);
for (const penSel of penSels) {
  for (const p of pens) { const o = document.createElement('option'); o.value = p; o.textContent = `${p} mm`; penSel.append(o); }
  for (const t of sortedTanks) { const o = document.createElement('option'); o.value = `t:${t.name}`; o.textContent = `${t.name}'s gun (${t.base.ShellPenetration} mm)`; penSel.append(o); }
  penSel.value = '70';
  penSel.onchange = () => {
    const v = penSel.value; pen = v.startsWith('t:') ? tanks.find(t => t.name === v.slice(2)).base.ShellPenetration : +v;
    for (const o of penSels) o.value = v;
    TA.redraw();
  };
}
const dm = document.getElementById('duel-mode');
for (const [k, l] of [['front', 'Face on'], ['angled', 'Both angled 30°']]) {
  const b = document.createElement('button'); b.textContent = l; b.setAttribute('aria-pressed', String(k === duelMode));
  b.onclick = () => { duelMode = k; for (const x of dm.children) x.setAttribute('aria-pressed', String(x === b)); drawDuel(); };
  dm.append(b);
}
const pick = () => tanks.find(t => t.id === TA.selected) || sortedTanks.find(t => t.cls === 'Heavy') || tanks[0];
const pi = () => pens.indexOf(pen);
const el0 = a => a.el.indexOf(0);
const noDmg = (a, ei, ai) => 1 - a.dchance[ei][ai][pi()];
const pct = x => `${Math.round(x * 100)}%`;

// sequential colour for 0..1 using the page ramp
const seq = ['--seq-0', '--seq-1', '--seq-2', '--seq-3', '--seq-4', '--seq-5', '--seq-6', '--seq-7'];
const seqVar = x => `var(${seq[Math.max(0, Math.min(7, Math.floor(x * 8)))]})`;

// 1. roses
function drawRoses() {
  const host = document.getElementById('roses'); host.replaceChildren();
  const W = width('roses'), cols = W < 520 ? 3 : W < 820 ? 4 : 6, cw = W / cols, R = Math.min(cw, 150) / 2 - 16, ch = R * 2 + 40;
  const order = [...tanks].sort((a, b) => {
    const A = AR[a.name], B = AR[b.name];
    const m = x => x.dchance[el0(x)].reduce((s, r) => s + 1 - r[pi()], 0) / x.az.length;
    return m(B) - m(A);
  });
  const rows = Math.ceil(order.length / cols);
  const svg = el('svg', { viewBox: `0 0 ${W} ${rows * ch}`, role: 'img', 'aria-label': 'Armor rose per tank' }, host);
  order.forEach((t, i) => rose(svg, t, (i % cols) * cw + cw / 2, Math.floor(i / cols) * ch + R + 22, R));
  txt(svg, 0, rows * ch - 4, 'Front is up, the tank\'s left side is left. Outer ring = 100% of hits do no damage.', { fill: 'var(--muted)', 'font-size': 11 });
}
// one tank's rose centred at cx, cy with radius R
function rose(svg, t, cx, cy, R, selectable = true) {
  const a = AR[t.name], e = el0(a);
  for (const r of [0.5, 1]) el('circle', { cx, cy, r: R * r, fill: 'none', stroke: 'var(--grid)' }, svg);
  el('line', { x1: cx, x2: cx, y1: cy - R, y2: cy + R, stroke: 'var(--grid)' }, svg);
  el('line', { x1: cx - R, x2: cx + R, y1: cy, y2: cy, stroke: 'var(--grid)' }, svg);
  const pts = a.az.map((az, ai) => { const v = noDmg(a, e, ai), th = az * Math.PI / 180; return [cx - Math.sin(th) * R * v, cy - Math.cos(th) * R * v]; });
  const d = pts.map((p, k) => (k ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ') + 'Z';
  el('path', { d, fill: `var(${TA.CLS[t.cls]})`, 'fill-opacity': 0.18, stroke: `var(${TA.CLS[t.cls]})`, 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
  const lab = txt(svg, cx, cy - R - 8, t.name, { 'text-anchor': 'middle', fill: TA.selected === t.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': TA.selected === t.id ? 600 : 400, 'font-size': 12 });
  const hit = el('circle', { cx, cy, r: R + 6, fill: 'transparent' }, svg);
  if (selectable) { hit.style.cursor = 'pointer'; hit.addEventListener('click', () => TA.select(TA.selected === t.id ? null : t.id)); }
  hit.addEventListener('pointermove', ev => {
    const ang = (Math.atan2(-(ev.offsetX - cx), -(ev.offsetY - cy)) * 180 / Math.PI + 360) % 360;
    const ai = Math.round(ang / 5) % a.az.length;
    showTip(ev, [pct(noDmg(a, e, ai)), `${t.name}, shot from ${a.az[ai]}° (${sideName(a.az[ai])})`, `no-damage chance vs ${pen} mm, level shots`]);
  });
  hit.addEventListener('pointerleave', hideTip);
}
// the tank page's single rose
function drawRose(hostId) {
  const host = document.getElementById(hostId); host.replaceChildren();
  const t = pick(), R = 96, W = 2 * R + 40;
  const svg = el('svg', { viewBox: `0 0 ${W} ${2 * R + 52}`, role: 'img', 'aria-label': `Armor rose for ${t.name}` }, host);
  svg.style.width = `${W}px`; svg.style.maxWidth = '100%';   // 1:1 scale so the hover angle maths holds
  rose(svg, t, W / 2, R + 24, R, false);
  txt(svg, W / 2, 2 * R + 48, 'Outer ring = 100% no damage', { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 11 });
}
const sideName = az => az <= 22 || az >= 338 ? 'front' : az < 68 ? 'front-left' : az <= 112 ? 'left' : az < 158 ? 'rear-left' : az <= 202 ? 'rear' : az < 248 ? 'rear-right' : az <= 292 ? 'right' : 'front-right';

// 2. hemisphere map for the picked tank
function drawHemi(hostId = 'hemi', titleId = 'hemi-title') {
  const host = document.getElementById(hostId); host.replaceChildren();
  const t = pick(), a = AR[t.name];
  document.getElementById(titleId).textContent = `${t.name}: no-damage chance from every direction vs ${pen} mm`;
  const W = width(hostId), m = { l: 46, r: 10, t: 10, b: 40 }, H = 260;
  const n = a.az.length, cw = (W - m.l - m.r) / n, chh = (H - m.t - m.b) / a.el.length;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Hemisphere armor map' }, host);
  // x runs -180..180 with front in the middle
  const col = k => (k + n / 2) % n;
  a.el.forEach((elv, ei) => {
    const y = m.t + (a.el.length - 1 - ei) * chh;
    txt(svg, m.l - 6, y + chh / 2 + 4, `${elv}°`, { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10 });
    a.az.forEach((az, ai) => {
      const v = noDmg(a, ei, ai), x = m.l + col(ai) * cw;
      const r = el('rect', { x: x + 0.5, y: y + 0.5, width: cw - 1, height: chh - 1, fill: seqVar(v) }, svg);
      r.addEventListener('pointermove', ev => showTip(ev, [pct(v), `from ${sideName(az)} (${az}°), ${elv}° above level`, `${(a.area[ei][ai]).toFixed(1)} m² visible, ${pct(a.tread[ei][ai])} treads`]));
      r.addEventListener('pointerleave', hideTip);
    });
  });
  for (const [az, l] of [[180, 'rear'], [270, 'right'], [0, 'front'], [90, 'left'], [175, 'rear']]) {
    const ai = a.az.indexOf(az); if (ai < 0) continue;
    txt(svg, m.l + col(ai) * cw + cw / 2, H - m.b + 16, l, { 'text-anchor': 'middle', fill: 'var(--ink-2)', 'font-size': 11 });
  }
  txt(svg, m.l, H - 6, 'direction the shot comes from →  ·  ↑ shooter elevation', { fill: 'var(--muted)', 'font-size': 11 });
}

// 3. x-ray views
const CAT = [
  ['pen', 'Penetrates', '--x-pen'], ['fifty', '50/50', '--x-fifty'], ['bounce', 'Too thick', '--x-bounce'],
  ['auto', 'Auto-bounce angle (over 80°)', '--x-auto'], ['tread', 'Treads (tracks you, no HP damage)', '--x-tread'], ['crit', 'Crit module', '--x-crit'],
];
function catOf(eff, mod) {
  if (mod === 1) return 'tread';
  if (mod === 2) return 'crit';
  if (eff === 999) return 'auto';
  if (eff <= pen) return 'pen';
  if (eff <= pen * FIFTY) return 'fifty';
  return 'bounce';
}
function drawXray(hostId = 'xray', titleId = 'xray-title', legendId = 'xray-legend') {
  const host = document.getElementById(hostId); host.replaceChildren();
  const t = pick(), a = AR[t.name];
  document.getElementById(titleId).textContent = `${t.name} under a ${pen} mm gun`;
  const cs = getComputedStyle(document.documentElement);
  const colours = Object.fromEntries(CAT.map(([k, , v]) => [k, cs.getPropertyValue(v).trim()]));
  const grid = document.createElement('div'); grid.className = 'xgrid'; host.append(grid);
  const W = width(hostId);
  for (const [key, label] of [['front', 'Front'], ['left', 'Left side'], ['rear', 'Rear'], ['top', 'From above']]) {
    const v = a.views[key]; if (!v) continue;
    const fig = document.createElement('figure'); fig.className = 'xview';
    const cap = document.createElement('figcaption');
    const counts = {}; let tot = 0;
    v.eff.forEach((e, i) => { if (e < 0) return; tot++; const c = catOf(e, v.mod[i]); counts[c] = (counts[c] || 0) + 1; });
    cap.textContent = `${label} · ${pct(((counts.pen || 0) + (counts.crit || 0) + 0.5 * (counts.fifty || 0)) / Math.max(tot, 1))} of hits do damage`;
    const scale = Math.max(1, Math.min(Math.floor(Math.min(W / 2 - 20, 520) / v.w), Math.floor(300 / v.h)));
    const cv = document.createElement('canvas'); cv.width = v.w; cv.height = v.h;
    cv.style.width = `${v.w * scale}px`; cv.style.maxWidth = '100%'; cv.style.imageRendering = 'pixelated';
    const ctx = cv.getContext('2d'), img = ctx.createImageData(v.w, v.h);
    const rgb = {}; for (const [k, c] of Object.entries(colours)) { const d = document.createElement('canvas').getContext('2d'); d.fillStyle = c; d.fillRect(0, 0, 1, 1); rgb[k] = d.getImageData(0, 0, 1, 1).data; }
    v.eff.forEach((e, i) => { if (e < 0) return; const c = rgb[catOf(e, v.mod[i])]; img.data.set([c[0], c[1], c[2], 255], i * 4); });
    ctx.putImageData(img, 0, 0);
    cv.addEventListener('pointermove', ev => {
      const r = cv.getBoundingClientRect(), x = Math.floor((ev.clientX - r.left) / r.width * v.w), y = Math.floor((ev.clientY - r.top) / r.height * v.h);
      const i = y * v.w + x, e = v.eff[i]; if (e === undefined || e < 0) { hideTip(); return; }
      const c = catOf(e, v.mod[i]);
      showTip(ev, [e === 999 ? 'over 80°' : `${e} mm effective`, CAT.find(k => k[0] === c)[1], `${t.name}, ${label.toLowerCase()}`]);
    });
    cv.addEventListener('pointerleave', hideTip);
    fig.append(cv, cap); grid.append(fig);
  }
  const lg = document.getElementById(legendId); lg.replaceChildren();
  for (const [, label, v] of CAT) { const s = document.createElement('span'); const k = document.createElement('i'); k.className = 'key'; k.style.background = `var(${v})`; k.style.borderRadius = '2px'; s.append(k, label); lg.append(s); }
}

// 4. duel matrix
function drawDuel() {
  const host = document.getElementById('duel'); host.replaceChildren();
  const M = T.duel[duelMode], ord = [...tanks.keys()].sort((i, j) => M[j].filter(x => x > 0).length - M[i].filter(x => x > 0).length);
  const n = ord.length, lab = 78, cell = Math.min(32, (Math.max(560, width('duel')) - lab - 60) / n);
  const svg = el('svg', { viewBox: `0 0 ${lab + cell * n + 60} ${lab + cell * n + 10}`, role: 'img', 'aria-label': 'One on one time-to-kill matrix' }, host);
  const div = x => { const s = Math.max(-1, Math.min(1, x / 2)); const k = Math.round(Math.abs(s) * 3); return k === 0 ? 'var(--div-0)' : `var(--div-${s > 0 ? 'p' : 'n'}${k})`; };
  ord.forEach((i, r) => {
    const A = tanks[i];
    txt(svg, lab - 6, lab + r * cell + cell / 2 + 4, A.name, { 'text-anchor': 'end', fill: TA.selected === A.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': TA.selected === A.id ? 600 : 400 });
    txt(svg, 0, 0, A.name, { transform: `translate(${lab + r * cell + cell / 2 + 4},${lab - 6}) rotate(-60)`, fill: 'var(--ink-2)' });
    const wins = M[i].filter(x => x > 0).length;
    txt(svg, lab + n * cell + 8, lab + r * cell + cell / 2 + 4, `${wins} wins`, { fill: 'var(--muted)', 'font-size': 10.5 });
    ord.forEach((j, c) => {
      if (i === j) { el('rect', { x: lab + c * cell + 1, y: lab + r * cell + 1, width: cell - 2, height: cell - 2, rx: 2, fill: 'var(--grid)' }, svg); return; }
      const x = M[i][j], rc = el('rect', { x: lab + c * cell + 1, y: lab + r * cell + 1, width: cell - 2, height: cell - 2, rx: 2, fill: div(x) }, svg);
      rc.addEventListener('pointermove', ev => showTip(ev, [x > 0 ? `${2 ** x < 10 ? (2 ** x).toFixed(1) : Math.round(2 ** x)}× faster` : `${2 ** -x < 10 ? (2 ** -x).toFixed(1) : Math.round(2 ** -x)}× slower`,
        `${A.name} (row) killing ${tanks[j].name} (column)`, x > 0 ? `${A.name} wins this face-off` : `${tanks[j].name} wins this face-off`]));
      rc.addEventListener('pointerleave', hideTip);
    });
  });
}

TA.chart('armor', drawRoses); TA.chart('armor', () => drawHemi()); TA.chart('armor', () => drawXray());
TA.chart('combat', drawDuel);
TA.chart('tank', () => { if (!TA.selected) return; drawRose('t-rose'); drawHemi('t-hemi', 't-hemi-title'); drawXray('t-xray', 't-xray-title', 't-xray-legend'); });
// this file loads after the router's first draw, so draw now if its page is already showing
if (['armor', 'combat', 'tank'].includes(TA.page)) TA.redraw();
})();
