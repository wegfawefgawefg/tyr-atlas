// Findings for the components, armor, combat and maps pages. Helpers live in findings.js (TA.F).
// Chart-local state (scenario, penetration, map, camo) is read back from the controls, so the text follows the charts.
(() => {
const TA = window.TA, T = window.TYR, F = TA && TA.F;
if (!F) return;
const { tanks, sortedTanks, CLASSES } = TA;
const { mean, median, pearson, list, pctS, pct, n0, n1, times, byName, sortBy, show, items, panel, head, add, run, mapsMeta, bushPeaks, ratioList } = F;
const $ = id => document.getElementById(id);
const cap = s => s[0].toUpperCase() + s.slice(1);
const pressed = id => { const h = $(id); return h ? [...h.children].findIndex(b => b.getAttribute('aria-pressed') === 'true') : -1; };

// ---------- components ----------
const L = window.TYR_LOAD;
if (L) {
  const SC = Object.keys(L.scenarios);
  const scen = () => { const b = $('scen') && $('scen').querySelector('[aria-pressed="true"]'); return b ? b.dataset.s : 'brawling'; };
  const cn = id => L.components[id].name, LT = t => L.tanks[t.name];
  const gainOf = (t, id, sc) => { const S = LT(t).single[sc]; return S[id].duel / S._base.duel - 1; };
  const lab = sc => L.scenarios[sc].flags.length ? `while ${L.scenarios[sc].label.toLowerCase()}` : 'with only always-on effects';
  const counts = sc => { const c = {}; for (const t of tanks) for (const id of LT(t).best[sc].comps) c[id] = (c[id] || 0) + 1; return Object.entries(c).sort((a, b) => b[1] - a[1]); };
  add('components', () => {
    const med = SC.map(sc => ({ sc, m: median(tanks.map(t => LT(t).best[sc].gain)) })).sort((a, b) => b.m - a.m);
    const st = SC.find(s => !L.scenarios[s].flags.length), same = st && counts(st).filter(([, n]) => n === tanks.length);
    const top = {}; for (const sc of SC) { const b = sortBy(tanks, t => -LT(t).best[sc].gain)[0].name; top[b] = (top[b] || 0) + 1; }
    const lead = Object.entries(top).sort((a, b) => b[1] - a[1])[0];
    show(head('components'), 'page', items(
      () => `${L.scenarios[med[0].sc].label} pays the most: the best loadout adds a median ${pctS(med[0].m)} duel score, against ${list(med.slice(1).map(x => `${pctS(x.m)} ${lab(x.sc)}`))}.`,
      () => same && same.length === 3 ? `Every tank's best loadout ${lab(st)} is the same three: ${list(same.map(([id]) => cn(id)))}.` : null,
      () => `${lead[0]} gains the most from components in ${lead[1]} of ${SC.length} scenarios.`,
    ));
  });
  add('components', () => {
    const sc = scen(), r = sortBy(tanks, t => -LT(t).best[sc].gain), c = counts(sc);
    show(panel('comp'), 'f', items(
      () => `${cap(lab(sc))}, best loadouts add from ${pctS(LT(r.at(-1)).best[sc].gain)} on ${r.at(-1).name} to ${pctS(LT(r[0]).best[sc].gain)} on ${r[0].name}.`,
      () => `${cn(c[0][0])} is in ${c[0][1]} of ${tanks.length} best loadouts, ${cn(c[1][0])} in ${c[1][1]}.`,
    ));
    const ids = Object.keys(L.components), G = ids.map(id => ({ id, g: tanks.map(t => ({ t, g: gainOf(t, id, sc) })) }));
    const all = G.flatMap(x => x.g.map(y => ({ id: x.id, ...y }))), top = sortBy(all, x => -x.g)[0];
    const meds = sortBy(G.map(x => ({ id: x.id, m: median(x.g.map(y => y.g)) })), x => -x.m), dead = G.filter(x => x.g.every(y => y.g <= 1e-6)).length;
    show(panel('cheat'), 'f', items(
      () => `The biggest single-component gain ${lab(sc)} is ${cn(top.id)} on ${top.t.name}: ${pctS(top.g, 1)}.`,
      () => `On the median tank the best components are ${cn(meds[0].id)} (${pctS(meds[0].m, 1)}) and ${cn(meds[1].id)} (${pctS(meds[1].m, 1)}).`,
      () => dead ? `${dead} of ${ids.length} components show no duel effect on any tank ${lab(sc)}.` : null,
    ));
    const t = tanks.find(x => x.id === TA.selected) || sortedTanks[0], D = LT(t), b = D.best[sc], h = D.hist[sc];
    show(panel('cloud'), 'f', items(
      () => `${t.name}'s best loadout ${lab(sc)} adds ${pctS(b.gain)}; the median loadout adds ${pctS(h.p50)} and the 90th percentile ${pctS(h.p90)}, so picking well is worth ${Math.round((b.gain - h.p50) * 100)} percentage points.`,
      () => `${D.fronts[sc].length} loadouts sit on its front, where no other loadout beats them on damage, health and speed at once.`,
    ));
    const spread = sortBy(tanks, u => -(LT(u).hist[sc].max - LT(u).hist[sc].p50));
    show(panel('ridge'), 'f', items(
      () => { const a = spread[0], z = spread.at(-1), H = u => LT(u).hist[sc];
        return `Loadout choice matters most on ${a.name} (best ${pctS(H(a).max)}, median ${pctS(H(a).p50)}) and least on ${z.name} (best ${pctS(H(z).max)}, median ${pctS(H(z).p50)}).`; },
      () => `Across tanks the median loadout adds ${pctS(median(tanks.map(u => LT(u).hist[sc].p50)))} and the best ${pctS(median(tanks.map(u => LT(u).hist[sc].max)))}.`,
    ));
    const cm = c => mean(tanks.filter(u => u.cls === c).map(u => LT(u).best[sc].gain));
    show(panel('best'), 'f', items(
      () => `${r[0].name} has the best loadout ${lab(sc)}: ${list(LT(r[0]).best[sc].comps.map(cn))}.`,
      () => `By class the best loadouts average ${sortBy(CLASSES, c => -cm(c)).map(c => `${pctS(cm(c))} for ${c.toLowerCase()} tanks`).join(', ')}.`,
    ));
  });
  add('components', () => {
    const outs = sortBy(L.outliers, o => -(o.gain - o.median)), seen = new Set(), pick = [];
    for (const o of outs) if (!seen.has(o.comp)) { seen.add(o.comp); pick.push(o); if (pick.length === 2) break; }
    const alpha = sortBy(tanks, t => t.core.ShellDamage);
    const abil = sortBy(tanks, t => t.base.AbilityCost * 100 + t.base.AbilityCooldown);
    const why = o => { const t = byName[o.tank], d = L.components[o.comp].desc;
      if (alpha.indexOf(t) < 3 && /Shell Damage by \{LevelValue\}/.test(d)) return ` ${o.tank} fires light ${Math.round(t.core.ShellDamage)}-damage shells, so a flat damage bonus is a bigger share.`;
      if (abil.indexOf(t) === 0 && /abilit/i.test(d)) return ` It pays out on ability use, and ${o.tank} has the cheapest ability (${t.base.AbilityCost} energy, ${t.base.AbilityCooldown} s cooldown).`;
      return ''; };
    const best = {}; for (const s of L.synergy_top) if (!best[s.tank] || s.syn > best[s.tank].syn) best[s.tank] = s;
    const syn = Object.values(best).sort((a, b) => b.syn - a.syn).slice(0, 4), pairs = [...new Set(syn.map(s => `${cn(s.a)} + ${cn(s.b)}`))];
    const cost = t => t.base.AbilityCost, medCost = median(tanks.map(cost)), cheap = syn.every(s => cost(byName[s.tank]) < medCost);
    show(panel('notable'), 'f', items(
      ...pick.map(o => () => `${cn(o.comp)} is worth far more on ${o.tank} than on most tanks: ${pctS(o.gain)} ${lab(o.scen)} against ${pctS(o.median)} on the median tank.${why(o)}`),
      () => `The strongest pairs are energy loops: ${list(pairs)} amplify each other most on ${list(syn.map(s => s.tank))}` +
        (cheap ? `, whose abilities cost ${Math.min(...syn.map(s => cost(byName[s.tank])))} to ${Math.max(...syn.map(s => cost(byName[s.tank])))} energy against a roster median of ${Math.round(medCost)}.` : '.'),
    ));
  });
}

// ---------- armor ----------
const AR = window.TYR_ARMOR;
if (AR) {
  const penOf = id => { const v = $(id) ? $(id).value : '70'; return v.startsWith('t:') ? byName[v.slice(2)].base.ShellPenetration : +v; };
  const any = AR[tanks[0].name], e0 = any.el.indexOf(0), azI = az => any.az.indexOf(az);
  const nd = (t, ai, pen, ei = e0) => 1 - AR[t.name].dchance[ei][ai][AR[t.name].pen.indexOf(pen)];
  const arc = (t, pen, a, b) => mean(any.az.map((az, i) => [az, i]).filter(([az]) => az >= a && az <= b).map(([, i]) => nd(t, i, pen)));
  const side = (t, pen) => (arc(t, pen, 80, 100) + arc(t, pen, 260, 280)) / 2;
  add('armor', () => {
    const B = (t, k) => t.base[k], fr = sortBy(tanks, t => -B(t, 'FrontBounce70')), gap = sortBy(tanks, t => -(B(t, 'FrontBounce70') - B(t, 'SideBounce70')));
    const fs = t => `${t.name} (${Math.round(B(t, 'FrontBounce70'))}% / ${Math.round(B(t, 'SideBounce70'))}%)`;
    const thin = tanks.filter(t => B(t, 'FrontBounce70') < 5), rear = sortBy(tanks, t => -B(t, 'RearBounce70'));
    show(head('armor'), 'page', items(
      () => `${fr[0].name} has the toughest front: ${Math.round(B(fr[0], 'FrontBounce70'))}% of 70 mm hits do no damage. Next are ${fr[1].name} (${Math.round(B(fr[1], 'FrontBounce70'))}%) and ${fr[2].name} (${Math.round(B(fr[2], 'FrontBounce70'))}%).`,
      () => `The biggest front-to-side gaps, front / side: ${list(gap.slice(0, 3).map(fs))}.`,
      () => thin.length ? `${list(thin.map(t => t.name))} stop${thin.length > 1 ? '' : 's'} under 5% of 70 mm hits from the front.` : null,
      () => `The best rear armor is ${rear[0].name}'s at ${Math.round(B(rear[0], 'RearBounce70'))}%; ${tanks.filter(t => B(t, 'RearBounce70') < 30).length} of ${tanks.length} tanks stop under 30% from behind.`,
    ));
  });
  add('armor', () => {
    const pen = penOf('arm-pen'), round = t => mean(any.az.map((_, i) => nd(t, i, pen))), r = sortBy(tanks, t => -round(t));
    const open = tanks.filter(t => Math.max(...any.az.map((_, i) => nd(t, i, pen))) < 0.01);
    const fh = tanks.filter(t => arc(t, pen, 0, 10) + arc(t, pen, 350, 355) > 0 && (arc(t, pen, 0, 10) + arc(t, pen, 350, 355)) / 2 >= 3 * Math.max(side(t, pen), 0.01) && (arc(t, pen, 0, 10) + arc(t, pen, 350, 355)) / 2 > 0.3);
    show(panel('armor'), 'f', items(
      () => `Against ${pen} mm, ${r[0].name} is the toughest all round (${pct(round(r[0]))} of level hits do no damage on average), then ${r[1].name} (${pct(round(r[1]))}) and ${r[2].name} (${pct(round(r[2]))}).`,
      () => open.length ? `${list(open.map(t => t.name))} take${open.length > 1 ? '' : 's'} damage from every level hit, from every side, at ${pen} mm.` : null,
      () => fh.length ? `${list(fh.map(t => t.name))} stop at least three times as much from the front as from the side, so showing a side costs them most.` : null,
    ));
  });
  add('armor', () => {
    const pen = penOf('arm-pen'), t = tanks.find(x => x.id === TA.selected) || sortedTanks.find(x => x.cls === 'Heavy') || tanks[0], a = AR[t.name];
    const f = nd(t, 0, pen), ang = (nd(t, azI(30), pen) + nd(t, azI(330), pen)) / 2, top = a.el.indexOf(75);
    show(panel('hemi'), 'f', items(
      () => `${t.name} against ${pen} mm: ${pct(f)} of level hits from the front do no damage, ${pct(side(t, pen))} from the side, ${pct(arc(t, pen, 170, 190))} from the rear.`,
      () => Math.abs(ang - f) >= 0.02 ? `Angling 30° ${ang > f ? 'raises' : 'lowers'} its front no-damage share to ${pct(ang)}.` : `Angling 30° barely changes its front (${pct(ang)}).`,
      () => top >= 0 ? `Shots from steeply above (75°) at the front do no damage ${pct(nd(t, 0, pen, top))} of the time.` : null,
      () => `Treads take ${pct(a.tread[e0][azI(90)])} of side hits; crit modules make up ${pct(a.crit[e0][azI(180)])} of the rear.`,
    ));
  });
}

// ---------- combat ----------
const C = window.TYR_COMBAT;
if (C) {
  const names = tanks.map(t => t.name), pick = () => tanks.find(t => t.id === TA.selected) || byName.Atlas || tanks[0];
  const aimPen = () => { const i = pressed('aim-pen'); return i >= 0 ? C.aim_pens[i] : 70; };
  add('combat', () => {
    const mode = pressed('duel-mode') === 1 ? 'angled' : 'front', M = T.duel[mode], W = m => T.duel[m].map(r => r.filter(x => x > 0).length);
    const w = W(mode), r = sortBy(tanks.map((t, i) => ({ t, w: w[i] })), x => -x.w), topW = r.filter(x => x.w === r[0].w);
    const d = W('angled').map((x, i) => x - W('front')[i]), up = d.indexOf(Math.max(...d)), dn = d.indexOf(Math.min(...d));
    show(panel('duel'), 'f', items(
      () => `${mode === 'front' ? 'Face on' : 'Both angled 30°'}, ${list(topW.map(x => x.t.name))} win the most face-offs (${r[0].w} of ${tanks.length - 1}); ${r.at(-1).t.name} wins the fewest (${r.at(-1).w}).${r.slice(0, 5).every(x => x.t.cls === 'Heavy') ? ' The top five are all heavies.' : ''}`,
      () => d[up] > 0 ? `Angling both tanks 30° helps ${tanks[up].name} most (+${d[up]} win${d[up] > 1 ? 's' : ''})${d[dn] < 0 ? ` and hurts ${tanks[dn].name} most (−${-d[dn]} win${d[dn] < -1 ? 's' : ''})` : ''}.` : null,
      () => { const one = [], fin = []; M.forEach((row, i) => row.forEach((x, j) => { if (i !== j && x > 0) (2 ** x > 1000 ? one : fin).push([i, j, x]); }));
        const big = fin.sort((a, b) => b[2] - a[2])[0];
        return `${one.length ? `In ${one.length} face-offs one tank can't hurt the other's front at all, such as ${tanks[one[0][1]].name} against ${tanks[one[0][0]].name}. ` : ''}` +
          (big ? `The biggest mismatch where both can do damage: ${tanks[big[0]].name} kills ${tanks[big[1]].name} ${times(2 ** big[2])} faster than the reverse.` : ''); },
    ));
    const S = (a, b) => C.stk[a][b], rowM = a => mean(names.filter(b => b !== a).map(b => S(a, b).stk)), colM = b => mean(names.filter(a => a !== b).map(a => S(a, b).stk));
    const att = sortBy(names, rowM), def = sortBy(names, b => -colM(b));
    const zero = {}; for (const a of names) for (const b of names) if (a !== b && S(a, b).dc_aim <= 0) (zero[b] = zero[b] || []).push(a);
    const zt = Object.entries(zero).sort((a, b) => b[1].length - a[1].length)[0];
    show(panel('stk'), 'f', items(
      () => `${att[0]} needs the fewest damaging hits, ${n1(rowM(att[0]))} on average across the roster, with ${Math.round(byName[att[0]].core.ShellDamage)}-damage shells; ${att.at(-1)} needs the most (${n1(rowM(att.at(-1)))}).`,
      () => `${def[0]} is the hardest to kill at ${n1(colM(def[0]))} hits on average; ${def.at(-1)} is the easiest at ${n1(colM(def.at(-1)))}.`,
      () => zt ? `${list(zt[1])} can't damage ${zt[0]}'s front at all, even aimed.` : null,
    ));
    const me = pick().name, levers = {}; let nAtt = 0, nDef = 0, dl = {};
    for (const b of names) if (b !== me) { const s = S(me, b); if (s.levers.length) { nAtt++; for (const l of s.levers.map(x => x.replace(/ \(.*\)$/, ''))) levers[l] = (levers[l] || 0) + 1; } }
    for (const a of names) if (a !== me) { const s = S(a, me); if (s.def_levers.length) { nDef++; for (const l of s.def_levers.map(x => x.replace(/ \(.*\)$/, ''))) dl[l] = (dl[l] || 0) + 1; } }
    const lv = Object.entries(levers).sort((a, b) => b[1] - a[1])[0], dv = Object.entries(dl).sort((a, b) => b[1] - a[1])[0];
    show(panel('breaks'), 'f', items(
      () => lv ? `${me} can cut a shot off ${nAtt} of ${names.length - 1} matchups with one change; the lever that works most often is ${lv[0]} (${lv[1]} matchups).` : `No single component or ammo cuts a shot off any of ${me}'s matchups.`,
      () => dv ? `Defending, ${nDef} enemies need an extra hit on ${me} with the right durability component; ${dv[0]} does it in ${dv[1]}.` : null,
    ));
  });
  add('combat', () => {
    const ratio = b => { const r = names.filter(a => a !== b).map(a => C.stk[a][b]).filter(s => s.dc_even > 0).map(s => s.dc_aim / s.dc_even); return r.length ? median(r) : 1; };
    const R = sortBy(names, b => -ratio(b)), low = R.filter(b => ratio(b) < 1);
    const t = pick(), pen = aimPen(), a = C.tanks[t.name].aim, pi = C.aim_pens.indexOf(pen), cv = C.crit_values;
    show(panel('aim'), 'f', items(
      () => `Aiming pays most against heavy fronts: with a ${C.ref_sigma} m spread, hits on ${R[0]} do damage ${times(ratio(R[0]))} as often as evenly spread hits, ${R[1]} ${times(ratio(R[1]))}, ${R[2]} ${times(ratio(R[2]))}.`,
      () => low.length ? `On ${list(low)} aiming loses (${low.map(b => times(ratio(b))).join(', ')}): there is little armor to aim around, and aimed shots that drift off the tank miss.` : null,
      () => a.front && pi >= 0 ? `${t.name} at ${pen} mm: aimed with a ${C.sigmas[0]} m spread, ${pct(a.front[pi][0])} of front shots do damage, falling to ${pct(a.front[pi].at(-1))} at ${C.sigmas.at(-1)} m.` : null,
      () => `Crit modules: a bonus spot adds ${Math.round(cv.bonus * 100)}% damage, and a fire deals ${cv.fire_total} damage in total.`,
    ));
    const pen2 = String(pen), hd = t => C.tanks[t.name].hulldown, avg = t => mean(Object.values(hd(t).dchance));
    const atPen = sortBy(tanks, t => hd(t).dchance[pen2]), allP = sortBy(tanks, avg), none = tanks.filter(t => Object.values(hd(t).dchance).every(v => v >= 0.999));
    const dep = sortBy(tanks, t => hd(t).depression_deg), lo = dep.filter(t => hd(t).depression_deg === hd(dep[0]).depression_deg), hi = dep.filter(t => hd(t).depression_deg === hd(dep.at(-1)).depression_deg);
    show(panel('hull'), 'f', items(
      () => `At ${pen} mm, ${list(atPen.slice(0, 3).map(t => `${t.name} (${pct(hd(t).dchance[pen2])})`))} are the hardest to hurt hull-down.`,
      () => `Averaged over every gun from ${C.aim_pens[0]} to ${C.aim_pens.at(-1)} mm, the best hull-down tanks are ${list(allP.slice(0, 3).map(t => t.name))}.`,
      () => none.length ? `Hull-down doesn't help ${list(none.map(t => t.name))}: every hit on the exposed part does damage, whatever the gun.` : null,
      () => `Gun depression runs from ${hd(dep[0]).depression_deg}° on ${list(lo.map(t => t.name))} to ${hd(dep.at(-1)).depression_deg}° on ${list(hi.map(t => t.name))}; more lets a tank use steeper crests.`,
    ));
    const me = t.name, M = C.ammo_vs_front[me], ams = Object.keys(M).filter(k => C.ammo[k].selectable || k === 'Standard' || k === 'ArmorPiercing');
    const defs = names.filter(b => b !== me), bestAm = b => ams.reduce((x, y) => (M[y][b] > M[x][b] ? y : x)), cnt = {};
    for (const b of defs) { const k = bestAm(b); cnt[k] = (cnt[k] || 0) + 1; }
    const topAm = Object.entries(cnt).sort((a, b) => b[1] - a[1])[0], amName = k => k.replace(/([a-z])([A-Z])/g, '$1 $2') + ' ammo';
    const gain = sortBy(defs.filter(b => M.Standard[b] > 0), b => -(M[bestAm(b)][b] / M.Standard[b]))[0], dead = defs.filter(b => ams.every(k => M[k][b] <= 0));
    show(panel('ammo'), 'f', items(
      () => `For ${me}, ${amName(topAm[0])} is the best ammo against ${topAm[1]} of ${defs.length} fronts.`,
      () => gain ? `Its biggest gain over standard shells is against ${gain}: ${Math.round(M[bestAm(gain)][gain])} instead of ${Math.round(M.Standard[gain])} damage per shot with ${amName(bestAm(gain))}.` : null,
      () => dead.length ? `${me} can't damage the front of ${list(dead)} with any ammo.` : null,
    ));
    const ypi = AR ? AR[tanks[0].name].pen.indexOf(pen) : -1, Y = u => C.tanks[u.name].yaw, i90 = Y(t).deg.indexOf(90);
    if (ypi >= 0 && i90 >= 0) {
      const dY = u => Y(u).dchance[i90][ypi] - Y(u).dchance[0][ypi], s = sortBy(tanks, u => -dY(u));
      show(panel('yaw'), 'f', items(
        () => `Turning the turret 90° off the hull raises front damage chance most on ${s[0].name} (${pct(Y(s[0]).dchance[0][ypi])} to ${pct(Y(s[0]).dchance[i90][ypi])}) at ${pen} mm.`,
        () => dY(s.at(-1)) < -0.01 ? `On ${s.at(-1).name} it lowers it (${pct(Y(s.at(-1)).dchance[0][ypi])} to ${pct(Y(s.at(-1)).dchance[i90][ypi])}).` : null,
        () => { const v = Y(t).deg.map((d, i) => Y(t).dchance[i][ypi]);
          return Math.max(...v) - Math.min(...v) < 0.005 ? `${t.name}: ${pct(v[0])} at every turret angle.` : `${t.name}: ${Y(t).deg.map((d, i) => `${pct(v[i])} at ${d}°`).join(', ')}.`; },
      ));
    }
  });
  add('combat', () => {
    const tr = t => Math.max(...C.tanks[t.name].tread.area), s = sortBy(tanks, t => -tr(t)), none = tanks.filter(t => tr(t) <= 0);
    const ts = sortBy(tanks, t => -t.base.TreadShareSide);
    show(panel('tread'), 'f', items(
      () => `${s[0].name} shows the most tread, ${n1(tr(s[0]))} m² at its widest; ${list((none.length ? none : [s.at(-1)]).map(t => t.name))} ${none.length ? `${none.length > 1 ? 'have' : 'has'} none` : `shows the least (${n1(tr(s.at(-1)))} m²)`}.`,
      () => `Treads soak up the most side hits on ${list(ts.slice(0, 3).map(t => `${t.name} (${Math.round(t.base.TreadShareSide)}%)`))}.`,
    ));
    const Z = t => C.tanks[t.name].size, z = sortBy(tanks, t => -Z(t).side_m2);
    show(panel('size'), 'f', items(
      () => `${z[0].name} has the biggest side silhouette (${n1(Z(z[0]).side_m2)} m²) with ${Z(z[0]).camo}% camo; ${z.at(-1).name} the smallest (${n1(Z(z.at(-1)).side_m2)} m²) with ${Z(z.at(-1)).camo}%.`,
      () => `Size and camo run against each other: r = ${F.sgn(pearson(tanks.map(t => Z(t).side_m2), tanks.map(t => Z(t).camo)))} across the roster.`,
    ));
    const K = t => C.tanks[t.name].ram, k = sortBy(tanks, t => -K(t).ke_mj);
    show(panel('ram'), 'f', items(
      () => `${k[0].name} hits hardest: ${n1(K(k[0]).ke_mj)} MJ at top speed (${K(k[0]).mass_t} t at ${Math.round(K(k[0]).speed_kph)} kph), ${(K(k[0]).ke_mj / K(k.at(-1)).ke_mj).toFixed(1)} times as much as ${k.at(-1).name}, the weakest hitter.`,
      () => `The top three are ${list(k.slice(0, 3).map(t => t.name))}.`,
    ));
  });
}

// ---------- maps ----------
add('maps', () => mapsMeta().then(maps => {
  if (!maps.length) return;
  const opens = maps.flatMap(m => Object.values(m.meta.spots).flat().filter(s => s.kind === 'open').map(s => s.ratio));
  const pk = bushPeaks(maps), bush = pk.filter(p => p.hasBush), none = pk.filter(p => !p.hasBush), at = median(bush.map(p => p.at));
  const last = bush.map(p => p.last), km = sortBy(maps, m => m.meta.playable_km2), cap = maps[0].meta.rules.max_camo;
  const allMap = maps.every(m => m.meta.boundary === 'map');
  show(head('maps'), 'page', items(
    () => `Open-ground spotting is symmetric on every map: every open spot spots between ${Math.min(...opens).toFixed(2)}× and ${Math.max(...opens).toFixed(2)}× as much ground as it is spotted from.`,
    () => bush.length ? `Behind-bush spots peak around ${Math.round(at)}% camo: ${ratioList(bush)}.${none.length ? ` ${list(none.map(p => p.name))} ${none.length > 1 ? 'have' : 'has'} no bushes.` : ''}` : null,
    () => bush.length && last[0].c >= cap ? `At ${Math.round(last[0].c)}% camo the bush edge disappears (at most ${times(Math.max(...last.map(l => l.r)))}), because the cap leaves bushes nothing to add.` : null,
    () => `With ${allMap ? 'real' : 'mostly real'} boundaries, the playable areas run from ${km[0].meta.playable_km2.toFixed(2)} km² on ${km[0].name} to ${km.at(-1).meta.playable_km2.toFixed(2)} km² on ${km.at(-1).name}.`,
  ));
  // the map and camo level on screen
  const key = $('map-pick') && $('map-pick').value, m = maps.find(x => x.key === key), ci = pressed('map-camo');
  if (!m || ci < 0) return show(panel('maps'), 'f', []);
  const sp = m.meta.spots[String(ci)] || [], b = sp.filter(s => s.kind === 'bush'), o = sp.filter(s => s.kind === 'open'), c = m.meta.camos[ci];
  const B1 = b.length && b.reduce((x, y) => (y.ratio > x.ratio ? y : x)), O1 = o.length && o.reduce((x, y) => (y.sees_m2 > x.sees_m2 ? y : x));
  show(panel('maps'), 'f', items(
    () => B1 ? `On ${m.name} at ${c}% camo the best behind-bush spot spots ${B1.ratio}× more ground than it is spotted from (${n1(B1.sees_m2 / 1e4)} ha against ${n1(B1.seen_m2 / 1e4)} ha).` : `${m.name} has no behind-bush spots at ${c}% camo.`,
    () => O1 ? `The best overlook spots ${n1(O1.sees_m2 / 1e4)} ha and sits ${O1.height_m >= 0 ? O1.height_m + ' m above' : -O1.height_m + ' m below'} the map's median ground.` : null,
    () => `At ${c}% camo you are spotted from ${Math.round(m.meta.rules.vision_m * (1 - c / 100))} m; ${m.name} has ${m.meta.bushes.length} bushes and ${n1(m.meta.playable_km2 * 100)} ha of playable ground.`,
  ));
}).catch(e => console.warn('map findings skipped:', e)));

run(TA.page);
})();
