"""Carry callout names from a previous segmentation (regions_v1.npy + callouts_v1.json) onto the current regions.

A new region takes the old name it overlaps most (if that overlap covers >= 40% of the new region). If two new regions
want one name, the larger overlap keeps it. Regions holding a spawn become "A Spawn"/"B Spawn". Anything left is
named "Unnamed <id>" and listed so it can be named by hand. Writes extract/maps/<map>/callouts.json.
"""
import json, os, sys
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')

def carry(name):
    d = os.path.join(ROOT, 'extract/maps', name)
    new = np.load(os.path.join(d, 'regions.npy')); old = np.load(os.path.join(d, 'regions_v1.npy'))
    R = json.load(open(os.path.join(d, 'regions.json')))['regions']
    oldnames = {c['id']: c for c in json.load(open(os.path.join(d, 'callouts_v1.json')))['callouts']}
    h = min(new.shape[0], old.shape[0]); w = min(new.shape[1], old.shape[1])
    new_, old_ = new[:h, :w], old[:h, :w]
    claims = {}
    for r in R:
        m = new_ == r['id']
        if not m.any(): continue
        ids, cnt = np.unique(old_[m], return_counts=True)
        keep = ids >= 0
        if not keep.any(): continue
        ids, cnt = ids[keep], cnt[keep]
        k = int(np.argmax(cnt)); share = cnt[k] / m.sum()
        if share >= 0.4 and int(ids[k]) in oldnames:
            claims.setdefault(oldnames[int(ids[k])]['name'], []).append((cnt[k], r['id'], oldnames[int(ids[k])]['why']))
    named = {}
    for nm, lst in claims.items():
        lst.sort(reverse=True); _, rid, why = lst[0]; named[rid] = (nm, why, 'carried')
    out, todo = [], []
    for r in R:
        if r['id'] in named:
            nm, why, how = named[r['id']]
        else:
            sp = next((c for c in r['contains'] if c.get('kind') == 'spawn'), None)
            if sp: nm, why, how = f"{sp['team']} Spawn", f"{sp['team']} team spawn dome", 'spawn'
            else: nm, why, how = f"Unnamed {r['id']}", '', 'todo'; todo.append(r['id'])
        out.append(dict(id=r['id'], name=nm, why=why, source=how))
    names = [o['name'] for o in out]
    dup = {n for n in names if names.count(n) > 1}
    json.dump(dict(map=name, callouts=out), open(os.path.join(d, 'callouts.json'), 'w'), indent=1)
    print(f"{name}: {len(R)} regions, {sum(o['source'] == 'carried' for o in out)} carried, unnamed {todo}, duplicates {sorted(dup)}")
    return todo

if __name__ == '__main__':
    for n in sys.argv[1:]: carry(n)
