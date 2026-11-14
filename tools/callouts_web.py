"""Export callouts for the Maps page: site/maps/<map>/callouts.json + regions.png.

regions.png is a transparent image the size of base.jpg holding the region borders. callouts.json lists each region's
name, reason, side, area and a label anchor in base.jpg pixels (the point deepest inside the region).
Region cells are 2x2 spotting-grid cells with the same origin (tools/callouts.py, F = 2); base.jpg is the spotting grid
cropped to the playable area plus 40 m and flipped vertically (tools/maplos.py export_web).
usage: python3 -I tools/callouts_web.py Fields Divide ...
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, os.path.dirname(__file__))
import maplos as ML
import callouts as CO

ROOT = os.path.join(os.path.dirname(__file__), '..')
ZWORD = {'Cap': 'CaptureZone', 'Heal': 'HealZone', 'Ammo': 'AmmunitionZone', 'Energy': 'AbilityResourceZone'}

def export(name):
    d, ground, dsm, bushm, play, meta = ML.prepare(name)
    H, W = ground.shape; res = meta['res']; F = CO.F
    ys, xs = np.where(play); m = int(40 / res)
    y0, y1, x0, x1 = max(0, ys.min() - m), min(H, ys.max() + m), max(0, xs.min() - m), min(W, xs.max() + m)
    reg = np.load(os.path.join(d, 'regions.npy'))
    lab = np.full((H, W), -1, np.int32)
    up = np.repeat(np.repeat(reg, F, 0), F, 1)
    lab[:up.shape[0], :up.shape[1]] = up[:H, :W]
    lab[~play] = -1
    names = {c['id']: c for c in json.load(open(os.path.join(d, 'callouts.json')))['callouts']}
    R = {r['id']: r for r in json.load(open(os.path.join(d, 'regions.json')))['regions']}
    cl = lab[y0:y1, x0:x1][::-1]
    # borders between two named regions only (obstacle outlines would clutter the map)
    edge = np.zeros(cl.shape, bool)
    edge[:, :-1] |= (cl[:, :-1] != cl[:, 1:]) & (cl[:, :-1] >= 0) & (cl[:, 1:] >= 0)
    edge[:-1, :] |= (cl[:-1, :] != cl[1:, :]) & (cl[:-1, :] >= 0) & (cl[1:, :] >= 0)
    rgba = np.zeros(cl.shape + (4,), np.uint8); rgba[edge] = (255, 255, 255, 200)
    out = os.path.join(ROOT, 'site/maps', name.lower())
    Image.fromarray(rgba, 'RGBA').save(os.path.join(out, 'regions.png'), optimize=True)
    # zones in base.jpg pixels (same transform as maplos.export_web's to_px)
    zpx = [(int(round(z['x'] - x0)), int(round(y1 - 1 - z['y']))) for z in meta['zones']]
    items = []
    for rid, c in names.items():
        mk = cl == rid
        if not mk.any(): continue
        dt = distance_transform_edt(np.pad(mk, 1))[1:-1, 1:-1]
        py, px = np.unravel_index(np.argmax(dt), dt.shape)
        # a region holding a zone gets its label next to the zone ring (10-30 px off it, well inside the region)
        zs = [(zx, zy) for zx, zy in zpx if 0 <= zy < cl.shape[0] and 0 <= zx < cl.shape[1] and cl[zy, zx] == rid]
        r = R.get(rid, {})
        if r.get('area_m2', 1e9) < 2000 and not r.get('neighbours'): continue     # cut-off speck (e.g. Divide's east energy pad): its neighbour carries the name
        word = next((w for w in ZWORD if w in c['name']), None)
        if not zs and word:         # named after a zone that sits on a cut-off speck next to it: label beside that zone
            near = [(zx, zy) for (zx, zy), z in zip(zpx, meta['zones']) if z['kind'] == ZWORD[word]]
            near = [q for q in near if np.hypot(q[0] - px, q[1] - py) < 120]
            zs = near[:1]
        if not zs and c['name'].endswith('Spawn'):   # spawn regions: label at the spawn end, not mid-strip
            sp = [(int(round(x - x0)), int(round(y1 - 1 - y))) for x, y in meta['spawns']]
            zs = sorted(sp, key=lambda q: np.hypot(q[0] - px, q[1] - py))[:1]
        if zs:
            zx, zy = zs[0]; yy, xx = np.indices(cl.shape); dz = np.hypot(xx - zx, yy - zy)
            ok = (dt >= min(8, dt.max() * 0.6)) & (dz >= 12) & mk
            if ok.any():
                py, px = np.unravel_index(np.argmin(np.where(ok, dz, np.inf)), dt.shape)
        items.append(dict(id=rid, name=c['name'], why=c['why'], side=r.get('side'), area_m2=r.get('area_m2'),
                          height_m=r.get('height_m'), px=[int(px), int(py)]))
    json.dump(dict(map=name, size=[int(x1 - x0), int(y1 - y0)], callouts=items), open(os.path.join(out, 'callouts.json'), 'w'), indent=1)
    print(name, len(items), 'callouts', cl.shape[::-1])

if __name__ == '__main__':
    for n in sys.argv[1:]: export(n)
