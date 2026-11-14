// Combat charts: shots to kill + breakpoints, aimed weak spots, hull-down, ammo, turret yaw, tread radar, ram, size vs camo.
// Data: window.TYR_COMBAT (tools/combat.py). Containers are looked up by id; missing containers are skipped.
(() => {
const TA = window.TA, C = window.TYR_COMBAT;
if (!TA || !C) return;
const { el, txt, tanks, sortedTanks, showTip, hideTip } = TA;
const $ = id => document.getElementById(id);
const W = id => TA.width(id);
const byName = Object.fromEntries(tanks.map(t => [t.name, t]));
const pick = () => tanks.find(t => t.id === TA.selected) || byName.Atlas || tanks[0];  // default target/attacker when no tank is picked
const clsVar = t => `var(${TA.CLS[t.cls]})`;
const seq = k => `var(--seq-${Math.max(0, Math.min(7, k))})`;
const pct = x => `${Math.round(x * 100)}%`;
let stkMode = 'hits', aimPen = 70;

function segButtons(hostId, opts, get, set) {
  const host = $(hostId); if (!host || host.childElementCount) return;
  for (const [k, l] of opts) {
    const b = document.createElement('button'); b.textContent = l; b.setAttribute('aria-pressed', String(get() === k));
    b.onclick = () => { set(k); for (const x of host.children) x.setAttribute('aria-pressed', String(x === b)); drawCombat(); };
    host.append(b);
  }
}

// 1. shots to kill matrix
function drawStk() {
  const host = $('stk'); if (!host) return; host.replaceChildren();
  segButtons('stk-mode', [['hits', 'Damaging hits needed'], ['even', 'Shots fired, hits spread evenly'], ['aimed', 'Shots fired, aimed (0.5 m spread)']], () => stkMode, v => { stkMode = v; });
  const names = sortedTanks.map(t => t.name), n = names.length;
  const lab = 76, cell = Math.max(24, Math.min(34, (Math.max(600, W('stk')) - lab - 10) / n));
  const svg = el('svg', { viewBox: `0 0 ${lab + cell * n + 10} ${lab + cell * n + 10}`, role: 'img', 'aria-label': 'Shots to kill matrix' }, host);
  const vals = names.flatMap(a => names.filter(b => b !== a).map(b => C.stk[a][b][stkMode === 'hits' ? 'stk' : stkMode]));
  const lo = Math.min(...vals), hi = Math.min(Math.max(...vals), 60);
  names.forEach((a, r) => {
    const sel = TA.selected === byName[a].id;
    txt(svg, lab - 6, lab + r * cell + cell / 2 + 4, a, { 'text-anchor': 'end', fill: sel ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': sel ? 600 : 400 });
    txt(svg, 0, 0, a, { transform: `translate(${lab + r * cell + cell / 2 + 4},${lab - 6}) rotate(-60)`, fill: 'var(--ink-2)' });
    names.forEach((b, c) => {
      const x = lab + c * cell, y = lab + r * cell;
      if (a === b) { el('rect', { x: x + 1, y: y + 1, width: cell - 2, height: cell - 2, rx: 2, fill: 'var(--grid)' }, svg); return; }
      const s = C.stk[a][b], v = stkMode === 'hits' ? s.stk : s[stkMode];
      const k = Math.round(Math.log(Math.min(v, hi) / lo) / Math.log(hi / lo) * 7);
      el('rect', { x: x + 1, y: y + 1, width: cell - 2, height: cell - 2, rx: 2, fill: seq(k) }, svg);
      const t = txt(svg, x + cell / 2, y + cell / 2 + 4, v >= 100 ? '99+' : stkMode === 'hits' ? String(v) : v.toFixed(v < 10 ? 1 : 0),
        { 'text-anchor': 'middle', 'font-size': cell < 30 ? 9.5 : 10.5, 'font-family': 'var(--f-data)', fill: k >= 5 ? '#fff' : 'var(--ink)' });
      const hit = el('rect', { x, y, width: cell, height: cell, fill: 'transparent' }, svg);
      hit.addEventListener('pointermove', ev => showTip(ev, [`${s.stk} damaging hits`, `${a} shooting ${b} from the front`,
        `${pct(s.dc_even)} of evenly spread hits do damage, ${pct(s.dc_aim)} aimed`, `about ${s.even} shots fired spread, ${s.aimed} aimed`,
        s.next_alpha ? `one shot fewer at ${s.next_alpha} damage${s.levers.length ? ': ' + s.levers.join(', ') : ' (no single lever gets there)'}` : 'already one shot']));
      hit.addEventListener('pointerleave', hideTip);
      void t;
    });
  });
}

// 2. breakpoints for the picked tank
function drawBreak() {
  const host = $('breaks'); if (!host) return; host.replaceChildren();
  const t = pick(), me = t.name;
  $('breaks-title') && ($('breaks-title').textContent = `${me}: where one change saves or costs a shot`);
  const mk = (title, rows) => {
    const box = document.createElement('div'); box.className = 'bk';
    const h = document.createElement('h4'); h.textContent = title; box.append(h);
    if (!rows.length) { const p = document.createElement('p'); p.className = 'note'; p.textContent = 'None in this roster.'; box.append(p); }
    const ul = document.createElement('ul');
    for (const [who, text] of rows) { const li = document.createElement('li'); const b = document.createElement('b'); b.textContent = who; li.append(b, ` ${text}`); ul.append(li); }
    box.append(ul); return box;
  };
  const att = Object.entries(C.stk[me]).filter(([, s]) => s.levers.length).map(([b, s]) => [b, `${s.stk} → ${s.stk - 1} hits with ${s.levers.join(' or ')}`]);
  const def = Object.entries(C.stk).filter(([a]) => a !== me).map(([a, row]) => [a, row[me]]).filter(([, s]) => s.def_levers.length)
    .map(([a, s]) => [a, `needs ${s.stk + 1} hits instead of ${s.stk} if you run ${s.def_levers.join(' or ')}`]);
  const grid = document.createElement('div'); grid.className = 'bkgrid';
  grid.append(mk(`${me} attacking`, att), mk(`${me} defending`, def));
  host.append(grid);
}

// 3. aimed weak spots: damage chance vs spread for the picked tank as target
function drawAim() {
  const host = $('aim'); if (!host) return; host.replaceChildren();
  segButtons('aim-pen', C.aim_pens.map(p => [p, `${p} mm`]), () => aimPen, v => { aimPen = v; });
  const t = pick(), a = C.tanks[t.name].aim, pi = C.aim_pens.indexOf(aimPen);
  $('aim-title') && ($('aim-title').textContent = `${t.name} as the target, ${aimPen} mm gun`);
  const w = W('aim'), h = 280, m = { l: 46, r: 120, t: 14, b: 40 };
  const sig = C.sigmas, X = i => m.l + i / (sig.length - 1) * (w - m.l - m.r), Y = v => m.t + (1 - v) * (h - m.t - m.b);
  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': 'Aimed damage chance by spread' }, host);
  for (const v of [0, 0.25, 0.5, 0.75, 1]) { el('line', { x1: m.l, x2: w - m.r, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }, svg); txt(svg, m.l - 6, Y(v) + 4, pct(v), { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10 }); }
  sig.forEach((s, i) => txt(svg, X(i), h - m.b + 16, `${s} m`, { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10 }));
  txt(svg, w - m.r, h - 6, 'spread around the aim point (1σ) →', { 'text-anchor': 'end', fill: 'var(--ink-2)', 'font-size': 11 });
  const views = [['front', 'Front', 'var(--c-light)'], ['front30', 'Front, 30° angle', 'var(--c-medium)'], ['left', 'Side', 'var(--c-heavy)'], ['rear', 'Rear', 'var(--muted)']];
  const ends = [];
  for (const [k, label, col] of views) {
    if (!a[k]) continue;
    const ys = a[k][pi];
    el('path', { d: ys.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' '), fill: 'none', stroke: col, 'stroke-width': 2, 'stroke-linejoin': 'round' }, svg);
    ys.forEach((v, i) => { const c = el('circle', { cx: X(i), cy: Y(v), r: 4, fill: col, stroke: 'var(--surface)', 'stroke-width': 2 }, svg);
      c.addEventListener('pointermove', ev => showTip(ev, [pct(v), `${label}, ${sig[i]} m spread`, 'best aim point on the silhouette'])); c.addEventListener('pointerleave', hideTip); });
    ends.push([Y(ys[ys.length - 1]), label]);
  }
  ends.sort((p, q) => p[0] - q[0]); let last = -99;
  for (const [y, label] of ends) { const yy = Math.max(y + 4, last + 13); txt(svg, w - m.r + 8, yy, label, { fill: 'var(--ink-2)', 'font-size': 11 }); last = yy; }
}

// 4. hull-down ranking
function drawHull() {
  const host = $('hull'); if (!host) return; host.replaceChildren();
  const pi = C.aim_pens.indexOf(aimPen);
  const rows = sortedTanks.map(t => ({ t, h: C.tanks[t.name].hulldown })).sort((p, q) => p.h.dchance[aimPen] - q.h.dchance[aimPen]);
  const w = W('hull'), lab = 84, rh = 22, h = rows.length * rh + 26, x0 = lab, x1 = w - 260;
  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': 'Hull-down armor ranking' }, host);
  rows.forEach(({ t, h: d }, i) => {
    const y = i * rh + 4, v = d.dchance[aimPen], bw = v * (x1 - x0);
    txt(svg, lab - 8, y + 14, t.name, { 'text-anchor': 'end', fill: TA.selected === t.id ? 'var(--ink)' : 'var(--ink-2)', 'font-weight': TA.selected === t.id ? 600 : 400 });
    el('rect', { x: x0, y: y + 4, width: Math.max(2, bw), height: 13, rx: 2, fill: clsVar(t) }, svg);
    txt(svg, x0 + bw + 6, y + 14, `${pct(v)} damage · ${d.exposed_m2} m² showing · ${d.depression_deg}° depression`, { fill: 'var(--ink-2)', 'font-size': 10.5, 'font-family': 'var(--f-data)' });
  });
  void pi;
}

// 5. ammo vs fronts for the picked attacker
function drawAmmo() {
  const host = $('ammo'); if (!host) return; host.replaceChildren();
  const me = pick().name, M = C.ammo_vs_front[me];
  $('ammo-title') && ($('ammo-title').textContent = `${me}'s gun: expected damage per shot fired at each tank's front`);
  const ammos = Object.keys(M).filter(k => C.ammo[k].selectable || k === 'Standard' || k === 'ArmorPiercing');
  const defs = sortedTanks.map(t => t.name).filter(n => n !== me);
  const lab = 108, cell = Math.max(26, Math.min(40, (Math.max(640, W('ammo')) - lab) / defs.length)), rh = 24;
  const svg = el('svg', { viewBox: `0 0 ${lab + cell * defs.length + 10} ${70 + ammos.length * rh}`, role: 'img', 'aria-label': 'Ammo damage table' }, host);
  defs.forEach((b, c) => txt(svg, 0, 0, b, { transform: `translate(${lab + c * cell + cell / 2 + 4},64) rotate(-60)`, fill: 'var(--ink-2)', 'font-size': 10.5 }));
  const best = Object.fromEntries(defs.map(b => [b, Math.max(...ammos.map(a => M[a][b]))]));
  const mx = Math.max(...Object.values(best));
  ammos.forEach((am, r) => {
    const y = 70 + r * rh;
    txt(svg, lab - 8, y + 15, am.replace(/([a-z])([A-Z])/g, '$1 $2') + (C.ammo[am].selectable || am === 'Standard' ? '' : ' *'), { 'text-anchor': 'end', fill: 'var(--ink-2)', 'font-size': 11 });
    defs.forEach((b, c) => {
      const v = M[am][b], x = lab + c * cell;
      el('rect', { x: x + 1, y: y + 1, width: cell - 2, height: rh - 2, rx: 2, fill: seq(Math.round(v / mx * 7)) }, svg);
      txt(svg, x + cell / 2, y + 15, String(Math.round(v)), { 'text-anchor': 'middle', 'font-size': 9.5, 'font-family': 'var(--f-data)', fill: v / mx > 0.6 ? '#fff' : 'var(--ink)', 'font-weight': v === best[b] ? 700 : 400 });
      const hit = el('rect', { x, y, width: cell, height: rh, fill: 'transparent' }, svg);
      hit.addEventListener('pointermove', ev => showTip(ev, [`${v.toFixed(0)} damage per shot`, `${am} against ${b}'s front`, `x${C.ammo[am].dmg} damage, x${C.ammo[am].pen} pen${v === best[b] ? ' · best here' : ''}`]));
      hit.addEventListener('pointerleave', hideTip);
    });
  });
}

// 6. turret yaw
function drawYaw() {
  const host = $('yaw'); if (!host) return; host.replaceChildren();
  const w = W('yaw'), h = 260, m = { l: 46, r: 90, t: 12, b: 36 };
  const degs = C.tanks[tanks[0].name].yaw.deg, X = i => m.l + i / (degs.length - 1) * (w - m.l - m.r), Y = v => m.t + (1 - v) * (h - m.t - m.b);
  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': 'Front damage chance by turret angle' }, host);
  for (const v of [0, 0.25, 0.5, 0.75, 1]) { el('line', { x1: m.l, x2: w - m.r, y1: Y(v), y2: Y(v), stroke: 'var(--grid)' }, svg); txt(svg, m.l - 6, Y(v) + 4, pct(v), { 'text-anchor': 'end', fill: 'var(--muted)', 'font-size': 10 }); }
  degs.forEach((d, i) => txt(svg, X(i), h - m.b + 16, `${d}°`, { 'text-anchor': 'middle', fill: 'var(--muted)', 'font-size': 10 }));
  txt(svg, w - m.r, h - 4, 'turret turned away from the hull →', { 'text-anchor': 'end', fill: 'var(--ink-2)', 'font-size': 11 });
  const pens = window.TYR_ARMOR ? window.TYR_ARMOR[tanks[0].name].pen : null;
  const sel = pick();
  for (const t of [...tanks].sort((a, b) => (a.id === sel.id) - (b.id === sel.id))) {
    const y = C.tanks[t.name].yaw, pi = (pens || []).indexOf(aimPen); if (pi < 0) continue;
    const ys = y.dchance.map(r => r[pi]), on = t.id === sel.id;
    el('path', { d: ys.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' '), fill: 'none', stroke: on ? clsVar(t) : 'var(--axis)', 'stroke-width': on ? 2.5 : 1, opacity: on ? 1 : 0.7 }, svg);
    if (on) txt(svg, X(degs.length - 1) + 8, Y(ys[ys.length - 1]) + 4, t.name, { fill: 'var(--ink)', 'font-size': 11, 'font-weight': 600 });
  }
}

// 7. tread radar small multiples
function drawTread() {
  const host = $('tread'); if (!host) return; host.replaceChildren();
  const w = W('tread'), cols = w < 520 ? 3 : w < 820 ? 4 : 6, cw = w / cols, R = Math.min(cw, 140) / 2 - 14, ch = R * 2 + 36;
  const mx = Math.max(...tanks.flatMap(t => C.tanks[t.name].tread.area));
  const order = [...tanks].sort((a, b) => Math.max(...C.tanks[b.name].tread.area) - Math.max(...C.tanks[a.name].tread.area));
  const svg = el('svg', { viewBox: `0 0 ${w} ${Math.ceil(order.length / cols) * ch + 14}`, role: 'img', 'aria-label': 'Tread area by direction' }, host);
  order.forEach((t, i) => {
    const d = C.tanks[t.name].tread, cx = (i % cols) * cw + cw / 2, cy = Math.floor(i / cols) * ch + R + 20;
    el('circle', { cx, cy, r: R, fill: 'none', stroke: 'var(--grid)' }, svg); el('circle', { cx, cy, r: R / 2, fill: 'none', stroke: 'var(--grid)' }, svg);
    const pts = d.az.map((az, k) => { const r = R * d.area[k] / mx, th = az * Math.PI / 180; return [cx - Math.sin(th) * r, cy - Math.cos(th) * r]; });
    el('path', { d: pts.map((p, k) => (k ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ') + 'Z', fill: 'var(--x-tread)', 'fill-opacity': 0.25, stroke: 'var(--x-tread)', 'stroke-width': 1.5 }, svg);
    txt(svg, cx, cy - R - 6, `${t.name} · ${Math.max(...d.area).toFixed(1)} m²`, { 'text-anchor': 'middle', fill: 'var(--ink-2)', 'font-size': 11 });
  });
  txt(svg, 0, Math.ceil(order.length / cols) * ch + 10, `Tread area visible from each direction, level shots. Front is up. Outer ring = ${mx.toFixed(1)} m².`, { fill: 'var(--muted)', 'font-size': 11 });
}

// 8. ram energy + 9. size vs camo (two small bar/scatter charts)
function drawRam() {
  const host = $('ram'); if (!host) return; host.replaceChildren();
  const rows = sortedTanks.map(t => ({ t, r: C.tanks[t.name].ram })).sort((p, q) => q.r.ke_mj - p.r.ke_mj);
  const w = W('ram'), lab = 84, rh = 20, h = rows.length * rh + 10, x1 = w - 170, mx = rows[0].r.ke_mj;
  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': 'Ram energy' }, host);
  rows.forEach(({ t, r }, i) => {
    const y = i * rh, bw = r.ke_mj / mx * (x1 - lab);
    txt(svg, lab - 8, y + 14, t.name, { 'text-anchor': 'end', fill: 'var(--ink-2)' });
    el('rect', { x: lab, y: y + 4, width: Math.max(2, bw), height: 12, rx: 2, fill: clsVar(t) }, svg);
    txt(svg, lab + bw + 6, y + 14, `${r.ke_mj} MJ · ${r.mass_t} t at ${Math.round(r.speed_kph)} kph`, { fill: 'var(--ink-2)', 'font-size': 10.5, 'font-family': 'var(--f-data)' });
  });
}
function drawSize() {
  const host = $('size'); if (!host) return; host.replaceChildren();
  const w = W('size'), h = 340, m = { l: 50, r: 20, t: 20, b: 40 };
  const pts = tanks.map(t => ({ t, x: C.tanks[t.name].size.side_m2, y: C.tanks[t.name].size.camo }));
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const x0 = Math.min(...xs) * 0.9, x1 = Math.max(...xs) * 1.05, y0 = 0, y1 = Math.max(...ys) * 1.1;
  const X = v => m.l + (v - x0) / (x1 - x0) * (w - m.l - m.r), Y = v => h - m.b - (v - y0) / (y1 - y0) * (h - m.t - m.b);
  const svg = el('svg', { viewBox: `0 0 ${w} ${h}`, role: 'img', 'aria-label': 'Side silhouette against camouflage' }, host);
  TA.axes(svg, X, Y, TA.niceTicks(x0, x1), TA.niceTicks(y0, y1), m, w, h, 'Side silhouette (m²) →', '↑ Camouflage (%)');
  const P = pts.map(p => ({ t: p.t, x: X(p.x), y: Y(p.y), name: p.t.name, sel: TA.selected === p.t.id }));
  for (const p of P) TA.dot(svg, p.t, p.x, p.y, 5, () => [p.t.name, `${C.tanks[p.t.name].size.side_m2} m² side, ${C.tanks[p.t.name].size.camo}% camo`, `${C.tanks[p.t.name].size.height_m.toFixed(2)} m tall`]);
  TA.labelPoints(svg, P);
}

function drawCombat() { drawStk(); drawBreak(); drawAim(); drawHull(); drawAmmo(); drawYaw(); drawTread(); drawRam(); drawSize(); }
window.TC = { drawCombat };
if (TA.chart) { TA.chart('combat', drawCombat); TA.redraw && TA.redraw(); } else { TA.onDraw.push(drawCombat); drawCombat(); }
})();
