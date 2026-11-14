"""All 3-component loadouts per tank per scenario on the core talent build; fronts, synergy, outliers -> data/loadouts.json"""
import json, os, sys, math, itertools, time
sys.path.insert(0, os.path.dirname(__file__))
import components as C
import numpy as np
from optimize import pareto_mask

out = dict(ref=C.REF, scenarios={k: {kk: vv for kk, vv in v.items() if kk != 'flags'} | {'flags': sorted(v['flags'])} for k, v in C.SCENARIOS.items()},
           components={c: dict(name=C.COMP['Gameplay.Components.' + c]['name'].title(), desc=C.COMP['Gameplay.Components.' + c]['desc'],
                               cats=C.COMP['Gameplay.Components.' + c]['categories'], value=C.COMP['Gameplay.Components.' + c]['values'][0],
                               scored=c not in C.NOT_SCORED) for c in C.COMP_IDS},
           tanks={})
pairs = list(itertools.combinations(C.COMP_IDS, 2))
triples = list(itertools.combinations(C.COMP_IDS, 3))
syn_all = []
for tag, tank in C.D['tanks'].items():
    t0 = time.time()
    alloc = C.core_alloc(tank)
    T = dict(single={}, fronts={}, best={}, synergy=[])
    for scen in C.SCENARIOS:
        base = C.evaluate(tank, alloc, [], scen)
        single = {c: C.evaluate(tank, alloc, [c], scen) for c in C.COMP_IDS}
        T['single'][scen] = {'_base': {k: base[k] for k in ('dps', 'alpha', 'ehp', 'speed', 'duel', 'uses', 'reload', 'camo')},
                             **{c: {k: single[c][k] for k in ('dps', 'alpha', 'ehp', 'speed', 'duel', 'uses', 'reload', 'camo')} for c in C.COMP_IDS}}
        # pair synergy on log duel score (0 = independent; >0 = they amplify each other)
        if scen != 'static':
            lb = math.log(base['duel'])
            for a, b in pairs:
                m = C.evaluate(tank, alloc, [a, b], scen)
                s = math.log(m['duel']) - math.log(single[a]['duel']) - math.log(single[b]['duel']) + lb
                if abs(s) > 0.005:
                    T['synergy'].append(dict(scen=scen, a=a, b=b, syn=s, gain=m['duel'] / base['duel'] - 1))
        rows = []
        for tri in triples:
            m = C.evaluate(tank, alloc, list(tri), scen)
            rows.append((tri, m))
        V = np.array([[m['dps'], m['ehp'], m['speed']] for _, m in rows])
        mask = pareto_mask(np.round(V, 6))
        front = [dict(comps=list(t), dps=m['dps'], ehp=m['ehp'], speed=m['speed'], alpha=m['alpha'], duel=m['duel'])
                 for (t, m), k in zip(rows, mask) if k]
        T['fronts'][scen] = front
        # distributions over all loadouts: duel gain histogram and a DPS x EHP density grid
        g = np.array([m['duel'] / base['duel'] - 1 for _, m in rows])
        h, edges = np.histogram(g, bins=48)
        T.setdefault('hist', {})[scen] = dict(counts=h.tolist(), lo=float(edges[0]), hi=float(edges[-1]),
                                              p50=float(np.median(g)), p90=float(np.percentile(g, 90)), max=float(g.max()))
        H2, xe, ye = np.histogram2d(V[:, 0], V[:, 1], bins=36)
        T.setdefault('grid', {})[scen] = dict(counts=H2.astype(int).tolist(), x=[float(xe[0]), float(xe[-1])], y=[float(ye[0]), float(ye[-1])],
                                              base=[base['dps'], base['ehp']])
        bd = max(rows, key=lambda r: r[1]['duel'])
        T['best'][scen] = dict(comps=list(bd[0]), **{k: bd[1][k] for k in ('dps', 'alpha', 'ehp', 'speed', 'duel', 'uses')}, gain=bd[1]['duel'] / base['duel'] - 1)
    T['synergy'].sort(key=lambda s: -s['syn'])
    syn_all += [dict(tank=tank['name'], **s) for s in T['synergy'][:10]]
    out['tanks'][tank['name']] = T
    print(f"{tank['name']:9s} fronts " + ' '.join(f"{s}={len(T['fronts'][s])}" for s in C.SCENARIOS) +
          f" | best brawl {T['best']['brawling']['comps']} {T['best']['brawling']['gain']:+.0%} | {time.time()-t0:.0f}s", flush=True)
# tank-specific outliers: value of a component on a tank vs its median value across tanks (same scenario)
outl = []
for scen in C.SCENARIOS:
    for c in C.COMP_IDS:
        vals = {n: T['single'][scen][c]['duel'] / T['single'][scen]['_base']['duel'] - 1 for n, T in out['tanks'].items()}
        med = float(np.median(list(vals.values())))
        for n, v in vals.items():
            if v - med > 0.04: outl.append(dict(scen=scen, comp=c, tank=n, gain=v, median=med))
out['outliers'] = sorted(outl, key=lambda o: -(o['gain'] - o['median']))
out['synergy_top'] = sorted(syn_all, key=lambda s: -s['syn'])[:60]
json.dump(out, open(os.path.join(C.ROOT, 'data/loadouts.json'), 'w'))
open(os.path.join(C.ROOT, 'site/loadouts.js'), 'w').write('window.TYR_LOAD = ' + json.dumps(out, separators=(',', ':')) + ';\n')
print('\nTOP SYNERGIES')
for s in out['synergy_top'][:20]: print(f"  {s['tank']:9s} {s['scen']:9s} {s['a']} + {s['b']}: synergy {s['syn']:+.3f}  pair gain {s['gain']:+.0%}")
print('TOP OUTLIERS')
for o in out['outliers'][:20]: print(f"  {o['tank']:9s} {o['scen']:9s} {o['comp']}: {o['gain']:+.0%} vs median {o['median']:+.0%}")
