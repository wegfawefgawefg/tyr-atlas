// Stat distributions: density explorer, one-tank z-score profile, stat correlation matrix.
(() => {
const TA = window.TA, { el, txt, fmt, dot, showTip, hideTip, niceTicks, width, tanks, stats, statBy, CLS } = TA;
const CLASSES = ['Light', 'Medium', 'Heavy'];
const val = (t, k) => t[TA.mode][k];
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
const sdev = a => { const m = mean(a); return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1)); };
const skew = a => { const m = mean(a), n = a.length; const m2 = a.reduce((s, v) => s + (v - m) ** 2, 0) / n, m3 = a.reduce((s, v) => s + (v - m) ** 3, 0) / n; return m2 ? m3 / m2 ** 1.5 : 0; };
const gauss = (x, m, s) => Math.exp(-0.5 * ((x - m) / s) ** 2) / (s * Math.sqrt(2 * Math.PI));
const kde = (xs, h) => x => xs.reduce((s, v) => s + gauss(x, v, h), 0) / xs.length;
const sign = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2);
const unitOf = k => statBy[k].unit;
const withUnit = (k, v) => `${fmt(k, v)} ${unitOf(k)}`.trim();
const varies = (k, m) => { const v = tanks.map(t => t[m][k]); return Math.max(...v) > Math.min(...v); };
const pathOf = pts => pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');

// HTML legend with small line or swatch keys
function legend(host, items) {
  host.replaceChildren();
  for (const it of items) {
    const s = document.createElement('span');
    const k = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    k.setAttribute('width', 22); k.setAttribute('height', 10); k.style.width = '22px'; k.style.display = 'inline-block';
    if (it.kind === 'band') el('rect', { x: 0, y: 1, width: 22, height: 8, fill: it.color, 'fill-opacity': it.op ?? 1, rx: 2 }, k);
    else if (it.kind === 'dot') el('circle', { cx: 11, cy: 5, r: 4, fill: it.color, stroke: it.stroke || 'none', 'stroke-width': 1.5 }, k);
    else el('line', { x1: 1, x2: 21, y1: 5, y2: 5, stroke: it.color, 'stroke-width': 2, 'stroke-dasharray': it.dash || '' }, k);
    s.append(k, it.label); host.append(s);
  }
}

// ---------- 1. distribution explorer ----------
const ds = document.getElementById('ds');
for (const s of stats) { const o = document.createElement('option'); o.value = s.key; o.textContent = `${s.label} (${s.group})`; ds.append(o); }
ds.value = 'DPS';
ds.onchange = drawDist;
legend(document.getElementById('dist-legend'), [
  { label: 'Kernel density', color: 'var(--accent)' },
  { label: 'Normal fit', color: 'var(--ink-2)', dash: '4 3' },
  { label: 'Mean ± 1σ', color: 'var(--grid)', kind: 'band' },
]);

// stack near-equal x positions into levels so dots don't overlap
function levels(items, gap) {
  const lv = []; const out = [];
  for (const it of [...items].sort((a, b) => a.x - b.x)) {
    let l = 0; while (lv[l] !== undefined && it.x - lv[l] < gap) l++;
    lv[l] = it.x; out.push({ ...it, l });
  }
  return out;
}

function drawDist() {
  const host = document.getElementById('dist'); host.replaceChildren();
  const k = ds.value, s = statBy[k], line = document.getElementById('dist-stats');
  const xs = tanks.map(t => val(t, k)), mu = mean(xs), sd = sdev(xs), sk = skew(xs);
  const W = width('dist');
  if (!(sd > 0)) {
    const svg = el('svg', { viewBox: `0 0 ${W} 40` }, host);
    txt(svg, 0, 24, `Every tank has the same ${s.label.toLowerCase()} in this mode: ${withUnit(k, xs[0])}.`, { fill: 'var(--muted)', 'font-size': 12 });
    line.textContent = ''; return;
  }
  const lo0 = Math.min(...xs), hi0 = Math.max(...xs), span = hi0 - lo0;
  const q = [...xs].sort((a, b) => a - b), iqr = q[Math.floor(q.length * 0.75)] - q[Math.floor(q.length * 0.25)];
  const h = 1.06 * Math.min(sd, iqr / 1.34 || sd) * xs.length ** -0.2;   // Silverman bandwidth
  const lo = Math.min(lo0 - 2.6 * h, mu - 2.6 * sd), hi = Math.max(hi0 + 2.6 * h, mu + 2.6 * sd);
  const lab = 84, m = { l: lab, r: 18, t: 22 };
  const X = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
  const Hd = Math.max(160, Math.min(230, W * 0.24));
  const f = kde(xs, h), N = 180, grid = Array.from({ length: N + 1 }, (_, i) => lo + (hi - lo) * i / N);
  const dk = grid.map(f), dn = grid.map(x => gauss(x, mu, sd)), ymax = Math.max(...dk, ...dn) * 1.08;
  const base = m.t + Hd, Y = d => base - d / ymax * Hd;
  // rug positions
  const rug = levels(tanks.map(t => ({ t, x: X(val(t, k)) })), 9);
  const nLv = Math.max(...rug.map(r => r.l)) + 1;
  const rugTop = base + 12, axisY = rugTop + nLv * 9 + 4, rowsTop = axisY + 40, rowH = 44;
  const H = rowsTop + CLASSES.length * rowH + 6;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Distribution of ${s.label} across tanks` }, host);
  // sigma band, ticks, mean
  el('rect', { x: X(mu - sd), y: m.t, width: X(mu + sd) - X(mu - sd), height: Hd, fill: 'var(--grid)', 'fill-opacity': 0.45 }, svg);
  for (const v of niceTicks(lo, hi, W < 560 ? 4 : 7)) {
    el('line', { x1: X(v), x2: X(v), y1: axisY - 4, y2: axisY, stroke: 'var(--axis)' }, svg);
    txt(svg, X(v), axisY + 13, fmt('', v), { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' });
  }
  el('line', { x1: m.l, x2: W - m.r, y1: base, y2: base, stroke: 'var(--axis)' }, svg);
  el('line', { x1: m.l, x2: W - m.r, y1: axisY - 4, y2: axisY - 4, stroke: 'var(--axis)' }, svg);
  const dir = s.better > 0 ? 'higher is better →' : '← lower is better';
  txt(svg, s.better > 0 ? W - m.r : m.l, axisY + 30, `${s.label}${s.unit ? ' (' + s.unit + ')' : ''} · ${dir}`, { 'text-anchor': s.better > 0 ? 'end' : 'start', fill: 'var(--ink-2)', 'font-size': 12 });
  txt(svg, 0, m.t + 10, 'All tanks', { fill: 'var(--ink)', 'font-size': 12.5, 'font-weight': 600 });
  txt(svg, 0, m.t + 26, `n = ${xs.length}`, { fill: 'var(--muted)', 'font-size': 11 });
  // curves
  const kp = grid.map((x, i) => [X(x), Y(dk[i])]);
  el('path', { d: pathOf(kp) + ` L ${X(hi).toFixed(1)} ${base} L ${X(lo).toFixed(1)} ${base} Z`, fill: 'var(--accent)', 'fill-opacity': 0.12 }, svg);
  el('path', { d: pathOf(kp), fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
  el('path', { d: pathOf(grid.map((x, i) => [X(x), Y(dn[i])])), fill: 'none', stroke: 'var(--ink-2)', 'stroke-width': 1.5, 'stroke-dasharray': '4 3' }, svg);
  el('line', { x1: X(mu), x2: X(mu), y1: m.t - 4, y2: base, stroke: 'var(--ink-2)', 'stroke-width': 1 }, svg);
  const muLab = `mean ${fmt(k, mu)}`;
  txt(svg, X(mu), m.t - 8, muLab, { 'text-anchor': 'middle', fill: 'var(--ink)', 'font-size': 11, 'font-family': 'var(--f-data)' });
  txt(svg, X(mu - sd) + 3, base - 5, '−1σ', { fill: 'var(--muted)', 'font-size': 10 });
  txt(svg, X(mu + sd) - 3, base - 5, '+1σ', { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10 });
  // hover on the curve area: value + density reading
  const hit = el('rect', { x: m.l, y: m.t, width: W - m.l - m.r, height: Hd, fill: 'transparent' }, svg);
  const cross = el('line', { y1: m.t, y2: base, stroke: 'var(--axis)', visibility: 'hidden' }, svg);
  hit.addEventListener('pointermove', ev => {
    const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * W / r.width, v = lo + (px - m.l) / (W - m.l - m.r) * (hi - lo);
    cross.setAttribute('x1', px); cross.setAttribute('x2', px); cross.setAttribute('visibility', 'visible');
    const near = tanks.filter(t => Math.abs(val(t, k) - v) <= h).map(t => t.name);
    showTip(ev, [withUnit(k, v), `${((v - mu) / sd >= 0 ? '+' : '−')}${Math.abs((v - mu) / sd).toFixed(1)}σ from the mean`, near.length ? `Within one bandwidth: ${near.join(', ')}` : 'No tank within one bandwidth']);
  });
  hit.addEventListener('pointerleave', () => { cross.setAttribute('visibility', 'hidden'); hideTip(); });
  const rows = t => { const v = val(t, k); return [withUnit(k, v), t.name, `${t.cls} · ${sign((v - mu) / sd)}σ from the mean`]; };
  for (const r of rug) dot(svg, r.t, r.x, rugTop + r.l * 9, 3.6, () => rows(r.t));
  // class rows: mirrored density (violin), dots, class mean
  CLASSES.forEach((c, i) => {
    const ct = tanks.filter(t => t.cls === c), cv = ct.map(t => val(t, k)), cm = mean(cv), cy = rowsTop + i * rowH + rowH / 2;
    const colr = `var(${CLS[c]})`;
    txt(svg, 0, cy - 2, `${c} (${ct.length})`, { fill: 'var(--ink)', 'font-size': 12.5 });
    txt(svg, 0, cy + 13, `mean ${fmt(k, cm)}`, { fill: 'var(--muted)', 'font-size': 10.5, 'font-family': 'var(--f-data)' });
    el('line', { x1: m.l, x2: W - m.r, y1: cy, y2: cy, stroke: 'var(--grid)' }, svg);
    const fc = kde(cv, h), a = Math.max(lo, Math.min(...cv) - 2.2 * h), b = Math.min(hi, Math.max(...cv) + 2.2 * h);
    const g2 = Array.from({ length: 81 }, (_, j) => a + (b - a) * j / 80), d2 = g2.map(fc), dm = Math.max(...d2), hh = rowH * 0.36;
    const up = g2.map((x, j) => [X(x), cy - d2[j] / dm * hh]), dn2 = g2.map((x, j) => [X(x), cy + d2[j] / dm * hh]).reverse();
    el('path', { d: pathOf([...up, ...dn2]) + ' Z', fill: colr, 'fill-opacity': 0.16, stroke: colr, 'stroke-width': 1.2, 'stroke-opacity': 0.7 }, svg);
    el('line', { x1: X(cm), x2: X(cm), y1: cy - hh - 3, y2: cy + hh + 3, stroke: 'var(--ink)', 'stroke-width': 2 }, svg);
    for (const r of levels(ct.map(t => ({ t, x: X(val(t, k)) })), 8)) dot(svg, r.t, r.x, cy + (r.l % 2 ? 1 : -1) * Math.ceil(r.l / 2) * 7, 3.4, () => rows(r.t));
  });
  const tail = Math.abs(sk) < 0.3 ? 'roughly symmetric' : sk > 0 ? 'long tail to the high side' : 'long tail to the low side';
  line.textContent = `Mean ${withUnit(k, mu)} · σ ${fmt(k, sd)} · skew ${sign(sk)} (${tail}) · range ${fmt(k, lo0)} to ${fmt(k, hi0)} · bandwidth ${fmt(k, h)}`;
}

// ---------- 2. one tank's z-score profile ----------
// hostId/noteId let the tank page draw the same chart into its own container; noteId may be null
function drawZ(hostId = 'zprof', noteId = 'z-note') {
  const host = document.getElementById(hostId); host.replaceChildren();
  const t = tanks.find(x => x.id === TA.selected) || TA.sortedTanks[0];
  if (noteId) document.getElementById(noteId).textContent = TA.selected ? `${t.name}, ${t.cls.toLowerCase()}, ${TA.mode === 'base' ? 'base stats' : '31-point core build'}.`
    : `Showing ${t.name}. Pick a tank in the header to see its profile.`;
  const W = width(hostId), lab = W < 560 ? 124 : 190, pad = 52, rh = 21;
  const groups = [...new Set(stats.map(s => s.group))];
  const rows = []; let H = 0;
  for (const g of groups) {
    const ss = stats.filter(s => s.group === g && varies(s.key, TA.mode));
    if (!ss.length) continue;
    rows.push({ g }); H += 26;
    for (const s of ss) { const xs = tanks.map(u => val(u, s.key)), mu = mean(xs), sd = sdev(xs); rows.push({ s, mu, sd, z: (val(t, s.key) - mu) / sd * s.better }); H += rh; }
  }
  const L = Math.max(3, Math.ceil(Math.max(...rows.filter(r => r.s).map(r => Math.abs(r.z)))));
  const x0 = lab + pad, x1 = W - pad, X = z => x0 + (z + L) / (2 * L) * (x1 - x0);
  const top = 18, svg = el('svg', { viewBox: `0 0 ${W} ${H + top + 8}`, role: 'img', 'aria-label': `${t.name}: standard deviations from the roster mean on every stat` }, host);
  for (let z = -L; z <= L; z++) {
    el('line', { x1: X(z), x2: X(z), y1: top, y2: top + H, stroke: z === 0 ? 'var(--axis)' : 'var(--grid)', 'stroke-width': z === 0 ? 1.5 : 1 }, svg);
    if (W >= 480 || z % 2 === 0) txt(svg, X(z), 10, z === 0 ? 'mean' : `${z > 0 ? '+' : '−'}${Math.abs(z)}σ`, { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' });
  }
  let y = top; const colr = TA.col(t);
  for (const r of rows) {
    if (r.g) { txt(svg, 0, y + 18, r.g.toUpperCase(), { 'font-size': 11, 'font-weight': 600, fill: 'var(--muted)', 'letter-spacing': '.06em' }); y += 26; continue; }
    const s = r.s, cy = y + rh / 2, v = val(t, s.key);
    txt(svg, 0, cy + 4, s.label, { fill: 'var(--ink)', 'font-size': 12 });
    const a = X(Math.min(0, r.z)), b = X(Math.max(0, r.z));
    el('rect', { x: a, y: cy - 5, width: Math.max(1.5, b - a), height: 10, rx: 2, fill: colr, 'fill-opacity': Math.abs(r.z) >= 2 ? 1 : 0.7 }, svg);
    const tx = r.z >= 0 ? b + 5 : a - 5;
    txt(svg, tx, cy + 4, `${sign(r.z)} · ${fmt(s.key, v)}`, { 'text-anchor': r.z >= 0 ? 'start' : 'end', fill: 'var(--ink-2)', 'font-size': 10, 'font-family': 'var(--f-data)' });
    const hitR = el('rect', { x: 0, y, width: W, height: rh, fill: 'transparent' }, svg);
    hitR.addEventListener('pointermove', ev => showTip(ev, [`${sign(r.z)}σ`, `${s.label}: ${withUnit(s.key, v)}`, `Roster mean ${withUnit(s.key, r.mu)}, σ ${fmt(s.key, r.sd)}`, s.better > 0 ? 'Higher is better' : 'Lower is better, so the bar is flipped']));
    hitR.addEventListener('pointerleave', hideTip);
    y += rh;
  }
}

// ---------- 3. correlation matrix ----------
function pearson(a, b) {
  const ma = mean(a), mb = mean(b); let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < a.length; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y; }
  return sab / Math.sqrt(saa * sbb);
}
// average-linkage clustering on 1 − |r|; returns leaf order
function clusterOrder(R) {
  let cl = R.map((_, i) => [i]);
  const d = (A, B) => { let s = 0; for (const i of A) for (const j of B) s += 1 - Math.abs(R[i][j]); return s / (A.length * B.length); };
  while (cl.length > 1) {
    let bi = 0, bj = 1, bd = Infinity;
    for (let i = 0; i < cl.length; i++) for (let j = i + 1; j < cl.length; j++) { const x = d(cl[i], cl[j]); if (x < bd) { bd = x; bi = i; bj = j; } }
    let A = cl[bi], B = cl[bj];
    // orient so the most correlated ends touch
    const best = [[A, B], [A.slice().reverse(), B], [A, B.slice().reverse()], [A.slice().reverse(), B.slice().reverse()]]
      .reduce((p, q) => (Math.abs(R[q[0].at(-1)][q[1][0]]) > Math.abs(R[p[0].at(-1)][p[1][0]]) ? q : p));
    cl = cl.filter((_, k) => k !== bi && k !== bj); cl.push([...best[0], ...best[1]]);
  }
  return cl[0];
}
const DIV = [[-0.75, '--div-n3'], [-0.45, '--div-n2'], [-0.15, '--div-n1'], [0.15, '--div-0'], [0.45, '--div-p1'], [0.75, '--div-p2'], [Infinity, '--div-p3']];
const divCol = r => `var(${DIV.find(([e]) => r < e)[1]})`;
legend(document.getElementById('corr-legend'), [
  ['below −0.75', '--div-n3'], ['−0.75 to −0.45', '--div-n2'], ['−0.45 to −0.15', '--div-n1'], ['about 0', '--div-0'],
  ['0.15 to 0.45', '--div-p1'], ['0.45 to 0.75', '--div-p2'], ['above 0.75', '--div-p3'],
].map(([label, v]) => ({ label, color: `var(${v})`, kind: 'band' })));

const RATING = 'Designer ratings';
const gameKeys = stats.filter(s => s.group !== RATING && varies(s.key, 'base')).map(s => s.key);
const rateKeys = stats.filter(s => s.group === RATING && varies(s.key, 'base')).map(s => s.key);
const col = k => tanks.map(t => t.base[k]);
const R = gameKeys.map(a => gameKeys.map(b => pearson(col(a), col(b))));
const order = clusterOrder(R).map(i => gameKeys[i]);
const RR = rateKeys.map(a => order.map(b => pearson(col(a), col(b))));

function drawCorr() {
  const host = document.getElementById('corr'); host.replaceChildren();
  const n = order.length, lab = 150, topH = 112, W = Math.max(680, width('corr'));
  const cell = Math.max(13, Math.min(20, (W - lab - 70) / n)), gap = 34;
  const Wsvg = lab + n * cell + 70, H = topH + n * cell + gap + rateKeys.length * cell + 6;
  const svg = el('svg', { viewBox: `0 0 ${Wsvg} ${H}`, role: 'img', 'aria-label': 'Correlation matrix of tank stats' }, host);
  const short = k => statBy[k].label;
  order.forEach((k, j) => txt(svg, 0, 0, short(k), { transform: `translate(${lab + j * cell + cell / 2 + 3},${topH - 6}) rotate(-60)`, 'font-size': 10.5 }));
  const cellAt = (x, y, r, a, b) => {
    const c = el('rect', { x: x + 1, y: y + 1, width: cell - 2, height: cell - 2, rx: 2, fill: a === b ? 'var(--axis)' : divCol(r) }, svg);
    if (a === b) return;
    c.addEventListener('pointermove', ev => showTip(ev, [`r = ${sign(r)}`, `${statBy[a].label} and ${statBy[b].label}`, r > 0 ? 'rise together' : 'one rises as the other falls']));
    c.addEventListener('pointerleave', hideTip);
  };
  order.forEach((a, i) => {
    txt(svg, lab - 6, topH + i * cell + cell / 2 + 4, short(a), { 'text-anchor': 'end', 'font-size': 10.5 });
    const ia = gameKeys.indexOf(a);
    order.forEach((b, j) => cellAt(lab + j * cell, topH + i * cell, R[ia][gameKeys.indexOf(b)], a, b));
  });
  const y0 = topH + n * cell + gap;
  txt(svg, 0, y0 - 10, 'DESIGNER RATINGS', { 'font-size': 11, 'font-weight': 600, fill: 'var(--muted)', 'letter-spacing': '.06em' });
  rateKeys.forEach((a, i) => {
    txt(svg, lab - 6, y0 + i * cell + cell / 2 + 4, short(a), { 'text-anchor': 'end', 'font-size': 10.5, fill: 'var(--ink)' });
    order.forEach((b, j) => cellAt(lab + j * cell, y0 + i * cell, RR[i][j], a, b));
  });
  // plain-language notes for each rating
  const notes = document.getElementById('corr-notes'); notes.replaceChildren();
  rateKeys.forEach((a, i) => {
    const pairs = order.map((b, j) => [b, RR[i][j]]).sort((p, q) => q[1] - p[1]);
    const pos = pairs.filter(p => p[1] >= 0.47).slice(0, 2), neg = pairs.filter(p => p[1] <= -0.47).reverse().slice(0, 2);
    const li = document.createElement('li'), b = document.createElement('b'); b.textContent = statBy[a].label;
    const part = ps => ps.map(([k, r]) => `${statBy[k].label.toLowerCase()} (${sign(r)})`).join(' and ');
    let s = pos.length ? ` tracks ${part(pos)}` : ' has no strong positive link to any stat';
    if (neg.length) s += `${pos.length ? ', but' : ', and'} runs against ${part(neg)}`;
    li.append(b, s + '.'); notes.append(li);
  });
}

TA.chart('stats', drawDist); TA.chart('stats', () => drawZ());
TA.chart('compare', drawCorr);
TA.chart('tank', () => { if (TA.selected) drawZ('t-zprof', null); });
})();
