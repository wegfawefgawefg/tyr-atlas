"""Per tank: core-maxed stats at 31 points, minimum points needed to reach them, free points; global dominance across tanks."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import optimize as O
objs = ['dps', 'alpha', 'hp', 'speed']
rows = []
for tag, t in O.D['tanks'].items():
    F = O.front(t, objs, 31)
    ideal = [max(r[0][i] for r in F) for i in range(len(objs))]
    hit = lambda FF: any(all(abs(a - b) < 1e-9 for a, b in zip(r[0], ideal)) for r in FF)
    if hit(F):
        need = next(B for B in range(0, 32) if hit(O.front(t, objs, B)))
        rows.append((t['name'], t['cls'], t['wip'], ideal, need))
    else:
        print('TRADEOFF', t['name'], 'front size', len(F))
        for r in F: print('   ', [round(x, 1) for x in r[0]], r[2])
        rows.append((t['name'], t['cls'], t['wip'], ideal, -1))
dominated = {r[0]: [s[0] for s in rows if s is not r and all(x >= y for x, y in zip(s[3], r[3])) and s[3] != r[3]] for r in rows}
print(f"{'tank':10s} {'class':11s} {'dps':>6s} {'alpha':>6s} {'hp':>6s} {'speed':>6s}  need free  dominated by")
for n, c, w, b, need in sorted(rows, key=lambda r: -r[3][0]):
    print(f"{n + ('*' if w else ''):10s} {c:11s} {b[0]:6.1f} {b[1]:6.0f} {b[2]:6.0f} {b[3]:6.1f}  {need:4d} {31-need:4d}  {', '.join(dominated[n])}")
json.dump([dict(name=n, cls=c, wip=w, dps=b[0], alpha=b[1], hp=b[2], speed=b[3], points_needed=need) for n, c, w, b, need in rows],
          open(os.path.join(O.ROOT, 'data/core_maxed.json'), 'w'), indent=1)
