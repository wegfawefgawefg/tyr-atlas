"""Count valid talent allocations per tank for a point budget (tier rule: points in lower tiers >= 5*tier;
prereqs must be maxed). Counts allocations using exactly B points and <= B points."""
import json, sys, functools
D = json.load(open('data/tyr.json'))
def count(tree, B):
    ppt = tree['meta']['points_per_tier_required']
    tiers = {}
    for n in tree['nodes']: tiers.setdefault(n['tier'], []).append(n)
    T = max(tiers) + 1
    # per tier: distribution of (points used) -> number of ways, honoring intra-tier prereqs (prereq in same or earlier tier)
    # prereqs across tiers handled by tracking maxed-set is costly; check: are all prereqs one tier up?
    def tier_ways(t, maxed_prev):
        nodes = tiers.get(t, [])
        ways = {}
        def rec(i, used, maxed):
            if i == len(nodes):
                ways.setdefault(used, []).append(frozenset(maxed)); return
            n = nodes[i]
            ok = all(p in maxed_prev or p in maxed for p in n['prereq'])
            rec(i + 1, used, maxed)
            if ok:
                for k in range(1, n['max'] + 1):
                    rec(i + 1, used + k, maxed | ({n['tag']} if k == n['max'] else set()))
        rec(0, 0, set())
        return ways
    @functools.lru_cache(None)
    def go(t, spent, maxed):
        if t == T: return {spent: 1}
        res = {}
        unlocked = spent >= ppt * t
        for used, ms in tier_ways(t, maxed).items():
            if used and not unlocked: continue
            if spent + used > B: continue
            for m in ms:
                for k, v in go(t + 1, spent + used, maxed | m).items(): res[k] = res.get(k, 0) + v
        return res
    r = go(0, 0, frozenset())
    return r.get(B, 0), sum(r.values())
for B in map(int, sys.argv[1:]):
    tot = 0
    for tag, t in D['tanks'].items():
        e, le = count(t['tree'], B); tot += le
        print(f"B={B:2d} {t['name']:10s} exactly={e:>14,} atmost={le:>14,}")
    print('total', f'{tot:,}')
