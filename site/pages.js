// Page content that is not a chart: home findings, the tank page header and stat tiles, the tank index, method details.
// Findings are computed from the data files so they stay true after a data refresh.
(() => {
const TA = window.TA, T = window.TYR;
if (!TA) return;
const { tanks, sortedTanks, statBy, CLASSES, CLS, fmt, make, keyEl, hashFor } = TA;
const $ = id => document.getElementById(id);
const val = (t, k) => t[TA.mode][k];
const signed = (v, d = 2) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}`;
const pctS = (g, d = 0) => `${g >= 0 ? '+' : '−'}${Math.abs(g * 100).toFixed(d)}%`;
const ord = n => n + (n % 100 >= 11 && n % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][n % 10] || 'th');
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
function pearson(a, b) {
  const ma = mean(a), mb = mean(b); let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < a.length; i++) { const x = a[i] - ma, y = b[i] - mb; sab += x * y; saa += x * x; sbb += y * y; }
  return sab / Math.sqrt(saa * sbb);
}
const list = (names) => names.length < 3 ? names.join(' and ') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;

// ---------- home: headline findings ----------
function finding(host, { page, tank, see, kicker, title, big, text, go }) {
  const a = make('a', 'find'); a.href = hashFor(page, tank === undefined ? TA.selected : tank, TA.mode, see);
  a.append(make('p', 'kicker', kicker), make('h3', null, title), make('div', 'big', big), make('p', null, text), make('span', 'go', go + ' →'));
  host.append(a);
}
function drawFinds() {
  const host = $('finds'); host.replaceChildren();
  const B = (t, k) => t.base[k];
  // 1. damage per second leader
  const byDps = [...tanks].sort((a, b) => B(b, 'DPS') - B(a, 'DPS')), [d1, d2] = byDps;
  finding(host, { page: 'compare', tank: d1.id, see: 'scatter', kicker: 'Compare', title: `${d1.name} has the most damage per second`,
    big: `${fmt('DPS', B(d1, 'DPS'))} dmg/s`, go: 'Health against DPS',
    text: `${Math.round((B(d1, 'DPS') / B(d2, 'DPS') - 1) * 100)}% more than ${d2.name}, the next best, on base stats. Top DPS puts it on the frontier of every scatter with DPS on one axis.` });
  // 2. designer firepower rating against real DPS
  const col = k => tanks.map(t => B(t, k)), rD = pearson(col('FirepowerRating'), col('DPS')), rA = pearson(col('FirepowerRating'), col('ShellDamage'));
  finding(host, { page: 'compare', see: 'corr', kicker: 'Compare', title: `The in-game Firepower rating runs ${rD < 0 ? 'against' : 'with'} DPS`,
    big: `r = ${signed(rD)}`, go: 'Which stats move together',
    text: `Across the roster, tanks rated higher for firepower ${rD < 0 ? 'deal less' : 'deal more'} damage per second.${rA > 0.3 ? ` The rating follows shell damage instead (r = ${signed(rA)}).` : ''} ${d1.name}, the DPS leader, is rated ${B(d1, 'FirepowerRating')}/10.` });
  // 3. frontal face-offs
  const M = T.duel.front, wins = tanks.map((t, i) => ({ t, w: M[i].filter(x => x > 0).length })).sort((a, b) => b.w - a.w);
  const topW = wins.filter(x => x.w === wins[0].w), top5 = wins.slice(0, 5);
  finding(host, { page: 'combat', tank: topW[0].t.id, kicker: 'Combat', title: `${list(topW.map(x => x.t.name))} win the most frontal face-offs`,
    big: `${wins[0].w} of ${tanks.length - 1}`, go: 'Face-off matrix',
    text: `Both tanks on core builds, front to front, judged on damage per second, health and penetration against armor.${top5.every(x => x.t.cls === 'Heavy') ? ' The top five are all heavies.' : ''}` });
  // 4. the component worth most more on one tank than on the median tank
  const L = window.TYR_LOAD;
  if (L) {
    const o = [...L.outliers].sort((a, b) => (b.gain - b.median) - (a.gain - a.median))[0], t = tanks.find(x => x.name === o.tank);
    finding(host, { page: 'components', tank: t.id, see: 'notable', kicker: 'Components', title: `${L.components[o.comp].name} on ${o.tank}`,
      big: pctS(o.gain), go: 'Notable builds',
      text: `Duel score gain while ${L.scenarios[o.scen].label.toLowerCase()}, against ${pctS(o.median)} on the median tank. No other component is worth this much more on one tank.` });
  }
  // 5. biggest gap between front and side armor
  const gap = [...tanks].sort((a, b) => (B(b, 'FrontBounce70') - B(b, 'SideBounce70')) - (B(a, 'FrontBounce70') - B(a, 'SideBounce70')));
  const fs = t => `${Math.round(B(t, 'FrontBounce70'))}% / ${Math.round(B(t, 'SideBounce70'))}%`;
  finding(host, { page: 'armor', tank: gap[0].id, see: 'hemi', kicker: 'Armor', title: `${gap[0].name}: strong front, soft sides`,
    big: fs(gap[0]), go: `${gap[0].name} from every angle`,
    text: `Share of hits from a 70 mm gun that do no damage, front against side. Next biggest gaps: ${gap[1].name} (${fs(gap[1])}) and ${gap[2].name} (${fs(gap[2])}).` });
  // 6. talents: the core build
  const cheap = [...tanks].sort((a, b) => a.core_points - b.core_points)[0];
  finding(host, { page: 'talents', kicker: 'Talents', title: '31 talent points max the core stats', big: `${tanks.length - 1} of ${tanks.length} tanks`, go: 'What talents buy',
    text: `On every tank but Fuse, 31 points max damage, reload, health and speed at once, so the core build has no trade-off. ${cheap.name} needs only ${cheap.core_points}.` });
}

// ---------- tank page ----------
const TILES = [
  ['MaxHealth', 'Health'], ['ShellDamage', 'Shell damage'], ['DPS', 'Damage per second'], ['ShellPenetration', 'Penetration'],
  ['MaxSpeed', 'Top speed'], ['CamoPercentage', 'Camouflage'], ['FrontBounce70', 'Front armor', 'no damage vs 70 mm'],
];
function tile(host, t, [k, label, sub]) {
  const s = statBy[k], v = val(t, k), vs = tanks.map(u => val(u, k));
  const rank = 1 + vs.filter(x => s.better * (x - v) > 1e-9).length, ties = vs.filter(x => Math.abs(x - v) < 1e-9).length;
  const d = make('div', 'tile'), lab = make('div', 'lab', label), num = make('div', 'val', s.unit === '%' ? `${fmt(k, v)}%` : fmt(k, v));
  if (s.unit && s.unit !== '%') num.append(make('small', null, s.unit));
  const lo = Math.min(...vs), hi = Math.max(...vs);
  d.append(lab, num);
  if (sub) d.append(make('div', 'sub', sub));
  d.append(make('div', 'rk', `${ord(rank)} of ${tanks.length}${ties > 1 ? ', tied' : ''} · range ${fmt(k, lo)}–${fmt(k, hi)}`));
  d.title = `${s.label}: ${s.better > 0 ? 'higher' : 'lower'} is better`;
  host.append(d);
}
function drawTankHead() {
  const t = tanks.find(x => x.id === TA.selected);
  if (!t) return drawIndex();
  const kick = $('t-kicker'); kick.replaceChildren(keyEl(t), `${t.cls} tank`);
  $('t-name').textContent = t.name;
  $('t-mode').textContent = `Numbers follow the stat mode in the header: ${TA.mode === 'base' ? 'base stats, no talents' : '31-point core talent build'}. Ranks run best to worst.`;
  const host = $('t-tiles'); host.replaceChildren();
  for (const d of TILES) tile(host, t, d);
}
function drawIndex() {
  const host = $('t-cards'); host.replaceChildren();
  for (const c of CLASSES) {
    const g = make('section', 'tgroup'), h = make('h2'), k = make('i', 'key'); k.style.background = `var(${CLS[c]})`;
    h.append(k, c); g.append(h);
    const cards = make('div', 'tcards');
    for (const t of sortedTanks.filter(x => x.cls === c)) {
      const a = make('a', 'tcard'); a.href = hashFor('tank', t.id);
      const b = make('b'); b.append(keyEl(t), t.name);
      a.append(b, make('span', null, `${fmt('MaxHealth', val(t, 'MaxHealth'))} HP · ${fmt('DPS', val(t, 'DPS'))} dmg/s · ${fmt('MaxSpeed', val(t, 'MaxSpeed'))} kph`));
      cards.append(a);
    }
    g.append(cards); host.append(g);
  }
}
// show the profile or the index before any tank-page chart draws (hidden containers measure 0 wide)
const showTankView = () => { const has = !!TA.selected; $('t-index').hidden = has; $('t-profile').hidden = !has; };
TA.onChange.push(showTankView);
showTankView();   // the router's first pass ran before this file loaded

// ---------- method page ----------
function drawMethod() {
  const S = T.source, date = (S.trees_file.match(/\d{4}-\d{2}-\d{2}/) || [''])[0];
  $('meth-build').textContent = `Steam build ${S.steam_buildid} of the game`;
  $('meth-trees').textContent = `talent data version ${S.talent_tree_version}${date ? `, fetched ${date}` : ''}`;
  const L = window.TYR_LOAD; if (!L) return;
  const r = L.ref, dl = $('meth-ref'); dl.replaceChildren();
  for (const [k, v] of [
    ['Fight length', `${r.fight_s} s`], ['Enemy damage per second', `${r.enemy_dps} dmg/s`], ['Enemy damage per shell', `${r.enemy_alpha} dmg`],
    ['Enemy shots that bounce off you', `${r.incoming_bounce * 100}%`], ['Enemy hits that damage your modules', `${r.incoming_module * 100}%`],
    ['Your shots that penetrate', `${r.our_pen * 100}%`], ['Your hits that damage enemy modules', `${r.our_module * 100}%`], ['Shots that are alt shells', `${r.alt_share * 100}%`],
  ]) { const d = make('div'); d.append(make('dt', null, k), make('dd', null, v)); dl.append(d); }
  const ul = $('meth-scen'); ul.replaceChildren();
  for (const sc of Object.values(L.scenarios)) { const li = make('li'); li.append(make('b', null, sc.label + '. '), sc.desc); ul.append(li); }
}

TA.chart('home', drawFinds);
TA.chart('tank', drawTankHead);
TA.chart('method', drawMethod);
if (['home', 'tank', 'method'].includes(TA.page)) TA.redraw();
})();
