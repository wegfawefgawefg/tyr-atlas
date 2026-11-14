// Components and loadouts: scenario + assumptions, tank x component heatmap, loadout cloud, ridgeline, notable builds, best table.
(() => {
const TA = window.TA, L = window.TYR_LOAD, { el, txt, showTip, hideTip, niceTicks, width, tanks, CLS } = TA;
const SCENS = ['static', 'sniping', 'brawling', 'flanking'];
const CATS = ['Firepower', 'Durability', 'Mobility', 'Scouting', 'Ability'];
let scen = 'brawling';
const C = L.components, compIds = Object.keys(C);
const cname = id => C[id].name;
// descriptions carry the game's placeholders; the export has no level values, so show N
const cdesc = id => C[id].desc.replace(/<bold>(.*?)<\/>/g, '$1').replace(/\{LevelValuePercent[A-Za-z]*\}/g, 'N%').replace(/\{LevelValue[A-Za-z]*\}/g, 'N').replace(/\s+/g, ' ').trim();
const LT = t => L.tanks[t.name];
const pct = (g, d = 1) => `${g >= 0 ? '+' : '−'}${Math.abs(g * 100).toFixed(d)}%`;
const n0 = v => Math.round(v).toLocaleString('en-US'), n1 = v => (+v).toFixed(1);
const gainOf = (t, id, sc = scen) => { const S = LT(t).single[sc]; return S[id].duel / S._base.duel - 1; };
const cur = () => tanks.find(x => x.id === TA.selected) || TA.sortedTanks[0];
const median = a => { const s = [...a].sort((x, y) => x - y), n = s.length; return (s[n >> 1] + s[(n - 1) >> 1]) / 2; };
const tankByName = Object.fromEntries(tanks.map(t => [t.name, t]));
const SEQ = i => `var(--seq-${Math.max(0, Math.min(7, i))})`;
const pathOf = pts => pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
const hover = (node, rows) => { node.addEventListener('pointermove', ev => showTip(ev, rows())); node.addEventListener('pointerleave', hideTip); };
const span = (host, text, cls) => { const s = document.createElement('span'); if (cls) s.className = cls; s.textContent = text; host.append(s); return s; };
function keySvg(kind, color, extra = {}) {
  const k = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); k.setAttribute('width', 16); k.setAttribute('height', 12); k.style.width = '16px';
  if (kind === 'sq') el('rect', { x: 1, y: 1, width: 14, height: 10, rx: 2, fill: color, ...extra }, k);
  else if (kind === 'line') el('line', { x1: 1, x2: 15, y1: 6, y2: 6, stroke: color, 'stroke-width': 1.5, ...extra }, k);
  else el('circle', { cx: 8, cy: 6, r: 4, fill: color, ...extra }, k);
  return k;
}
function legendItems(host, items) {
  host.replaceChildren();
  for (const [k, label] of items) { const s = document.createElement('span'); s.append(k, label); host.append(s); }
}
function rampKey(lo, hi) {
  const k = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); k.setAttribute('width', 96); k.setAttribute('height', 12); k.style.width = '96px';
  for (let i = 0; i < 8; i++) el('rect', { x: i * 12, y: 1, width: 11, height: 10, fill: SEQ(i) }, k);
  const s = document.createElement('span'); s.append(lo + ' ', k, ' ' + hi); return s;
}

// ---------- 4. scenario selector + assumptions ----------
// the components page and the tank page each have a scenario picker; they share one value
const segs = ['scen', 't-scen'].map(id => document.getElementById(id)).filter(Boolean);
for (const seg of segs) for (const s of SCENS) {
  const b = document.createElement('button'); b.textContent = L.scenarios[s].label; b.dataset.s = s;
  b.onclick = () => { scen = s; TA.redraw(); }; seg.append(b);
}
const syncSegs = () => { for (const seg of segs) for (const b of seg.children) b.setAttribute('aria-pressed', String(b.dataset.s === scen)); };
function drawScenario() {
  syncSegs();
  const sc = L.scenarios[scen], r = L.ref;
  document.getElementById('scen-desc').textContent = `${sc.label}: ${sc.desc}` + (sc.flags.length ? ` Triggers that count: ${sc.flags.map(f => f.replace(/_/g, ' ')).join(', ')}.` : '');
  const dl = document.getElementById('assume'); dl.replaceChildren();
  const rows = [
    ['Fight length', `${r.fight_s} s`], ['Opponent', 'median tank'], ['Enemy damage per second', `${n1(r.enemy_dps)} dmg/s`],
    ['Enemy damage per shell', `${n1(r.enemy_alpha)} dmg`], ['Enemy shots that bounce off you', `${r.incoming_bounce * 100}%`],
    ['Enemy hits that damage your modules', `${r.incoming_module * 100}%`], ['Your shots that penetrate', `${r.our_pen * 100}%`],
    ['Your hits that damage enemy modules', `${r.our_module * 100}%`], ['Shots that are alt shells', `${r.alt_share * 100}%`],
    ['Talent build', '31-point core'], ['Loadouts per tank', '12,341'],
  ];
  for (const [k, v] of rows) { const d = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = k; dd.textContent = v; d.append(dt, dd); dl.append(d); }
}

// ---------- 5. tank x component heatmap ----------
function drawCheat() {
  const host = document.getElementById('cheat'); host.replaceChildren();
  const rowsT = TA.sortedTanks, G = new Map();
  for (const t of rowsT) for (const id of compIds) G.set(t.name + '|' + id, gainOf(t, id));
  const med = Object.fromEntries(compIds.map(id => [id, median(rowsT.map(t => G.get(t.name + '|' + id)))]));
  const mx = Math.max(...G.values(), 1e-9);
  const out = new Set(L.outliers.filter(o => o.scen === scen).map(o => o.tank + '|' + o.comp));
  const cols = []; for (const c of CATS) cols.push(...compIds.filter(id => C[id].cats[0] === c).sort((a, b) => med[b] - med[a] || cname(a).localeCompare(cname(b))).map(id => ({ id, c })));
  const lab = 78, topH = 136, gapC = 8, W = Math.max(860, width('cheat'));
  const cell = Math.max(15, Math.min(22, (W - lab - 60 - gapC * (CATS.length - 1)) / cols.length));
  const xs = []; let x = lab; cols.forEach((col, j) => { if (j && col.c !== cols[j - 1].c) x += gapC; xs.push(x); x += cell; });
  const Wsvg = x + 60, H = topH + rowsT.length * cell + 4;
  const svg = el('svg', { viewBox: `0 0 ${Wsvg} ${H}`, role: 'img', 'aria-label': `Duel gain of each component on each tank, ${L.scenarios[scen].label}` }, host);
  for (const c of CATS) {
    const js = cols.map((k, j) => j).filter(j => cols[j].c === c); if (!js.length) continue;
    const a = xs[js[0]], b = xs[js.at(-1)] + cell;
    txt(svg, a + 1, 11, c.toUpperCase(), { 'font-size': 10.5, 'font-weight': 600, fill: 'var(--muted)', 'letter-spacing': '.05em' });
    el('line', { x1: a + 1, x2: b - 1, y1: 17, y2: 17, stroke: 'var(--axis)' }, svg);
  }
  cols.forEach((col, j) => txt(svg, 0, 0, cname(col.id), { transform: `translate(${xs[j] + cell / 2 + 3},${topH - 5}) rotate(-60)`, 'font-size': 10.5 }));
  const bin = g => g <= 1e-6 ? -1 : Math.min(7, Math.floor(Math.sqrt(g / mx) * 8));
  rowsT.forEach((t, i) => {
    const y = topH + i * cell, sel = TA.selected === t.id;
    const lt = txt(svg, lab - 6, y + cell / 2 + 4, t.name, { 'text-anchor': 'end', fill: sel ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': sel ? 600 : 400 });
    lt.style.cursor = 'pointer'; lt.addEventListener('click', () => TA.select(sel ? null : t.id));
    cols.forEach((col, j) => {
      const g = G.get(t.name + '|' + col.id), b = bin(g);
      const r = el('rect', { x: xs[j] + 1, y: y + 1, width: cell - 2, height: cell - 2, rx: 2, fill: b < 0 ? 'var(--page)' : SEQ(b), stroke: b < 0 ? 'var(--grid)' : 'none' }, svg);
      if (out.has(t.name + '|' + col.id)) el('rect', { x: xs[j] + 1.5, y: y + 1.5, width: cell - 3, height: cell - 3, rx: 2, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.6, 'pointer-events': 'none' }, svg);
      hover(r, () => [g > 1e-6 ? pct(g) : 'no effect', `${cname(col.id)} on ${t.name}`, `Median across tanks ${pct(med[col.id])}${out.has(t.name + '|' + col.id) ? ' · outlier' : ''}`, cdesc(col.id)]);
    });
    if (sel) el('rect', { x: lab - 2, y, width: x - lab + 4, height: cell, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, rx: 3 }, svg);
  });
  const ring = keySvg('sq', 'none', { stroke: 'var(--ink)', 'stroke-width': 1.6 });
  const leg = document.getElementById('cheat-legend'); leg.replaceChildren();
  const s0 = document.createElement('span'); s0.append(keySvg('sq', 'var(--page)', { stroke: 'var(--grid)' }), 'No effect'); leg.append(s0);
  leg.append(rampKey('0%', pct(mx, 0)));
  const s2 = document.createElement('span'); s2.append(ring, 'Outlier'); leg.append(s2);
  span(leg, 'Colour steps are square-root spaced', 'note');
}

// ---------- 6. loadout cloud ----------
const ct = document.getElementById('cloud-t');
for (const t of TA.sortedTanks) { const o = document.createElement('option'); o.value = t.id; o.textContent = t.name; ct.append(o); }
ct.onchange = () => TA.select(ct.value);
legendItems(document.getElementById('cloud-legend'), [
  [rampKey('few', 'many'), 'loadouts'],
  [keySvg('dot', 'var(--ink)', { stroke: 'var(--surface)', 'stroke-width': 1.5 }), 'Front on damage and health'],
  [keySvg('dot', 'var(--surface)', { stroke: 'var(--ink)', 'stroke-width': 1.5 }), 'On the front only through speed'],
  [keySvg('dot', 'none', { stroke: 'var(--muted)', 'stroke-width': 1.5, r: 3.5 }), 'No components'],
]);
// hostId/noteId/selId let the tank page draw the same chart into its own container; selId may be null
function drawCloud(hostId = 'cloud', noteId = 'cloud-note', selId = 'cloud-t') {
  const host = document.getElementById(hostId); host.replaceChildren();
  const t = cur(); if (selId) document.getElementById(selId).value = t.id;
  const D = LT(t), g = D.grid[scen], F = D.fronts[scen], best = D.best[scen], base = D.single[scen]._base;
  const W = width(hostId), H = Math.min(520, Math.max(320, W * 0.58)), m = { l: 54, r: 22, t: 28, b: 46 };
  const padx = (g.x[1] - g.x[0]) * 0.04 || 1, pady = (g.y[1] - g.y[0]) * 0.04 || 10;
  const x0 = g.x[0] - padx, x1 = g.x[1] + padx, y0 = g.y[0] - pady, y1 = g.y[1] + pady;
  const X = v => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r), Y = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `All loadouts for ${t.name} by damage and health` }, host);
  TA.axes(svg, X, Y, niceTicks(x0, x1, W < 560 ? 4 : 6), niceTicks(y0, y1), m, W, H, 'Effective damage per second →', '↑ Effective health');
  const nb = g.counts.length, dx = (g.x[1] - g.x[0]) / nb, dy = (g.y[1] - g.y[0]) / g.counts[0].length;
  const cmax = Math.max(...g.counts.flat());
  g.counts.forEach((colc, i) => colc.forEach((c, j) => {
    if (!c) return;
    const a = g.x[0] + i * dx, b = g.y[0] + j * dy;
    const r = el('rect', { x: X(a), y: Y(b + dy), width: Math.max(1, X(a + dx) - X(a)) + 0.4, height: Math.max(1, Y(b) - Y(b + dy)) + 0.4, fill: SEQ(1 + Math.min(6, Math.floor(Math.log(c) / Math.log(cmax + 1) * 7))) }, svg);
    hover(r, () => [`${c.toLocaleString('en-US')} loadout${c > 1 ? 's' : ''}`, `DPS ${n1(a)} to ${n1(a + dx)}`, `Health ${n0(b)} to ${n0(b + dy)}`]);
  }));
  // equal duel score through the best loadout: dps * ehp = const
  const iso = []; for (let k = 0; k <= 80; k++) { const d = x0 + (x1 - x0) * k / 80, e = best.duel / d; if (e >= y0 && e <= y1) iso.push([X(d), Y(e)]); }
  if (iso.length > 1) el('path', { d: pathOf(iso), fill: 'none', stroke: 'var(--muted)', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, svg);
  // 2D front (damage and health only) inside the 3D front
  const on2 = F.filter(a => !F.some(b => b !== a && b.dps >= a.dps && b.ehp >= a.ehp && (b.dps > a.dps || b.ehp > a.ehp)));
  const fs = [...on2].sort((a, b) => a.dps - b.dps);
  if (fs.length) {
    const pts = [[X(x0), Y(fs[0].ehp)]];
    fs.forEach((p, i) => { pts.push([X(p.dps), Y(p.ehp)]); if (i + 1 < fs.length) pts.push([X(p.dps), Y(fs[i + 1].ehp)]); });
    pts.push([X(fs.at(-1).dps), Y(y0)]);
    el('path', { d: pathOf(pts), fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5, 'stroke-linejoin': 'round', 'stroke-opacity': 0.8 }, svg);
  }
  el('circle', { cx: X(base.dps), cy: Y(base.ehp), r: 5, fill: 'none', stroke: 'var(--muted)', 'stroke-width': 1.5 }, svg);
  const set2 = new Set(on2);
  const rows = p => [`${pct(p.duel / base.duel - 1)} duel score`, p.comps.map(cname).join(' + '), `DPS ${n1(p.dps)} · health ${n0(p.ehp)} · speed ${n1(p.speed)} kph`];
  for (const p of F) {
    const gg = el('g', {}, svg);
    el('circle', { cx: X(p.dps), cy: Y(p.ehp), r: 11, fill: 'transparent' }, gg);
    el('circle', { cx: X(p.dps), cy: Y(p.ehp), r: 4, fill: set2.has(p) ? 'var(--ink)' : 'var(--surface)', stroke: set2.has(p) ? 'var(--surface)' : 'var(--ink)', 'stroke-width': 1.5 }, gg);
    hover(gg, () => rows(p));
  }
  const bx = X(best.dps), by = Y(best.ehp);
  el('circle', { cx: bx, cy: by, r: 7.5, fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.5 }, svg);
  const right = bx > W * 0.6;
  const halo = { stroke: 'var(--surface)', 'stroke-width': 3, 'paint-order': 'stroke', 'stroke-linejoin': 'round' };
  txt(svg, right ? bx - 11 : bx + 11, by - 9, `best ${pct(best.gain, 0)}`, { 'text-anchor': right ? 'end' : 'start', fill: 'var(--ink)', 'font-size': 11.5, 'font-weight': 600, ...halo });
  txt(svg, X(base.dps) + 8, Y(base.ehp) - 8, 'no components', { fill: 'var(--ink-2)', 'font-size': 10.5, ...halo });
  document.getElementById(noteId).textContent = `${t.name}, ${L.scenarios[scen].label.toLowerCase()}. Best duel score: ${best.comps.map(cname).join(' + ')}, ${pct(best.gain)} over no components (DPS ${n1(best.dps)}, health ${n0(best.ehp)}). ${F.length} loadouts on the full front, ${on2.length} of them on the damage and health line.${TA.selected ? '' : ' Pick a tank in the header or in the menu to change it.'}`;
}

// ---------- 7. ridgeline of duel gain per tank ----------
function drawRidge() {
  const host = document.getElementById('ridge'); host.replaceChildren();
  const rows = tanks.map(t => ({ t, h: LT(t).hist[scen], best: LT(t).best[scen] })).sort((a, b) => b.h.max - a.h.max);
  const W = width('ridge'), lab = 74, padR = 64, step = 24, peak = 40, top = peak - step + 8;
  const gmax = Math.max(...rows.map(r => r.h.hi)) || 1;
  const X = v => lab + v / gmax * (W - lab - padR);
  const H = top + rows.length * step + 30;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Spread of loadout duel gain per tank, ${L.scenarios[scen].label}` }, host);
  for (const v of niceTicks(0, gmax, W < 560 ? 4 : 6)) {
    el('line', { x1: X(v), x2: X(v), y1: top - 10, y2: top + rows.length * step, stroke: 'var(--grid)' }, svg);
    txt(svg, X(v), H - 12, pct(v, 0), { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10, 'font-family': 'var(--f-data)' });
  }
  txt(svg, W - padR, H, 'duel gain over no components →', { 'text-anchor': 'end', fill: 'var(--ink-2)', 'font-size': 11.5 });
  rows.forEach((r, i) => {
    const yb = top + (i + 1) * step, h = r.h, n = h.counts.length, w = (h.hi - h.lo) / n, cm = Math.sqrt(Math.max(...h.counts)) || 1;
    const pts = [[X(h.lo), yb]];
    h.counts.forEach((c, k) => pts.push([X(h.lo + (k + 0.5) * w), yb - Math.sqrt(c) / cm * peak]));
    pts.push([X(h.hi), yb]);
    const d = pathOf(pts) + ' Z', colr = `var(${CLS[r.t.cls]})`, sel = TA.selected === r.t.id;
    el('path', { d, fill: 'var(--surface)' }, svg);
    el('path', { d, fill: colr, 'fill-opacity': 0.28, stroke: colr, 'stroke-width': sel ? 2 : 1.2, 'stroke-linejoin': 'round' }, svg);
    el('line', { x1: lab, x2: W - padR, y1: yb, y2: yb, stroke: 'var(--axis)', 'stroke-width': 0.8 }, svg);
    el('line', { x1: X(h.p50), x2: X(h.p50), y1: yb - 9, y2: yb + 2, stroke: 'var(--ink)', 'stroke-width': 2 }, svg);
    el('line', { x1: X(h.p90), x2: X(h.p90), y1: yb - 9, y2: yb + 2, stroke: 'var(--ink-2)', 'stroke-width': 1.2, 'stroke-dasharray': '2 1.5' }, svg);
    const lt = txt(svg, lab - 6, yb - 2, r.t.name, { 'text-anchor': 'end', fill: sel ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': sel ? 600 : 400 });
    txt(svg, W - padR + 6, yb - 2, pct(h.max, 0), { fill: 'var(--ink-2)', 'font-size': 10.5, 'font-family': 'var(--f-data)' });
    const hit = el('rect', { x: 0, y: yb - step, width: W, height: step, fill: 'transparent' }, svg);
    hit.style.cursor = 'pointer';
    hit.addEventListener('click', () => TA.select(sel ? null : r.t.id));
    hover(hit, () => [`best ${pct(h.max)}`, r.t.name, `median loadout ${pct(h.p50)} · 90th percentile ${pct(h.p90)}`, `Best: ${r.best.comps.map(cname).join(' + ')}`]);
    lt.style.pointerEvents = 'none';
  });
  // tick legend
  const ly = 10;
  el('line', { x1: lab, x2: lab, y1: ly - 8, y2: ly + 2, stroke: 'var(--ink)', 'stroke-width': 2 }, svg);
  txt(svg, lab + 6, ly + 1, 'median loadout', { 'font-size': 10.5 });
  el('line', { x1: lab + 104, x2: lab + 104, y1: ly - 8, y2: ly + 2, stroke: 'var(--ink-2)', 'stroke-width': 1.2, 'stroke-dasharray': '2 1.5' }, svg);
  txt(svg, lab + 110, ly + 1, '90th percentile', { 'font-size': 10.5 });
  txt(svg, W - padR + 6, ly + 1, 'best', { fill: 'var(--muted)', 'font-size': 10.5 });
}

// ---------- 8. notable builds ----------
const SCEN_PREF = { brawling: 3, sniping: 2, flanking: 1, static: 0 };
const ordinal = k => (k === 1 ? '' : k === 2 ? '2nd-' : '3rd-');
const METRICS = [['alpha', 'shell damage', v => n0(v)], ['dps', 'damage per second', n1], ['ehp', 'effective health', n0], ['speed', 'speed', v => n1(v) + ' kph']];
function card(host, t, title, scenLabel, big, sub, sentences) {
  const c = document.createElement('article'); c.className = 'card'; c.tabIndex = 0;
  const h = document.createElement('h3'); h.textContent = title;
  const k = document.createElement('div'); k.className = 'k'; k.textContent = `${t.name} · ${t.cls} · ${scenLabel}`;
  const b = document.createElement('div'); b.className = 'big'; b.textContent = big;
  const sb = document.createElement('div'); sb.className = 'k'; sb.textContent = sub;
  const p = document.createElement('p'); p.textContent = sentences.join(' ');
  c.append(h, k, b, sb, p);
  const go = () => TA.select(TA.selected === t.id ? null : t.id);
  c.addEventListener('click', go); c.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } });
  if (TA.selected === t.id) c.style.borderColor = 'var(--ink)';
  host.append(c);
}
function pickPerTank(list, keyOf, better, perTank = 2, n = 8) {
  const byKey = new Map();
  for (const e of list) { const k = keyOf(e), o = byKey.get(k); if (!o || better(e, o)) byKey.set(k, e); }
  const out = [], seen = {};
  for (const e of [...byKey.values()].sort((a, b) => b._score - a._score)) { if ((seen[e.tank] = (seen[e.tank] || 0) + 1) <= perTank) out.push(e); if (out.length >= n) break; }
  return out;
}
function drawCards() {
  const hs = document.getElementById('cards-syn'), ho = document.getElementById('cards-out'); hs.replaceChildren(); ho.replaceChildren();
  const syn = pickPerTank(L.synergy_top.map(s => ({ ...s, _score: s.syn })), s => s.tank + '|' + [s.a, s.b].sort().join('+'),
    (e, o) => SCEN_PREF[e.scen] > SCEN_PREF[o.scen] || (e.scen === o.scen && e.syn > o.syn));
  for (const s of syn) {
    const t = tankByName[s.tank], S = L.tanks[s.tank].single[s.scen], b0 = S._base;
    const ga = S[s.a].duel / b0.duel - 1, gb = S[s.b].duel / b0.duel - 1, stacked = (1 + ga) * (1 + gb) - 1;
    const adds = g => g > 5e-4 ? `adds ${pct(g)}` : 'adds nothing';
    const sent = [`Apart, ${cname(s.a)} ${adds(ga)} and ${cname(s.b)} ${adds(gb)}; simply stacked that would be ${pct(stacked)}, but together they add ${pct(s.gain)}.`];
    const [u, v] = S[s.a].uses > b0.uses ? [s.a, s.b] : S[s.b].uses > b0.uses ? [s.b, s.a] : [null, null];
    if (u) sent.push(`${cname(u)} raises ability uses per fight from ${n1(b0.uses)} to ${n1(S[u].uses)}${/abilit/i.test(C[v].desc) ? `, and ${cname(v)} pays out on each use` : ''}.`);
    card(hs, t, `${cname(s.a)} + ${cname(s.b)}`, L.scenarios[s.scen].label, pct(s.gain), `duel gain together, vs ${pct(stacked)} stacked`, sent);
  }
  const outs = pickPerTank(L.outliers.map(o => ({ ...o, _score: o.gain - o.median })), o => o.tank + '|' + o.comp,
    (e, o) => e.gain - e.median > o.gain - o.median || (e.gain - e.median === o.gain - o.median && SCEN_PREF[e.scen] > SCEN_PREF[o.scen]));
  for (const o of outs) {
    const t = tankByName[o.tank], S = L.tanks[o.tank].single[o.scen], b0 = S._base, s1 = S[o.comp];
    // which metric the component moves most on this tank
    const [mk, mlabel, mf] = METRICS.map(mm => [...mm, (s1[mm[0]] - b0[mm[0]]) / (b0[mm[0]] || 1)]).sort((a, b) => b[3] - a[3])[0];
    const delta = s1[mk] - b0[mk];
    const sent = [`${cname(o.comp)} raises ${o.tank}'s ${mlabel} from ${mf(b0[mk])} to ${mf(s1[mk])} in ${L.scenarios[o.scen].label.toLowerCase()}; that is worth ${pct(o.gain)} duel score here against ${pct(o.median)} on the median tank.`];
    // is the bonus flat across tanks? then a low base value explains the outlier
    const ds_ = tanks.map(u => { const U = LT(u).single[o.scen]; return { u, d: U[o.comp][mk] - U._base[mk], b: U._base[mk] }; }).filter(x => x.d > 1e-6);
    const flat = ds_.length > 3 && Math.max(...ds_.map(x => x.d)) / Math.min(...ds_.map(x => x.d)) < 1.05;
    if (flat) {
      const rank = [...ds_].sort((a, b) => a.b - b.b).findIndex(x => x.u === t) + 1;
      if (rank && rank <= 3) sent.push(`The bonus is a flat ${mk === 'speed' ? n1(delta) : n0(delta)} on every tank it works on, and ${o.tank} starts with the ${ordinal(rank)}lowest ${mlabel} of those, so it is a bigger share.`);
    }
    card(ho, t, `${cname(o.comp)} on ${o.tank}`, L.scenarios[o.scen].label, pct(o.gain), `duel gain, vs ${pct(o.median)} on the median tank`, sent);
  }
}

// ---------- 9. best loadout per tank ----------
function drawBest() {
  const tb = document.getElementById('best'); tb.replaceChildren();
  document.getElementById('best-note').textContent = `${L.scenarios[scen].label}: the loadout with the highest duel score for each tank, best first. Damage per second already counts only penetrating shots (${L.ref.our_pen * 100}%). Click a row to select the tank.`;
  const head = document.createElement('tr');
  for (const h of ['Tank', 'Components', 'Gain', 'DPS', 'Health', 'Speed']) { const th = document.createElement('th'); th.textContent = h; th.scope = 'col'; th.style.cursor = 'default'; if (h === 'Components') th.style.textAlign = 'left'; head.append(th); }
  const thead = document.createElement('thead'); thead.append(head); tb.append(thead);
  const body = document.createElement('tbody');
  for (const t of [...tanks].sort((a, b) => LT(b).best[scen].gain - LT(a).best[scen].gain)) {
    const b = LT(t).best[scen], tr = document.createElement('tr'); if (TA.selected === t.id) tr.className = 'sel';
    const cells = [t.name + (t.wip ? ' *' : ''), b.comps.map(cname).join(' + '), pct(b.gain), n1(b.dps), n0(b.ehp), n1(b.speed)];
    cells.forEach((v, i) => { const td = document.createElement('td'); td.textContent = v; if (i === 1) td.className = 'comps'; tr.append(td); });
    tr.style.cursor = 'pointer'; tr.onclick = () => TA.select(TA.selected === t.id ? null : t.id); body.append(tr);
  }
  tb.append(body);
}

// tank page: the selected tank's best loadout in every scenario
function drawTankBest(hostId) {
  const tb = document.getElementById(hostId); tb.replaceChildren();
  const t = cur(), head = document.createElement('tr');
  for (const h of ['Scenario', 'Components', 'Gain', 'DPS', 'Health', 'Speed']) { const th = document.createElement('th'); th.textContent = h; th.scope = 'col'; th.style.cursor = 'default'; if (h === 'Components') th.style.textAlign = 'left'; head.append(th); }
  const thead = document.createElement('thead'); thead.append(head); tb.append(thead);
  const body = document.createElement('tbody');
  for (const sc of SCENS) {
    const b = LT(t).best[sc], tr = document.createElement('tr'); if (sc === scen) tr.className = 'sel';
    const cells = [L.scenarios[sc].label, b.comps.map(cname).join(' + '), pct(b.gain), n1(b.dps), n0(b.ehp), n1(b.speed)];
    cells.forEach((v, i) => { const td = document.createElement('td'); td.textContent = v; if (i === 1) td.className = 'comps'; tr.append(td); });
    tr.style.cursor = 'pointer'; tr.onclick = () => { scen = sc; TA.redraw(); }; body.append(tr);
  }
  tb.append(body);
}

function drawBuild() { drawScenario(); drawCheat(); drawCloud(); drawRidge(); drawCards(); drawBest(); }
TA.chart('components', drawBuild);
TA.chart('tank', () => { if (!TA.selected) return; syncSegs(); drawCloud('t-cloud', 't-cloud-note', null); drawTankBest('t-best'); });
// this file loads after the router's first draw, so draw now if its page is already showing
if (['components', 'tank'].includes(TA.page)) TA.redraw();
})();
