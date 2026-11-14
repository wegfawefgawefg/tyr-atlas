(() => {
const T = window.TYR, tanks = T.tanks, stats = T.stats;
const statBy = Object.fromEntries(stats.map(s => [s.key, s]));
const CLS = { Light: '--c-light', Medium: '--c-medium', Heavy: '--c-heavy' };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const col = t => `var(${CLS[t.cls]})`;
const NS = 'http://www.w3.org/2000/svg';
let mode = 'base', selected = null;
const val = (t, k) => t[mode][k];
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); if (parent) parent.appendChild(e); return e; };
const txt = (parent, x, y, s, attrs = {}) => { const e = el('text', { x, y, fill: 'var(--ink-2)', 'font-size': 11, ...attrs }, parent); e.textContent = s; return e; };
const fmt = (k, v) => { const d = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2; return (+v).toFixed(d).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1'); };
const unit = k => statBy[k] ? statBy[k].unit : '';
const width = id => Math.max(320, document.getElementById(id).clientWidth);

document.getElementById('source').textContent =
  `Steam build ${T.source.steam_buildid} · talent data v${T.source.talent_tree_version} · extracted 2026-11-14 · standard ammo, no components or abilities`;

// legend + chips
const legend = document.getElementById('legend');
for (const c of ['Light', 'Medium', 'Heavy']) { const s = document.createElement('span'); const k = document.createElement('i'); k.className = 'key'; k.style.background = `var(${CLS[c]})`; s.append(k, c); legend.append(s); }
{ const s = document.createElement('span'); const k = document.createElement('i'); k.className = 'key hollow'; s.append(k, 'Work in progress'); legend.append(s); }
const chips = document.getElementById('chips');
const sortedTanks = [...tanks].sort((a, b) => ['Light', 'Medium', 'Heavy'].indexOf(a.cls) - ['Light', 'Medium', 'Heavy'].indexOf(b.cls) || a.name.localeCompare(b.name));
for (const t of sortedTanks) {
  const b = document.createElement('button'); b.setAttribute('aria-pressed', 'false'); b.dataset.id = t.id;
  const k = document.createElement('i'); k.className = 'key' + (t.wip ? ' hollow' : ''); if (!t.wip) k.style.background = col(t); else k.style.borderColor = col(t);
  b.append(k, t.name); b.onclick = () => select(selected === t.id ? null : t.id); chips.append(b);
}

// tooltip
const tip = document.getElementById('tip');
function showTip(ev, rows) {
  tip.replaceChildren();
  for (const [i, r] of rows.entries()) { const d = document.createElement(i === 0 ? 'strong' : 'div'); d.textContent = r; if (i > 1) d.className = 'k'; tip.append(d); }
  tip.hidden = false;
  const x = Math.min(ev.clientX + 14, innerWidth - tip.offsetWidth - 8), y = Math.min(ev.clientY + 14, innerHeight - tip.offsetHeight - 8);
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
const hideTip = () => { tip.hidden = true; };
function dot(svg, t, cx, cy, r, rows) {
  const g = el('g', { 'data-id': t.id }, svg);
  el('circle', { cx, cy, r: 12, fill: 'transparent' }, g);
  const c = el('circle', { class: 'dot', cx, cy, r, fill: t.wip ? 'var(--surface)' : col(t), stroke: t.wip ? col(t) : 'var(--surface)', 'stroke-width': 2 }, g);
  if (selected === t.id) { c.setAttribute('r', r + 2.5); c.setAttribute('stroke', 'var(--ink)'); }
  g.addEventListener('pointermove', ev => showTip(ev, rows()));
  g.addEventListener('pointerleave', hideTip);
  g.addEventListener('click', () => select(selected === t.id ? null : t.id));
  g.style.cursor = 'pointer';
  return g;
}

// strips
function drawStrips() {
  const host = document.getElementById('strips'); host.replaceChildren(); hideTip();
  const W = width('strips'), labelW = W < 560 ? 118 : 190, padR = 70, rowH = 30;
  const groups = [...new Set(stats.map(s => s.group))];
  let H = 0; const rows = [];
  for (const g of groups) { rows.push({ g }); H += 28; for (const s of stats.filter(s => s.group === g)) { rows.push({ s, h: rowH }); H += rowH; } }
  const svg = el('svg', { viewBox: `0 0 ${W} ${H + 6}`, role: 'img', 'aria-label': 'Strip plot of every tank on every stat' }, host);
  let y = 0;
  for (const r of rows) {
    if (r.g) { txt(svg, 0, y + 20, r.g.toUpperCase(), { 'font-size': 11, 'font-weight': 600, fill: 'var(--muted)', 'letter-spacing': '.06em' }); y += 28; continue; }
    const s = r.s, vals = tanks.map(t => val(t, s.key)), rh = r.h;
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const x0 = labelW, x1 = W - padR, cy = y + rh / 2;
    if (hi === lo) {
      txt(svg, 0, cy + 4, s.label, { fill: 'var(--ink)', 'font-size': 12.5 });
      txt(svg, x0, cy + 4, `Same for every tank in this mode: ${fmt(s.key, lo)} ${s.unit}`.trim(), { fill: 'var(--muted)', 'font-size': 11.5 });
      y += rh; continue;
    }
    const X = v => s.better > 0 ? x0 + (v - lo) / (hi - lo) * (x1 - x0) : x1 - (v - lo) / (hi - lo) * (x1 - x0);
    txt(svg, 0, cy + 4, s.label, { fill: 'var(--ink)', 'font-size': 12.5 });
    el('line', { x1: x0, x2: x1, y1: cy, y2: cy, stroke: 'var(--grid)', 'stroke-width': 1 }, svg);
    const worst = s.better > 0 ? lo : hi, best = s.better > 0 ? hi : lo;
    txt(svg, x0 - 6, cy + 4, fmt(s.key, worst), { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' });
    // ties and near-ties: pack each cluster into a block at most 3 dots tall, spreading sideways, kept inside the axis
    const order = tanks.map((t, i) => [t, X(vals[i])]).sort((a, b) => a[1] - b[1]);
    const clusters = [];
    for (const [t, x] of order) { const c = clusters[clusters.length - 1]; if (c && x - c.x1 < 9) { c.items.push([t, x]); c.x1 = x; } else clusters.push({ x1: x, items: [[t, x]] }); }
    const placed = [];
    for (const c of clusters) {
      const n = c.items.length;
      if (n === 1 || (n === 2 && c.items[1][1] - c.items[0][1] >= 7)) { for (const [t, x] of c.items) placed.push({ t, x, dy: 0 }); continue; }
      const rowsN = Math.min(3, n), colsN = Math.ceil(n / rowsN), step = 7.5;
      const mid = c.items.reduce((a, [, x]) => a + x, 0) / n;
      let left = mid - (colsN - 1) * step / 2; left = Math.max(x0, Math.min(x1 - (colsN - 1) * step, left));
      c.items.forEach(([t], i) => placed.push({ t, x: left + Math.floor(i / rowsN) * step, dy: ((i % rowsN) - (rowsN - 1) / 2) * 7.5 }));
    }
    for (const p of placed) {
      dot(svg, p.t, p.x, cy + p.dy, 3.6, () => [`${fmt(s.key, val(p.t, s.key))} ${s.unit}`.trim(), p.t.name, `${s.label} · ${p.t.cls}`]);
    }
    const bestV = s.better > 0 ? hi : lo, nBest = vals.filter(v => Math.abs(v - bestV) < 1e-9).length;
    const top = placed.reduce((a, b) => (b.x > a.x ? b : a));
    txt(svg, x1 + 12, cy + 4, nBest > 1 ? `${nBest} tied` : `${top.t.name}`, { fill: nBest > 1 ? 'var(--muted)' : 'var(--ink)', 'font-size': 11 });
    if (selected) { const p = placed.find(p => p.t.id === selected); if (p && p !== top) txt(svg, p.x, cy + p.dy - 9, `${fmt(s.key, val(p.t, s.key))}`, { 'text-anchor': 'middle', 'font-size': 10, fill: 'var(--ink)', 'font-family': 'var(--f-data)' }); }
    y += rh;
  }
}

// scatter
const sx = document.getElementById('sx'), sy = document.getElementById('sy'), us = document.getElementById('us');
for (const s of stats) for (const sel of [sx, sy, us]) { const o = document.createElement('option'); o.value = s.key; o.textContent = s.label; sel.append(o); }
sx.value = 'MaxHealth'; sy.value = 'DPS'; us.value = 'DPS';
function niceTicks(lo, hi, n = 5) {
  const span = hi - lo || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0);
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10)); return out;
}
function axes(svg, X, Y, xt, yt, m, W, H, xl, yl) {
  for (const v of yt) { el('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }, svg); txt(svg, m.l - 8, Y(v) + 4, fmt('', v), { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' }); }
  for (const v of xt) { el('line', { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b, stroke: 'var(--grid)' }, svg); txt(svg, X(v), H - m.b + 16, fmt('', v), { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' }); }
  el('line', { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, stroke: 'var(--axis)' }, svg);
  if (xl) txt(svg, W - m.r, H - m.b + 34, xl, { 'text-anchor': 'end', fill: 'var(--ink-2)', 'font-size': 12 });
  if (yl) txt(svg, m.l, m.t - 10, yl, { fill: 'var(--ink-2)', 'font-size': 12 });
}
function labelPoints(svg, pts) {
  // greedy: try right, left, above, below; skip if all collide
  const boxes = pts.map(p => ({ x: p.x - 7, y: p.y - 7, w: 14, h: 14 }));
  const hit = b => boxes.some(o => b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h);
  for (const p of [...pts].sort((a, b) => (b.sel - a.sel))) {
    const w = p.name.length * 6.2 + 2, h = 12;
    const cands = [[p.x + 8, p.y - 6, 'start'], [p.x - 8, p.y - 6, 'end'], [p.x, p.y - 20, 'middle'], [p.x, p.y + 8, 'middle']];
    for (const [x, y, anchor] of cands) {
      const bx = anchor === 'start' ? x : anchor === 'end' ? x - w : x - w / 2, b = { x: bx, y, w, h };
      if (!hit(b) || p.sel) { boxes.push(b); txt(svg, x, y + 10, p.name, { 'text-anchor': anchor, fill: p.sel ? 'var(--ink)' : 'var(--ink-2)', 'font-size': 11, 'font-weight': p.sel ? 600 : 400 }); break; }
    }
  }
}
function drawScatter() {
  const host = document.getElementById('scatter'); host.replaceChildren();
  const W = width('scatter'), H = Math.min(520, Math.max(340, W * 0.55)), m = { l: 52, r: 20, t: 26, b: 44 };
  const kx = sx.value, ky = sy.value;
  const xs = tanks.map(t => val(t, kx)), ys = tanks.map(t => val(t, ky));
  const pad = (a, b) => [a - (b - a) * 0.08 || a - 1, b + (b - a) * 0.08 || b + 1];
  const [x0, x1] = pad(Math.min(...xs), Math.max(...xs)), [y0, y1] = pad(Math.min(...ys), Math.max(...ys));
  const X = v => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r), Y = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Scatter of ${statBy[kx].label} against ${statBy[ky].label}` }, host);
  axes(svg, X, Y, niceTicks(x0, x1), niceTicks(y0, y1), m, W, H, `${statBy[kx].label} ${unit(kx) ? '(' + unit(kx) + ')' : ''} →`, `↑ ${statBy[ky].label} ${unit(ky) ? '(' + unit(ky) + ')' : ''}`);
  // Pareto frontier: tanks no other tank beats on both axes (each axis in its own better direction)
  const bx = statBy[kx].better, by = statBy[ky].better;
  const front = tanks.filter(a => !tanks.some(b => b !== a &&
    bx * val(b, kx) >= bx * val(a, kx) && by * val(b, ky) >= by * val(a, ky) &&
    (bx * val(b, kx) > bx * val(a, kx) || by * val(b, ky) > by * val(a, ky))));
  const fs = [...front].sort((a, b) => bx * (val(a, kx) - val(b, kx)));  // worst x first, so y runs best-first
  if (fs.length) {
    // attainment staircase: boundary of the region some frontier tank beats.
    // fs runs worst-x to best-x, so y runs best to worst; corners sit at (x_i, y_{i+1}).
    const worstX = bx > 0 ? x0 : x1, worstY = by > 0 ? y0 : y1;
    const pts_ = [[X(worstX), Y(val(fs[0], ky))]];
    fs.forEach((t, i) => {
      pts_.push([X(val(t, kx)), Y(val(t, ky))]);
      if (i + 1 < fs.length) pts_.push([X(val(t, kx)), Y(val(fs[i + 1], ky))]);
    });
    pts_.push([X(val(fs[fs.length - 1], kx)), Y(worstY)]);
    const d = pts_.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
    el('path', { d: d + ` L ${X(worstX).toFixed(1)} ${Y(worstY).toFixed(1)} Z`, fill: 'var(--accent)', 'fill-opacity': 0.07, stroke: 'none' }, svg);
    el('path', { d, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
  }
  const onFront = new Set(front.map(t => t.id));
  const pts = tanks.map(t => ({ t, x: X(val(t, kx)), y: Y(val(t, ky)), name: t.name, sel: selected === t.id || onFront.has(t.id) }));
  for (const p of pts) dot(svg, p.t, p.x, p.y, 5, () => [p.t.name, `${statBy[kx].label}: ${fmt(kx, val(p.t, kx))} ${unit(kx)}`, `${statBy[ky].label}: ${fmt(ky, val(p.t, ky))} ${unit(ky)}`, onFront.has(p.t.id) ? `${p.t.cls} · on the frontier` : `${p.t.cls} · beaten on both by another tank`]);
  labelPoints(svg, pts);
  document.getElementById('front-note').textContent = `Frontier: ${fs.map(t => t.name).join(' → ')}. The shaded area is beaten ground: every tank inside it has a tank on the line that is at least as good on both stats.`;
}

// PCA map
function drawMap() {
  const host = document.getElementById('map'); host.replaceChildren();
  const W = width('map'), H = Math.min(600, Math.max(380, W * 0.62)), m = { l: 40, r: 40, t: 36, b: 36 };
  const P = tanks.map(t => t.pca), L = T.pca.loadings;
  const ext = Math.max(...P.flat().map(Math.abs)) * 1.15;
  const sx_ = (W - m.l - m.r) / 2, sy_ = (H - m.t - m.b) / 2;
  const X = v => m.l + sx_ + v / ext * sx_, Y = v => m.t + sy_ - v / ext * sy_;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Principal component map of tanks' }, host);
  el('line', { x1: m.l, x2: W - m.r, y1: Y(0), y2: Y(0), stroke: 'var(--grid)' }, svg);
  el('line', { x1: X(0), x2: X(0), y1: m.t, y2: H - m.b, stroke: 'var(--grid)' }, svg);
  const v = T.pca.var.map(x => Math.round(x * 100));
  // axis captions from the two strongest stats at each end of each component
  const ends = ax => { const s = T.pca.keys.map((k, i) => [statBy[k].label.toLowerCase(), L[i][ax]]).sort((a, b) => b[1] - a[1]);
    return [s.slice(-2).reverse().map(x => x[0]).join(', '), s.slice(0, 2).map(x => x[0]).join(', ')]; };
  const [xneg, xpos] = ends(0), [yneg, ypos] = ends(1);
  txt(svg, W - m.r, H - 8, `more ${xpos} →`, { 'text-anchor': 'end', fill: 'var(--ink-2)' });
  txt(svg, m.l, H - 8, `← more ${xneg}`, { fill: 'var(--ink-2)' });
  txt(svg, m.l, 14, `↑ more ${ypos}   ·   ↓ more ${yneg}`, { fill: 'var(--ink-2)' });
  txt(svg, W - m.r, 14, `across ${v[0]}% · up ${v[1]}% of the spread`, { 'text-anchor': 'end', fill: 'var(--muted)' });
  // loadings: show the 8 longest
  const arrows = T.pca.keys.map((k, i) => ({ k, a: L[i] })).sort((p, q) => Math.hypot(...q.a) - Math.hypot(...p.a)).slice(0, 9);
  const scale = ext * 0.85;
  // merge arrows that point the same way so their labels don't print on top of each other
  const groups = [];
  for (const ar of arrows) {
    const ang = Math.atan2(ar.a[1], ar.a[0]), len = Math.hypot(...ar.a);
    const g = groups.find(g => Math.abs(Math.atan2(Math.sin(g.ang - ang), Math.cos(g.ang - ang))) < 0.12 && Math.abs(g.len - len) < 0.25);
    if (g) g.labels.push(statBy[ar.k].label); else groups.push({ ang, len, a: ar.a, labels: [statBy[ar.k].label] });
  }
  for (const g of groups) {
    const ex = X(g.a[0] * scale), ey = Y(g.a[1] * scale);
    el('line', { x1: X(0), y1: Y(0), x2: ex, y2: ey, stroke: 'var(--axis)', 'stroke-width': 1.5 }, svg);
    g.labels.forEach((l, i) => txt(svg, ex + (g.a[0] >= 0 ? 4 : -4), ey + (g.a[1] >= 0 ? -4 - (g.labels.length - 1 - i) * 12 : 12 + i * 12), l,
      { 'text-anchor': g.a[0] >= 0 ? 'start' : 'end', fill: 'var(--muted)', 'font-size': 10.5 }));
  }
  const pts = tanks.map(t => ({ t, x: X(t.pca[0]), y: Y(t.pca[1]), name: t.name, sel: selected === t.id }));
  for (const p of pts) dot(svg, p.t, p.x, p.y, 6, () => [p.t.name, `${p.t.cls}${p.t.wip ? ' · work in progress' : ''}`]);
  labelPoints(svg, pts);
}

// heatmap
function drawHeat() {
  const host = document.getElementById('heat'); host.replaceChildren();
  const ord = T.order.map(i => tanks[i]), n = ord.length;
  const W = Math.max(560, width('heat')), lab = 78, cell = Math.min(34, (W - lab - 10) / n), H = lab + cell * n + 4;
  const svg = el('svg', { viewBox: `0 0 ${lab + cell * n + 10} ${H}`, role: 'img', 'aria-label': 'Similarity heatmap' }, host);
  const D = T.dist, all = D.flat().filter(x => x > 0), lo = Math.min(...all), hi = Math.max(...all);
  const steps = ['--seq-7', '--seq-6', '--seq-5', '--seq-4', '--seq-3', '--seq-2', '--seq-1', '--seq-0'];
  ord.forEach((a, i) => {
    const ia = tanks.indexOf(a);
    txt(svg, lab - 6, lab + i * cell + cell / 2 + 4, a.name, { 'text-anchor': 'end', fill: selected === a.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': selected === a.id ? 600 : 400 });
    const tx = lab + i * cell + cell / 2;
    txt(svg, 0, 0, a.name, { transform: `translate(${tx + 4},${lab - 6}) rotate(-60)`, fill: selected === a.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': selected === a.id ? 600 : 400 });
    ord.forEach((b, j) => {
      const ib = tanks.indexOf(b), d = D[ia][ib];
      const s = i === j ? 'var(--grid)' : `var(${steps[Math.min(7, Math.floor((d - lo) / (hi - lo + 1e-9) * 8))]})`;
      const r = el('rect', { x: lab + j * cell + 1, y: lab + i * cell + 1, width: cell - 2, height: cell - 2, rx: 2, fill: s }, svg);
      if (i !== j) {
        r.addEventListener('pointermove', ev => showTip(ev, [`${d.toFixed(2)}`, `${a.name} and ${b.name}`, 'distance in standard deviations per stat']));
        r.addEventListener('pointerleave', hideTip);
      }
    });
  });
  if (selected) { const i = ord.findIndex(t => t.id === selected); el('rect', { x: lab, y: lab + i * cell, width: cell * n, height: cell, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, rx: 3 }, svg); }
  const nn = document.getElementById('nn'); nn.replaceChildren();
  for (const t of sortedTanks) {
    const i = tanks.indexOf(t); let bj = -1; for (let j = 0; j < tanks.length; j++) if (j !== i && (bj < 0 || D[i][j] < D[i][bj])) bj = j;
    const li = document.createElement('li'); const b = document.createElement('b'); b.textContent = t.name; li.append(b, ` closest to ${tanks[bj].name}`); nn.append(li);
  }
}

// uplift dumbbells
function drawUplift() {
  const host = document.getElementById('uplift'); host.replaceChildren();
  const k = us.value, s = statBy[k];
  const rows = [...tanks].map(t => ({ t, a: t.base[k], b: t.ceiling[k] })).sort((p, q) => s.better * (q.b - p.b));
  const W = width('uplift'), lab = 90, rh = 24, H = rows.length * rh + 30, padR = 120;
  const vals = rows.flatMap(r => [r.a, r.b]); let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
  const X = v => lab + (v - lo) / (hi - lo) * (W - lab - padR);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Talent uplift for ${s.label}` }, host);
  for (const v of niceTicks(lo, hi)) { el('line', { x1: X(v), x2: X(v), y1: 0, y2: H - 22, stroke: 'var(--grid)' }, svg); txt(svg, X(v), H - 6, fmt('', v), { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' }); }
  rows.forEach((r, i) => {
    const y = i * rh + rh / 2;
    txt(svg, lab - 8, y + 4, r.t.name, { 'text-anchor': 'end', fill: selected === r.t.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': selected === r.t.id ? 600 : 400 });
    el('line', { x1: X(r.a), x2: X(r.b), y1: y, y2: y, stroke: 'var(--axis)', 'stroke-width': 2, 'stroke-linecap': 'round' }, svg);
    el('circle', { cx: X(r.a), cy: y, r: 3.5, fill: 'var(--surface)', stroke: 'var(--muted)', 'stroke-width': 1.5 }, svg);
    dot(svg, r.t, X(r.b), y, 5, () => [`${fmt(k, r.b)} ${s.unit}`.trim(), r.t.name, `base ${fmt(k, r.a)} → talents ${fmt(k, r.b)}`]);
    const pct = r.a ? (r.b - r.a) / Math.abs(r.a) * 100 : 0;
    txt(svg, Math.max(X(r.a), X(r.b)) + 10, y + 4, `${fmt(k, r.b)}${r.b !== r.a ? `  (${pct > 0 ? '+' : ''}${pct.toFixed(0)}%)` : ''}`, { fill: 'var(--ink-2)', 'font-family': 'var(--f-data)', 'font-size': 10.5 });
  });
}

// table
let sortKey = 'DPS', sortDir = -1;
function drawTable() {
  const tb = document.getElementById('table'); tb.replaceChildren();
  const head = document.createElement('tr');
  const cols = [{ key: 'name', label: 'Tank' }, { key: 'cls', label: 'Class' }, ...stats];
  for (const c of cols) { const th = document.createElement('th'); th.textContent = c.label + (sortKey === c.key ? (sortDir > 0 ? ' ▲' : ' ▼') : ''); th.onclick = () => { sortDir = sortKey === c.key ? -sortDir : -1; sortKey = c.key; drawTable(); }; th.scope = 'col'; head.append(th); }
  const thead = document.createElement('thead'); thead.append(head); tb.append(thead);
  const get = (t, k) => (k === 'name' || k === 'cls') ? t[k] : val(t, k);
  const body = document.createElement('tbody');
  for (const t of [...tanks].sort((a, b) => { const x = get(a, sortKey), y = get(b, sortKey); return (x > y ? 1 : x < y ? -1 : 0) * sortDir; })) {
    const tr = document.createElement('tr'); if (selected === t.id) tr.className = 'sel';
    for (const c of cols) { const td = document.createElement('td'); td.textContent = c.key === 'name' ? t.name + (t.wip ? ' *' : '') : c.key === 'cls' ? t.cls : fmt(c.key, val(t, c.key)); tr.append(td); }
    tr.onclick = () => select(selected === t.id ? null : t.id); body.append(tr);
  }
  tb.append(body);
}

const onDraw = [];
function drawAll() { drawStrips(); drawScatter(); drawMap(); drawHeat(); drawUplift(); drawTable(); for (const f of onDraw) f(); }
function select(id) {
  selected = id;
  for (const b of chips.children) b.setAttribute('aria-pressed', String(b.dataset.id === id));
  drawAll();
}
function setMode(m) { mode = m; document.getElementById('m-base').setAttribute('aria-pressed', String(m === 'base')); document.getElementById('m-core').setAttribute('aria-pressed', String(m === 'core')); drawStrips(); drawScatter(); drawTable(); for (const f of onDraw) f(); }
document.getElementById('m-base').onclick = () => setMode('base');
document.getElementById('m-core').onclick = () => setMode('core');
sx.onchange = sy.onchange = drawScatter; us.onchange = drawUplift;
let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(drawAll, 120); });
window.TA = { el, txt, fmt, dot, showTip, hideTip, niceTicks, width, labelPoints, axes, tanks, stats, statBy, col, CLS, sortedTanks,
  get selected() { return selected; }, get mode() { return mode; }, select, onDraw };
drawAll();
})();
