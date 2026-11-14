// Findings: short numbered takeaways ("What this shows") on every page and under chart panels.
// Every number is computed from the loaded data at draw time, so the text stays true after a data refresh.
// This file holds the shared helpers (TA.F) and the roster pages: home, stats, compare, talents, tank, data, method.
// findings_fight.js adds components, armor, combat and maps.
(() => {
const TA = window.TA, T = window.TYR;
if (!TA) return;
const { tanks, sortedTanks, stats, statBy, fmt, make, CLASSES } = TA;
const $ = id => document.getElementById(id);

// ---------- helpers ----------
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
const sdev = a => { const m = mean(a); return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - 1)); };
const median = a => { const s = [...a].sort((x, y) => x - y), n = s.length; return (s[n >> 1] + s[(n - 1) >> 1]) / 2; };
function pearson(a, b) {
  const ma = mean(a), mb = mean(b); let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < a.length; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y; }
  return sab / Math.sqrt(saa * sbb);
}
const list = a => a.length < 3 ? a.join(' and ') : `${a.slice(0, -1).join(', ')} and ${a.at(-1)}`;
const minus = s => s.replace(/^-/, '−');
const sgn = (v, d = 2) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}`;
const pctS = (g, d = 0) => `${g >= 0 ? '+' : '−'}${Math.abs(g * 100).toFixed(d)}%`;
const pct = (x, d = 0) => `${(x * 100).toFixed(d)}%`;
const n0 = v => Math.round(v).toLocaleString('en-US');
const n1 = v => (+v).toFixed(1);
const times = x => `${x < 10 ? x.toFixed(1) : Math.round(x)}×`;
const withUnit = (k, v) => { const u = statBy[k] ? statBy[k].unit : '', s = Math.abs(v) >= 1000 ? n0(v) : minus(fmt(k, v)); return u === '%' ? `${s}%` : `${s}${u ? ' ' + u : ''}`; };
const byName = Object.fromEntries(tanks.map(t => [t.name, t]));
const V = (t, k) => t[TA.mode][k];
const modeWord = () => TA.mode === 'base' ? 'base stats' : 'the 31-point core build';
const sortBy = (a, f) => [...a].sort((x, y) => f(x) - f(y));
const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th');
const lc = k => statBy[k].label.toLowerCase();
// plain names for stats in running text
const SHORT = { MaxHealth: 'health', MaxSpeed: 'top speed', CamoPercentage: 'camouflage', HullTraverseSpeed: 'hull traverse', TurretTraverseSpeed: 'turret traverse',
  AccelerationTime: 'acceleration', FrontBounce70: 'front armor', FrontBounce85: 'front armor', AngledBounce70: 'front armor', RoundBounce70: 'all-round armor',
  SideBounce70: 'side armor', RearBounce70: 'rear armor', FrontEHP70: 'front effective health', GunMaxHoverTilt: 'gun hover tilt', MaxTurretRotation: 'turret arc',
  MaxStrafingSpeed: 'strafe speed', ShellDamage: 'shell damage', DPS: 'damage per second', Mass: 'mass' };
const short = k => SHORT[k] || lc(k);
const cap = s => s[0].toUpperCase() + s.slice(1);

// one findings block per anchor and key; items are strings, falsy ones are dropped
function show(anchor, key, items, heading = 'What this shows') {
  if (!anchor) return;
  let box = anchor.querySelector(`:scope > .findings[data-k="${key}"]`);
  if (!box) { box = make('div', 'findings'); box.dataset.k = key; box.append(make('h3'), make('ol')); anchor.append(box); }
  box.querySelector('h3').textContent = heading;
  const li = items.filter(Boolean);
  box.querySelector('ol').replaceChildren(...li.map(s => make('li', null, s)));
  box.hidden = !li.length;
}
function safe(fn) { try { return fn(); } catch (e) { console.warn('finding skipped:', e); return null; } }
const items = (...fns) => fns.map(safe);
const panel = id => { const h = $('h-' + id); return h && h.closest('.panel'); };
const head = page => document.querySelector(`main > .page[data-page="${page}"] .page-head`);

// pages register finding functions; each page runs them after its charts drew
const reg = {};
function add(page, fn) { if (!reg[page]) { reg[page] = []; TA.chart(page, () => run(page)); } reg[page].push(fn); }
function run(page) { for (const fn of reg[page] || []) safe(fn); }
// chart-local controls (selects, segmented buttons) redraw their own chart only; refresh the text after them
let pend = 0;
const again = ev => { if (!ev.target.closest || !ev.target.closest('.controls, .seg, select')) return; clearTimeout(pend); pend = setTimeout(() => run(TA.page), 0); };
$('main').addEventListener('click', again); $('main').addEventListener('change', again);

// map metadata for the maps in rotation, fetched once and shared by the home and maps findings
const LIVE_MAPS = ['fields', 'divide', 'ravine', 'scorch', 'windvalley', 'core'];
let metaP = null;
const mapsMeta = () => metaP || (metaP = Promise.all(LIVE_MAPS.map(m => fetch(`maps/${m}/meta.json`).then(r => r.ok ? r.json() : null).catch(() => null)))
  .then(a => a.map((meta, i) => meta && { key: LIVE_MAPS[i], name: meta.map.replace(/([a-z])([A-Z])/g, '$1 $2'), meta }).filter(Boolean)));
// the best behind-bush ratio per map, and the camo level where it peaks
function bushPeaks(maps) {
  return maps.map(m => {
    const lv = m.meta.camos.map((c, i) => ({ c, r: Math.max(0, ...(m.meta.spots[String(i)] || []).filter(s => s.kind === 'bush').map(s => s.ratio)) }));
    const top = lv.reduce((a, b) => (b.r > a.r ? b : a));
    return { name: m.name, peak: top.r, at: top.c, last: lv.at(-1), hasBush: m.meta.bushes.length > 0 && top.r > 0 };
  });
}
// "8.3× on Fields and Ravine, 7.6× on Wind Valley, about 5× on Divide and Scorch"
function ratioList(rows) {
  const g = [];
  for (const r of sortBy(rows, r => -r.peak)) {
    // equal to one decimal: one group; under 6× and equal when rounded: one "about" group
    const k = r.peak.toFixed(1), last = g.at(-1);
    if (last && (last.k === k || (r.peak < 6 && last.v < 6 && Math.round(last.v) === Math.round(r.peak)))) { if (last.k !== k) last.about = true; last.names.push(r.name); }
    else g.push({ k, v: r.peak, names: [r.name] });
  }
  return list(g.map(x => `${x.about ? `about ${Math.round(x.v)}` : x.k}× on ${list(x.names.sort())}`));
}
const pcaEnds = ax => {
  const s = T.pca.keys.map((k, i) => [k, T.pca.loadings[i][ax]]).sort((a, b) => b[1] - a[1]);
  const names = arr => [...new Set(arr.map(([k]) => short(k)))].slice(0, 3);
  return { pos: names(s), neg: names([...s].reverse()) };
};

TA.F = { mean, sdev, median, pearson, list, sgn, pctS, pct, n0, n1, times, withUnit, byName, sortBy, ord, short, minus,
  show, items, panel, head, add, run, mapsMeta, bushPeaks, ratioList };

// ---------- home: extra findings under the headline cards ----------
add('home', () => {
  const host = panel('finds');
  const ax = pcaEnds(0), v0 = Math.round(T.pca.var[0] * 100);
  const col = k => tanks.map(t => t.base[k]);
  const base = [
    () => `The biggest split in the roster is ${list(ax.pos)} against ${list(ax.neg)}: it alone explains ${v0}% of the spread between tanks.`,
    () => { const rD = pearson(col('DurabilityRating'), col('MaxHealth')), rS = pearson(col('ScoutingRating'), col('CamoPercentage'));
      return `The in-game Durability rating tracks health (r = ${sgn(rD)}) and Scouting tracks camouflage (r = ${sgn(rS)}), so those two ratings can be trusted.`; },
  ];
  const C = window.TYR_COMBAT;
  if (C) base.push(() => {
    const hd = sortBy(tanks, t => mean(Object.values(C.tanks[t.name].hulldown.dchance))).slice(0, 3);
    return `Hull-down, ${list(hd.map(t => t.name))} are the hardest to hurt: averaged over every gun, ${list(hd.map(t => pct(mean(Object.values(C.tanks[t.name].hulldown.dchance)))))} of hits on their exposed part do damage.`;
  });
  show(host, 'more', items(...base), 'More findings');
  mapsMeta().then(maps => {
    const pk = bushPeaks(maps).filter(p => p.hasBush);
    if (!pk.length) return;
    show(host, 'more', items(...base, () => `On the maps, a tank behind a bush spots up to ${times(Math.max(...pk.map(p => p.peak)))} more ground than it is spotted from, at ${Math.round(median(pk.map(p => p.at)))}% camo. On open ground spotting is even.`), 'More findings');
  });
});

// ---------- stats ----------
const clsMean = (c, k) => mean(tanks.filter(t => t.cls === c).map(t => V(t, k)));
add('stats', () => show(head('stats'), 'page', items(
  () => `On ${modeWord()}, heavies average ${n0(clsMean('Heavy', 'MaxHealth'))} HP against ${n0(clsMean('Medium', 'MaxHealth'))} for mediums and ${n0(clsMean('Light', 'MaxHealth'))} for light tanks.`,
  () => `Light tanks average ${n1(clsMean('Light', 'MaxSpeed'))} kph top speed, heavies ${n1(clsMean('Heavy', 'MaxSpeed'))} kph.`,
  () => { const c = sortBy(CLASSES, c => -clsMean(c, 'DPS')); const s = sortBy(tanks, t => -V(t, 'DPS'));
    return `${c[0]} tanks deal the most damage per second on average (${n1(clsMean(c[0], 'DPS'))} dmg/s); the single best is ${s[0].name} at ${n1(V(s[0], 'DPS'))}, the worst ${s.at(-1).name} at ${n1(V(s.at(-1), 'DPS'))}.`; },
  () => { const s = sortBy(tanks, t => V(t, 'CamoPercentage')), zero = tanks.filter(t => V(t, 'CamoPercentage') <= 0);
    return `Camouflage runs from ${zero.length > 1 ? `0% on ${list(zero.map(t => t.name))}` : `${fmt('', V(s[0], 'CamoPercentage'))}% on ${s[0].name}`} to ${fmt('', V(s.at(-1), 'CamoPercentage'))}% on ${s.at(-1).name}.`; },
)));
add('stats', () => {
  const real = stats.filter(s => s.group !== 'Designer ratings');
  const lead = {}, same = [];
  for (const s of real) {
    const vs = tanks.map(t => V(t, s.key)), best = s.better > 0 ? Math.max(...vs) : Math.min(...vs);
    if (Math.max(...vs) - Math.min(...vs) < 1e-9) { same.push(s.label.toLowerCase()); continue; }
    const w = tanks.filter((t, i) => Math.abs(vs[i] - best) < 1e-9);
    if (w.length === 1) lead[w[0].name] = (lead[w[0].name] || 0) + 1;
  }
  const L = Object.entries(lead).sort((a, b) => b[1] - a[1]);
  const spread = real.map(s => { const vs = tanks.map(t => V(t, s.key)).filter(v => v > 0); return { s, lo: Math.min(...vs), hi: Math.max(...vs), r: Math.max(...vs) / Math.min(...vs), n: vs.length }; })
    .filter(x => x.n === tanks.length && isFinite(x.r) && [x.lo, x.hi].every(v => tanks.filter(t => Math.abs(V(t, x.s.key) - v) < 1e-9).length === 1)).sort((a, b) => b.r - a.r)[0];
  const who = v => tanks.find(t => Math.abs(V(t, spread.s.key) - v) < 1e-9).name;
  show(panel('strips'), 'f', items(
    () => { const top = L.filter(x => x[1] === L[0][1]).map(x => x[0]), next = L.find(x => x[1] < L[0][1]);
      return `${list(top)} ${top.length > 1 ? 'each lead' : 'leads'} ${L[0][1]} stats outright, more than any other tank${next ? `; ${next[0]} leads ${next[1]}` : ''}.`; },
    () => `${cap(short(spread.s.key))} has the widest spread: ${withUnit(spread.s.key, spread.lo)} on ${who(spread.lo)} to ${withUnit(spread.s.key, spread.hi)} on ${who(spread.hi)}, ${times(spread.r)} apart.`,
    () => same.length === 1 ? `${same[0][0].toUpperCase() + same[0].slice(1)} is the same on every tank in this mode.` : same.length ? `${same.length} stats are the same on every tank in this mode: ${list(same.slice(0, 4))}${same.length > 4 ? ' and others' : ''}.` : null,
  ));
});
add('stats', () => {
  const k = $('ds').value, s = statBy[k], xs = tanks.map(t => V(t, k)), mu = mean(xs), sd = sdev(xs);
  if (!(sd > 0)) return show(panel('dist'), 'f', [`Every tank has the same ${s.label.toLowerCase()} in this mode.`]);
  const cm = sortBy(CLASSES, c => -clsMean(c, k) * s.better);
  const far = sortBy(tanks, t => -Math.abs(V(t, k) - mu))[0], z = (V(far, k) - mu) / sd;
  const within = xs.filter(x => Math.abs(x - mu) <= sd).length;
  show(panel('dist'), 'f', items(
    () => `${s.label} by class: ${cm.map((c, i) => `${c.toLowerCase()}${i ? '' : ' tanks average'} ${withUnit(k, clsMean(c, k))}`).join(', ')}.`,
    () => `${far.name} sits furthest from the mean, ${Math.abs(z).toFixed(1)} standard deviations ${z > 0 ? 'above' : 'below'} it at ${withUnit(k, V(far, k))}.`,
    () => `${within} of ${tanks.length} tanks sit within one standard deviation of the mean${within >= 13 ? ', so most of the roster is bunched together' : ''}.`,
  ));
});
const zRows = t => stats.filter(s => s.group !== 'Designer ratings').map(s => {
  const xs = tanks.map(u => V(u, s.key)), sd = sdev(xs); return sd > 0 ? { s, z: (V(t, s.key) - mean(xs)) / sd * s.better } : null; }).filter(Boolean);
const zText = (t, z) => {
  const r = sortBy(z, x => -x.z), f = x => `${short(x.s.key)} (${sgn(x.z, 1)}σ)`;
  const uniq = a => a.filter((x, i) => a.findIndex(y => short(y.s.key) === short(x.s.key)) === i);
  return [`${t.name}'s strongest stats against the roster: ${list(uniq(r).slice(0, 3).map(f))}.`, `Its weakest: ${list(uniq([...r].reverse()).slice(0, 2).map(f))}.`];
};
add('stats', () => {
  const t = tanks.find(x => x.id === TA.selected) || sortedTanks[0], z = zRows(t), far = z.filter(x => Math.abs(x.z) >= 2).length;
  show(panel('z'), 'f', items(...zText(t, z).map(s => () => s), () => `${far} of its ${z.length} stats sit past ±2σ.`));
});

// ---------- compare ----------
add('compare', () => {
  const kx = $('sx').value, ky = $('sy').value, bx = statBy[kx].better, by = statBy[ky].better;
  const front = tanks.filter(a => !tanks.some(b => b !== a && bx * V(b, kx) >= bx * V(a, kx) && by * V(b, ky) >= by * V(a, ky) &&
    (bx * V(b, kx) > bx * V(a, kx) || by * V(b, ky) > by * V(a, ky))));
  const r = pearson(tanks.map(t => V(t, kx)), tanks.map(t => V(t, ky)));
  const missing = CLASSES.filter(c => !front.some(t => t.cls === c));
  show(panel('scatter'), 'f', items(
    () => `With ${statBy[kx].label.toLowerCase()} across and ${statBy[ky].label.toLowerCase()} up, ${front.length} tank${front.length > 1 ? 's' : ''} make the frontier: ${list(sortBy(front, t => -bx * V(t, kx)).map(t => t.name))}.`,
    () => `Across the roster the two correlate at r = ${sgn(r)}${Math.abs(r) < 0.3 ? ', barely linked' : r > 0 ? ', so they tend to rise together' : ', so one tends to fall as the other rises'}.`,
    () => missing.length && missing.length < 3 ? `No ${list(missing.map(c => c.toLowerCase()))} tank reaches the frontier.` : null,
  ));
});
add('compare', () => {
  const a0 = pcaEnds(0), a1 = pcaEnds(1), v = T.pca.var.map(x => Math.round(x * 100));
  const ex = sortBy(tanks, t => t.pca[0]), cm = c => mean(tanks.filter(t => t.cls === c).map(t => t.pca[0]));
  const y = sortBy(tanks, t => t.pca[1]), lowEnd = Math.abs(y[0].pca[1]) > Math.abs(y.at(-1).pca[1]);
  const far = (lowEnd ? y : [...y].reverse()).slice(0, 2), hover = t => t.base.MaxStrafingSpeed > 0 || t.base.GunMaxHoverTilt > 0;
  const noTurret = tanks.filter(t => t.base.MaxTurretRotation < 360);
  show(panel('map'), 'f', items(
    () => `The first axis (${v[0]}% of the spread) runs from ${list(a0.neg)} at one end (${ex[0].name}) to ${list(a0.pos)} at the other (${ex.at(-1).name}, ${ex.at(-2).name}).`,
    () => `Class sits along it in order: heavies average ${minus(n1(cm('Heavy')))}, mediums ${minus(n1(cm('Medium')))}, light tanks ${minus(n1(cm('Light')))}.`,
    () => `The second axis (${v[1]}%) is driven by ${list((lowEnd ? a1.neg : a1.pos).slice(0, 3))}. Its far end holds ${far.every(hover) ? 'the hover tanks ' : ''}${list(far.map(t => t.name))}${noTurret.length === 1 ? `; ${noTurret[0].name}, with a ${noTurret[0].base.MaxTurretRotation}° turret arc, is the only tank without a full turret` : ''}.`,
  ));
});
add('compare', () => {
  const D = T.dist, n = tanks.length, nn = tanks.map((t, i) => { let j = -1; for (let k = 0; k < n; k++) if (k !== i && (j < 0 || D[i][k] < D[i][j])) j = k; return { t, u: tanks[j], d: D[i][j] }; });
  const pair = sortBy(nn, x => x.d)[0], lone = sortBy(nn, x => -x.d)[0];
  const cross = nn.filter(x => x.t.cls !== x.u.cls);
  show(panel('sim'), 'f', items(
    () => `${pair.t.name} and ${pair.u.name} are the most alike pair (distance ${pair.d.toFixed(2)}).`,
    () => `${lone.t.name} is the most unusual tank: its nearest neighbour, ${lone.u.name}, is ${lone.d.toFixed(2)} away, against a median nearest-neighbour distance of ${median(nn.map(x => x.d)).toFixed(2)}.`,
    () => cross.length ? `${cross.length} tank${cross.length > 1 ? 's have' : ' has'} a nearest neighbour from another class: ${list(cross.map(x => `${x.t.name} (${x.u.name})`))}.` : null,
  ));
});
add('compare', () => {
  const col = k => tanks.map(t => t.base[k]), r = (a, b) => pearson(col(a), col(b));
  show(panel('corr'), 'f', items(
    () => `The in-game Firepower rating runs ${r('FirepowerRating', 'DPS') < 0 ? 'against' : 'with'} damage per second (r = ${sgn(r('FirepowerRating', 'DPS'))}) and follows shell damage instead (r = ${sgn(r('FirepowerRating', 'ShellDamage'))}).`,
    () => `Durability tracks health (r = ${sgn(r('DurabilityRating', 'MaxHealth'))}) and Scouting tracks camouflage (r = ${sgn(r('ScoutingRating', 'CamoPercentage'))}).`,
    () => `Health and front armor rise together (r = ${sgn(r('MaxHealth', 'FrontBounce70'))}), and camouflage falls as health rises (r = ${sgn(r('CamoPercentage', 'MaxHealth'))}): no tank trades armor for health or hides well while tough.`,
  ));
});

// ---------- talents ----------
const CORE4 = ['DPS', 'ShellDamage', 'MaxHealth', 'MaxSpeed'];
const shortOf = t => CORE4.filter(k => t.core[k] < t.ceiling[k] - 1e-6);
add('talents', () => {
  const miss = tanks.filter(t => shortOf(t).length), cheap = sortBy(tanks, t => t.core_points), c0 = cheap[0];
  const noSpeed = c0.ceiling.MaxSpeed <= c0.base.MaxSpeed + 1e-9, noReload = c0.core.ReloadTime >= c0.base.ReloadTime - 1e-9;
  const spare = cheap.slice(1).filter(t => t.core_points < 30);
  const gain = k => sortBy(tanks, t => -(t.core[k] / t.base[k]))[0];
  const hp = gain('MaxHealth'), dps = gain('DPS');
  show(head('talents'), 'page', items(
    () => `31 talent points max damage per second, shell damage, health and speed at once on ${tanks.length - miss.length} of ${tanks.length} tanks.` +
      (miss.length ? ` ${list(miss.map(t => t.name))} can't max all four: ${miss.map(t => shortOf(t).map(k => `${short(k)} stops at ${withUnit(k, t.core[k])} of ${withUnit(k, t.ceiling[k])}`).join(', ')).join('; ')}.` : ''),
    () => `${c0.name} needs only ${c0.core_points} points (${list(c0.core_build.map(([n]) => n.toLowerCase()))})${noSpeed && noReload ? '; it has no speed or reload talents to buy' : ''}.` +
      (spare.length ? ` ${list(spare.map(t => `${t.name} (${t.core_points})`))} also have points to spare.` : ''),
    () => `Talents add the most health to ${hp.name} (${pctS(hp.core.MaxHealth / hp.base.MaxHealth - 1)}) and the most damage per second to ${dps.name} (${pctS(dps.core.DPS / dps.base.DPS - 1)}).`,
  ));
});
add('talents', () => {
  const k = $('us').value, s = statBy[k], g = tanks.map(t => ({ t, g: t.base[k] ? (t.ceiling[k] - t.base[k]) / Math.abs(t.base[k]) : 0 }));
  const up = sortBy(g.filter(x => Math.abs(x.g) > 1e-6), x => -x.g * s.better), none = g.length - up.length;
  const cut = s.better < 0 ? tanks.filter(t => t.core[k] < t.base[k] - 1e-9) : [];
  show(panel('uplift'), 'f', items(
    () => { if (!up.length) return null; const tied = v => list(up.filter(x => pctS(x.g) === pctS(v.g)).map(x => x.t.name));
      return `Talents raise ${s.label.toLowerCase()} most on ${tied(up[0])} (${pctS(up[0].g)}) and least on ${tied(up.at(-1))} (${pctS(up.at(-1).g)}).`; },
    () => { if (!up.length) return null; const cm = c => mean(g.filter(x => x.t.cls === c).map(x => x.g));
      return `By class the average gain is ${sortBy(CLASSES, c => -cm(c) * s.better).map(c => `${pctS(cm(c))} for ${c.toLowerCase()} tanks`).join(', ')}.`; },
    () => none && up.length ? `${none} tank${none > 1 ? 's' : ''} can't raise it at all.` : null,
    () => !up.length && cut.length ? `This chart shows the most each stat can rise, and lower is better for ${s.label.toLowerCase()}, so it stays flat. The core build still cuts it on ${cut.length} tanks, most on ${sortBy(cut, t => t.core[k] / t.base[k])[0].name} (${withUnit(k, sortBy(cut, t => t.core[k] / t.base[k])[0].base[k])} to ${withUnit(k, sortBy(cut, t => t.core[k] / t.base[k])[0].core[k])}).` : null,
    () => !up.length && !cut.length ? `No tank can change ${s.label.toLowerCase()} with talents.` : null,
  ));
});

// ---------- tank ----------
add('tank', () => {
  const t = tanks.find(x => x.id === TA.selected);
  if (!t) {
    const n = c => tanks.filter(u => u.cls === c).length, hp = sortBy(tanks, u => V(u, 'MaxHealth')), sp = sortBy(tanks, u => V(u, 'MaxSpeed'));
    return show(document.querySelector('#t-index .page-head'), 'page', items(
      () => `${tanks.length} tanks: ${n('Light')} light, ${n('Medium')} medium and ${n('Heavy')} heavy.`,
      () => `Health runs from ${n0(V(hp[0], 'MaxHealth'))} on ${hp[0].name} to ${n0(V(hp.at(-1), 'MaxHealth'))} on ${hp.at(-1).name}; top speed from ${n1(V(sp[0], 'MaxSpeed'))} kph on ${sp[0].name} to ${n1(V(sp.at(-1), 'MaxSpeed'))} on ${sp.at(-1).name}.`,
    ));
  }
  const i = tanks.indexOf(t), M = T.duel.front, wins = M[i].filter(x => x > 0).length;
  const rank = 1 + tanks.filter((u, j) => M[j].filter(x => x > 0).length > wins).length;
  let w = -1; M[i].forEach((x, j) => { if (j !== i && (w < 0 || M[j][i] > M[w][i])) w = j; });
  const D = T.dist[i]; let nb = -1; D.forEach((d, j) => { if (j !== i && (nb < 0 || d < D[nb])) nb = j; });
  const L = window.TYR_LOAD, lt = L && L.tanks[t.name];
  const sc = lt && Object.keys(lt.best).sort((a, b) => lt.best[b].gain - lt.best[a].gain)[0];
  show(document.querySelector('#t-profile .page-head'), 'page', items(
    ...zText(t, zRows(t)).map(s => () => s),
    () => `Face on, it wins ${wins} of ${tanks.length - 1} frontal face-offs (${tanks.filter((u, j) => M[j].filter(x => x > 0).length === wins).length > 1 ? 'tied ' : ''}${ord(rank)} of ${tanks.length}); its worst matchup is ${tanks[w].name}, ${2 ** M[w][i] > 1000 ? 'whose front it cannot damage' : `which kills it ${times(2 ** M[w][i])} faster`}.`,
    () => `From the front ${Math.round(t.base.FrontBounce70)}% of 70 mm hits do no damage, from the side ${Math.round(t.base.SideBounce70)}%, from the rear ${Math.round(t.base.RearBounce70)}%.`,
    () => lt ? `Components pay most ${L.scenarios[sc].flags.length ? 'while ' + L.scenarios[sc].label.toLowerCase() : 'with only always-on effects'}: ${list(lt.best[sc].comps.map(c => L.components[c].name))} add ${pctS(lt.best[sc].gain)} duel score. Closest tank on paper: ${tanks[nb].name}.` : null,
  ));
});

// ---------- data ----------
add('data', () => {
  const s = sortBy(tanks, t => -V(t, 'DPS')).slice(0, 3), sp = sortBy(tanks, t => -V(t, 'MaxSpeed'));
  const cls = [...new Set(s.map(t => t.cls))];
  const pen = sortBy(tanks, t => -V(t, 'ShellPenetration'));
  show(head('data'), 'page', items(
    () => `Sorted by damage per second the top three are ${list(s.map(t => `${t.name} (${n1(V(t, 'DPS'))})`))}${cls.length === 1 ? `, all ${cls[0].toLowerCase()} tanks` : ''}.`,
    () => `The fastest tank is ${sp[0].name} at ${n1(V(sp[0], 'MaxSpeed'))} kph, the slowest ${sp.at(-1).name} at ${n1(V(sp.at(-1), 'MaxSpeed'))} kph.`,
    () => `Penetration runs from ${fmt('', V(pen.at(-1), 'ShellPenetration'))} mm on ${list(tanks.filter(t => V(t, 'ShellPenetration') === V(pen.at(-1), 'ShellPenetration')).map(t => t.name))} to ${fmt('', V(pen[0], 'ShellPenetration'))} mm on ${pen[0].name}.`,
  ));
});

// ---------- method ----------
add('method', () => {
  const L = window.TYR_LOAD, A = window.TYR_ARMOR, n = c => tanks.filter(t => t.cls === c).length;
  const nc = L ? Object.keys(L.components).length : 0, choose3 = nc * (nc - 1) * (nc - 2) / 6;
  const a = A && A[tanks[0].name];
  const base = [
    () => `${tanks.length} tanks (${n('Light')} light, ${n('Medium')} medium, ${n('Heavy')} heavy) with ${stats.length} stats each, from Steam build ${T.source.steam_buildid}.`,
    () => L ? `${nc} components, so ${n0(choose3)} three-component loadouts per tank, each scored in ${Object.keys(L.scenarios).length} scenarios.` : null,
    () => a ? `Armor is tested from ${a.az.length} directions and ${a.el.length} heights against ${a.pen.length} gun penetrations (${a.pen[0]} to ${a.pen.at(-1)} mm).` : null,
  ];
  show(head('method'), 'page', items(...base));
  mapsMeta().then(maps => { if (!maps.length) return; const c = maps[0].meta.camos;
    show(head('method'), 'page', items(...base, () => `Spotting is swept on the ${maps.length} maps in rotation at ${c.length} camo levels from ${c[0]}% to ${c.at(-1)}%.`)); });
});

if (reg[TA.page]) run(TA.page);
})();
