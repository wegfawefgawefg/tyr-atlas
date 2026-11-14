"""Exact Pareto fronts of talent builds per tank (budget B points) over chosen objectives.

DP over tiers: state = (points spent, maxed prerequisite nodes) -> set of channel vectors (Pareto-pruned).
Channels = per-(attribute, op) sums of unconditional (LoadoutApplied) talent effects, oriented so bigger is better.
Every objective is monotone non-decreasing in every oriented channel, so channel-dominance pruning is exact.
GAS aggregation: (base + sum add) * (1 + sum(mult - 1)) / (1 + sum(div - 1)) * prod(compound).
"""
import json, itertools, sys, os
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
D = json.load(open(os.path.join(ROOT, 'data/tyr.json')))
E = D['effects']
LOWER_BETTER = {'ReloadTime', 'AbilityCost', 'AbilityCooldownTwo', 'BaseDispersionPenalty', 'MovementDispersionPenalty',
                'FiringDispersionPenalty', 'HullTraverseDispersionPenalty', 'TurretTraverseDispersionPenalty',
                'ShellSwapTime', 'IntraClipReloadTime', 'AccelerationTime', 'ModuleRepairTimeMultiplier',
                'PreciseDispersionTime', 'SpottedTime'}
UNCONDITIONAL = {'LoadoutApplied', 'Direct'}

def node_channels(node):
    """list over k=1..max of {channel: oriented value}; plus flags for conditional/behaviour effects"""
    per_k = []; notes = set()
    for k in range(1, node['max'] + 1):
        ch = {}
        for ef in node['effects']:
            g = E.get(ef['ge']) if ef['ge'] else None
            if ef['event'] not in UNCONDITIONAL or not g or not g.get('mods'):
                notes.add('conditional' if g and g.get('mods') else 'behaviour'); continue
            for attr, op, mag in g['mods']:
                if mag != 'TyrTalentMagCalculation':
                    notes.add('fixed-mag'); continue
                vals = node['values'] or []
                if not vals: continue
                v = vals[min(k, len(vals)) - 1]
                sign = -1 if attr in LOWER_BETTER else 1
                if op == 'Additive': c, x = (attr, 'add'), v
                elif op == 'Multiplicitive': c, x = (attr, 'mul'), v - 1
                elif op == 'MultiplyCompound': c, x = (attr, 'cmp'), np.log(v)
                elif op == 'Division': c, x = (attr, 'div'), v - 1; sign = -sign
                else: notes.add('override'); continue
                ch[c] = ch.get(c, 0) + sign * x
        per_k.append(ch)
    return per_k, notes

def stat(base, chan, attr):
    """final attribute from oriented channel sums"""
    s = -1 if attr in LOWER_BETTER else 1
    add = s * chan.get((attr, 'add'), 0); mul = s * chan.get((attr, 'mul'), 0)
    div = -s * chan.get((attr, 'div'), 0); cmp = s * chan.get((attr, 'cmp'), 0)
    return (base.get(attr, 0) + add) * (1 + mul) / (1 + div) * np.exp(cmp)

def reload_cycle(st):
    clip = max(1, st['ClipSize'])
    return st['ReloadTime'] + (clip - 1) * st['IntraClipReloadTime']

OBJECTIVES = {
    'alpha':  (['ShellDamage'], lambda st: st['ShellDamage']),
    'dps':    (['ShellDamage', 'ReloadTime', 'IntraClipReloadTime'], lambda st: st['ShellDamage'] * max(1, st['ClipSize']) / reload_cycle(st)),
    'hp':     (['MaxHealth'], lambda st: st['MaxHealth']),
    'speed':  (['MaxSpeed'], lambda st: st['MaxSpeed']),
    'camo':   (['CamoPercentage'], lambda st: st['CamoPercentage']),
    'ability_cost': (['AbilityCost'], lambda st: -st['AbilityCost']),
    'start_energy': (['InitialAbilityResource'], lambda st: st['InitialAbilityResource']),
}

def pareto_mask(V):
    """non-dominated rows of V (maximize all); exact duplicates keep the first"""
    n = len(V)
    if n <= 1: return np.ones(n, bool)
    order = np.argsort(-V.sum(1), kind='stable'); V2 = V[order]
    keep = np.ones(n, bool)
    for i in range(n):
        if not keep[i]: continue
        dom = np.all(V2[i] >= V2, axis=1)
        dom[: i + 1] = False
        keep &= ~dom
    m = np.zeros(n, bool); m[order[keep]] = True
    return m

def front(tank, objectives, B=31):
    tree = tank['tree']; ppt = tree['meta']['points_per_tier_required']
    attrs = sorted({a for o in objectives for a in OBJECTIVES[o][0]})
    nodes = tree['nodes']
    info = {n['tag']: node_channels(n) for n in nodes}
    chans = sorted({c for n in nodes for ch in info[n['tag']][0] for c in ch if c[0] in attrs})
    ci = {c: i for i, c in enumerate(chans)}
    prereq_tags = {p for n in nodes for p in n['prereq']}
    tiers = {}
    for n in nodes: tiers.setdefault(n['tier'], []).append(n)
    T = max(tiers) + 1
    def vec(n, k):
        v = np.zeros(len(chans))
        if k:
            for c, x in info[n['tag']][0][k - 1].items():
                if c in ci: v[ci[c]] += x
        return v
    # tier options: (used, maxed, vec, alloc)
    def tier_opts(t, maxed_prev):
        ns = tiers.get(t, [])
        out = []
        for ks in itertools.product(*[range(n['max'] + 1) for n in ns]):
            maxed = {n['tag'] for n, k in zip(ns, ks) if k == n['max'] and n['tag'] in prereq_tags}
            if any(k and not all(p in maxed_prev or p in maxed for p in n['prereq']) for n, k in zip(ns, ks)): continue
            v = sum((vec(n, k) for n, k in zip(ns, ks)), np.zeros(len(chans)))
            out.append((sum(ks), frozenset(maxed), v, tuple((n['tag'], k) for n, k in zip(ns, ks) if k)))
        return out
    states = {(0, frozenset()): [(np.zeros(len(chans)), ())]}
    for t in range(T):
        new = {}
        cache = {}
        for (spent, maxed), lst in states.items():
            if maxed not in cache: cache[maxed] = tier_opts(t, maxed)
            for used, m, v, alloc in cache[maxed]:
                if used and spent < ppt * t: continue
                if spent + used > B: continue
                key = (spent + used, maxed | m)
                bucket = new.setdefault(key, [])
                for pv, pa in lst: bucket.append((pv + v, pa + alloc))
        # prune each bucket on channel vectors; also prune across buckets with same maxed set and less spent? (more spent never hurts later)
        states = {}
        for key, lst in new.items():
            V = np.array([x[0] for x in lst]) if chans else np.zeros((len(lst), 0))
            if len(chans):
                m = pareto_mask(V); lst = [x for x, keep in zip(lst, m) if keep]
            else: lst = lst[:1]
            states[key] = lst
    base = tank['stats']
    rows = []
    for (spent, _), lst in states.items():
        for v, alloc in lst:
            ch = {c: v[i] for c, i in ci.items()}
            st = dict(base); st.update({a: stat(base, ch, a) for a in attrs})
            rows.append(([OBJECTIVES[o][1](st) for o in objectives], spent, alloc, {a: st[a] for a in attrs}))
    V = np.array([r[0] for r in rows])
    m = pareto_mask(np.round(V, 9))
    return [r for r, k in zip(rows, m) if k]

if __name__ == '__main__':
    import time
    objs = sys.argv[1].split(',') if len(sys.argv) > 1 else ['dps', 'alpha', 'hp', 'speed']
    B = int(sys.argv[2]) if len(sys.argv) > 2 else 31
    names = {n['tag']: n['name'] for t in D['tanks'].values() for n in t['tree']['nodes']}
    for tag, tank in D['tanks'].items():
        t0 = time.time(); F = front(tank, objs, B)
        print(f"{tank['name']:10s} front={len(F):5d}  {time.time()-t0:5.1f}s  base " +
              ' '.join(f"{o}={OBJECTIVES[o][1](tank['stats']):.1f}" for o in objs))
        for o_i, o in enumerate(objs):
            best = max(F, key=lambda r: r[0][o_i])
            print(f"   max {o:6s} -> " + ' '.join(f"{p}={x:.1f}" for p, x in zip(objs, best[0])) +
                  '  | ' + ', '.join(f"{names[a]} {k}" for a, k in best[2] if a in names))
