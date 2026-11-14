"""Split each map's playable area into callout regions and describe them for naming.

Seeds: capture/heal/ammo/energy zones, spawns, named landmarks (level instances and landmark meshes), large structure
clusters, terrain peaks and basins. Each playable cell joins the seed it can reach most cheaply along the ground
(Dijkstra on a 4 m grid; climbing and steep slopes cost extra, so ridges and walls become borders). Small regions merge
into their neighbours. Output: extract/maps/<map>/regions.json (+ regions.npy) and extract/maps/png/<map>_regions.png.
"""
import json, os, sys, re, importlib.util
import numpy as np
from scipy.ndimage import label, maximum_filter, minimum_filter, gaussian_filter, binary_dilation
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(__file__), '..')
spec = importlib.util.spec_from_file_location('maplos', os.path.join(os.path.dirname(__file__), 'maplos.py'))
ML = importlib.util.module_from_spec(spec); spec.loader.exec_module(ML)
F = 2                                  # 2 m analysis cells -> 4 m region cells
MIN_AREA_M2 = 12000
LANDMARK_WORDS = ['CrashedSpaceShip', 'CommSpires', 'DragonTeeth', 'Rotunda', 'Bridge', 'WallSection', 'RidgeWall', 'Crystals', 'Tower',
                  'Disk', 'Building', 'BrokenWall', 'LavaTube', 'GroundCracks', 'Windmills', 'Pillars', 'CenterStructures', 'Structures',
                  'BigTree', 'VistaBuilding', 'Spires', 'Ship', 'Ramp', 'Arch']

def landmarks(name):
    d = os.path.join(ROOT, 'extract/maps', name)
    m = json.load(open(os.path.join(d, 'map.json')))
    out = []
    for li in m['levelInstances']:
        nm = re.sub(r'_C_UAID.*|_UAID.*', '', li['owner'] or '')
        word = next((w for w in LANDMARK_WORDS if w.lower() in nm.lower()), None)
        if word: out.append(dict(kind='landmark', word=word, src=nm, x=li['xf']['t'][0], y=li['xf']['t'][1], z=li['xf']['t'][2]))
    for p in m['placements']:
        if 'inst' in p: continue
        nm = p['mesh'].split('/')[-1].split('.')[0]
        if 'Collision_Proxy' in nm: continue
        word = next((w for w in ('Tower', 'Disk', 'Bridge', 'Windmill', 'BigTree', 'LavaTube', 'Big_Building', 'Big_Pillar', 'ThrusterFront', 'Turret_Base') if w.lower() in nm.lower()), None)
        if word: out.append(dict(kind='landmark', word=word.replace('_', ''), src=nm, x=p['xf']['t'][0], y=p['xf']['t'][1], z=p['xf']['t'][2]))
    return out

def build(name):
    d, ground, dsm, bushm, play, meta = ML.prepare(name)
    res = meta['res'] * F
    H0, W0 = ground.shape; H, W = H0 // F, W0 // F
    g = ground[:H * F, :W * F].reshape(H, F, W, F).mean((1, 3))
    struct = (dsm - ground)[:H * F, :W * F].reshape(H, F, W, F).max((1, 3)) > 1.5
    pl = play[:H * F, :W * F].reshape(H, F, W, F).mean((1, 3)) > 0.5
    bush = bushm[:H * F, :W * F].reshape(H, F, W, F).max((1, 3))
    ox, oy = meta['origin']
    cellxy = lambda x, y: (int((x - ox) / 100 / res), int((y - oy) / 100 / res))
    seeds = []
    def add(kind, cx, cy, **kw):
        if 0 <= cx < W and 0 <= cy < H and pl[cy, cx]: seeds.append(dict(kind=kind, cx=cx, cy=cy, **kw))
        elif 0 <= cx < W and 0 <= cy < H:   # snap to the nearest playable cell (30 m; 80 m for spawns)
            r = int((80 if kind == 'spawn' else 30) / res); ys, xs = np.where(pl[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1])
            if len(ys):
                k = np.argmin((ys - min(cy, r)) ** 2 + (xs - min(cx, r)) ** 2)
                seeds.append(dict(kind=kind, cx=int(max(0, cx - r) + xs[k]), cy=int(max(0, cy - r) + ys[k]), **kw))
    for z in meta['zones']:
        add('zone', int(z['x'] / F), int(z['y'] / F), zone=z['kind'])
    sp = np.array(meta['spawns']) / F
    if len(sp):
        # two teams: split spawns by the larger axis
        ax = int(np.ptp(sp[:, 0]) < np.ptp(sp[:, 1]))
        mid = np.median(sp[:, ax])
        for team, sel in (('A', sp[:, ax] < mid), ('B', sp[:, ax] >= mid)):
            c = sp[sel].mean(0); add('spawn', int(c[0]), int(c[1]), team=team)
    for lm in landmarks(name):
        cx, cy = cellxy(lm['x'], lm['y']); add('landmark', cx, cy, word=lm['word'], src=lm['src'])
    sm = gaussian_filter(g, 3)
    r = int(60 / res)
    peaks = (sm == maximum_filter(sm, size=2 * r + 1)) & pl & (sm - gaussian_filter(sm, 15) > 6)
    pits = (sm == minimum_filter(sm, size=2 * r + 1)) & pl & (gaussian_filter(sm, 15) - sm > 6)
    for kind, mask in (('peak', peaks), ('pit', pits)):
        for cy, cx in zip(*np.where(mask)): add(kind, int(cx), int(cy))
    lab, n = label(struct & binary_dilation(pl, iterations=3))
    for k in range(1, n + 1):
        ys, xs = np.where(lab == k)
        if len(ys) * res * res >= 3000: add('structure', int(xs.mean()), int(ys.mean()), size_m2=float(len(ys) * res * res))
    # dedupe seeds closer than 35 m (keep the more important kind)
    order = {'zone': 0, 'spawn': 1, 'landmark': 2, 'structure': 3, 'peak': 4, 'pit': 5}
    seeds.sort(key=lambda s: order[s['kind']])
    kept = []
    for s in seeds:
        if all((s['cx'] - k['cx']) ** 2 + (s['cy'] - k['cy']) ** 2 > (70 / res) ** 2 for k in kept): kept.append(s)
    seeds = kept
    # graph over playable cells: cost = distance * (1 + climb + slope)
    idx = -np.ones((H, W), int); ys, xs = np.where(pl); idx[ys, xs] = np.arange(len(ys))
    rows, cols, wts = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        a = idx[max(0, -dy):H - max(0, dy), max(0, -dx):W - max(0, dx)]
        b = idx[max(0, dy):, max(0, dx):][:a.shape[0], :a.shape[1]] if dx >= 0 else idx[dy:, :W + dx][:a.shape[0], :a.shape[1]]
        ga = g[max(0, -dy):H - max(0, dy), max(0, -dx):W - max(0, dx)]
        gb = g[max(0, dy):, max(0, dx):][:a.shape[0], :a.shape[1]] if dx >= 0 else g[dy:, :W + dx][:a.shape[0], :a.shape[1]]
        sa = struct[max(0, -dy):H - max(0, dy), max(0, -dx):W - max(0, dx)]
        ok = (a >= 0) & (b >= 0)
        dist = res * (1.414 if dx and dy else 1.0)
        dz = np.abs(gb - ga)
        w = dist * (1 + 3 * dz / dist + 2 * sa)
        rows.append(a[ok]); cols.append(b[ok]); wts.append(w[ok])
    rows, cols, wts = np.concatenate(rows), np.concatenate(cols), np.concatenate(wts)
    G = coo_matrix((np.concatenate([wts, wts]), (np.concatenate([rows, cols]), np.concatenate([cols, rows]))), shape=(len(ys), len(ys))).tocsr()
    src = [idx[s['cy'], s['cx']] for s in seeds]
    dist, _, srcs = dijkstra(G, directed=False, indices=src, min_only=True, return_predecessors=True)
    seed_of = {v: i for i, v in enumerate(src)}
    reg = -np.ones((H, W), int)
    reg[ys, xs] = [seed_of.get(s, -1) for s in srcs]
    # merge small regions into the neighbour they share the longest border with
    for _ in range(8):
        areas = {k: int((reg == k).sum()) * res * res for k in range(len(seeds))}
        small = [k for k, a in areas.items() if 0 < a < MIN_AREA_M2 and (seeds[k]['kind'] not in ('zone', 'spawn') or a < 1500)]
        if not small: break
        for k in small:
            m = reg == k
            if not m.any(): continue
            ring = binary_dilation(m) & ~m & (reg >= 0)
            if ring.any():
                nb = np.bincount(reg[ring]).argmax(); reg[m] = nb
    # describe regions
    used = sorted(set(reg[reg >= 0].tolist()))
    med = float(np.median(g[pl]))
    los_d = os.path.join(d)
    sees = np.fromfile(os.path.join(los_d, 'sees_3.f32'), np.float32).reshape(H0, W0) if os.path.exists(os.path.join(los_d, 'sees_3.f32')) else None
    seen = np.fromfile(os.path.join(los_d, 'seen_3.f32'), np.float32).reshape(H0, W0) if os.path.exists(os.path.join(los_d, 'seen_3.f32')) else None
    spawn_pts = {s['team']: (s['cx'], s['cy']) for s in seeds if s['kind'] == 'spawn'}
    cxm, cym = np.mean(xs), np.mean(ys)
    regions = []
    for new_id, k in enumerate(used):
        m = reg == k; rys, rxs = np.where(m)
        cx, cy = float(rxs.mean()), float(rys.mean())
        inside = [s for s in seeds if reg[s['cy'], s['cx']] == k]
        nbrs = sorted(set(reg[binary_dilation(m) & ~m & (reg >= 0)].tolist()))
        side = None
        if len(spawn_pts) == 2:
            da, db = [np.hypot(cx - p[0], cy - p[1]) for p in (spawn_pts['A'], spawn_pts['B'])]
            side = 'A' if da < 0.8 * db else 'B' if db < 0.8 * da else 'mid'
        vis = None
        if sees is not None:
            big = np.kron(m, np.ones((F, F), bool)); big = np.pad(big, ((0, H0 - big.shape[0]), (0, W0 - big.shape[1])))
            s_ = sees[big]; s_ = s_[~np.isnan(s_)]
            vis = dict(spots_ha=round(float(s_.mean()) / 1e4, 2) if len(s_) else None, spotted_by=round(float(seen[big].mean()), 1))
        ang = np.degrees(np.arctan2(cy - cym, cx - cxm))
        compass = ['east', 'north-east', 'north', 'north-west', 'west', 'south-west', 'south', 'south-east'][int(((ang + 22.5) % 360) // 45)]
        regions.append(dict(id=new_id, seed=k, area_m2=int(m.sum() * res * res), centre=[round(cx, 1), round(cy, 1)], compass=compass,
                            dist_from_centre_m=round(float(np.hypot(cx - cxm, cy - cym) * res)), side=side,
                            height_m=round(float(g[m].mean() - med), 1), relief_m=round(float(np.ptp(g[m])), 1),
                            structure_share=round(float(struct[m].mean()), 2), bushes=int(bush[m].sum() * res * res / 30),
                            contains=[{kk: v for kk, v in s.items() if kk not in ('cx', 'cy')} for s in inside], neighbours=[used.index(n) for n in nbrs if n in used],
                            sight=vis))
    remap = {k: i for i, k in enumerate(used)}
    out = np.vectorize(lambda v: remap.get(v, -1))(reg).astype(np.int16)
    np.save(os.path.join(d, 'regions.npy'), out)
    json.dump(dict(map=name, res_m=res, shape=[H, W], origin=meta['origin'], regions=regions), open(os.path.join(d, 'regions.json'), 'w'), indent=1)
    # picture: hillshade + region borders + ids
    gy, gx = np.gradient(g); shade = np.clip(0.55 + (gx * -0.6 + gy * -0.6) * 0.25, 0.15, 1)
    img = np.stack([shade * 0.6] * 3, -1); img[struct] = [0.45, 0.32, 0.25]; img[bush] = [0.2, 0.45, 0.2]
    edge = np.zeros_like(pl); edge[:-1] |= out[:-1] != out[1:]; edge[:, :-1] |= out[:, :-1] != out[:, 1:]
    img[edge & pl] = [1, 1, 1]; img[~pl] *= 0.45
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)[::-1]).resize((W * 3, H * 3), Image.NEAREST)
    dr = ImageDraw.Draw(im)
    for r_ in regions:
        x, y = r_['centre'][0] * 3, (H - 1 - r_['centre'][1]) * 3
        dr.rectangle([x - 9, y - 7, x + 9, y + 7], fill=(0, 0, 0)); dr.text((x - 7, y - 6), str(r_['id']), fill=(255, 255, 255))
    for s in seeds:
        if s['kind'] in ('zone', 'spawn'):
            x, y = s['cx'] * 3, (H - 1 - s['cy']) * 3
            col = {'zone': (255, 210, 0), 'spawn': (255, 80, 80)}[s['kind']]
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], outline=col, width=2)
    os.makedirs(os.path.join(ROOT, 'extract/maps/png'), exist_ok=True)
    im.save(os.path.join(ROOT, 'extract/maps/png', f'{name.lower()}_regions.png'))
    print(f"{name}: {len(seeds)} seeds -> {len(regions)} regions")

if __name__ == '__main__':
    for n in sys.argv[1:]: build(n)
