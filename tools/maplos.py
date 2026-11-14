"""Spotting analysis per map: prepares grid.bin for tools/los (Rust), runs it, writes web layers to site/maps/<map>/.

Game rules used (from the game files):
  BP_TyrGameMode: MaxCamoValue 80, MaxBushCamoValue 40, GunFireCamoAddition -15, GunFireCamoScalar -0.4
  BP_VisionBlocker (bush): FoliageVision CamoPercentageIncreaseAmount 40, vision sphere 3.25 m, see-through sphere 15 m
  TankData: VisionRadius 400 on every tank, SpottedTime 7 s
  spotted when there is line of sight to any part of the tank and distance <= 400 m * (1 - camo/100)
Model assumptions (shown on the site):
  2 m cells; spotter eye at 2.5 m; target is a 2.5 m tall column; bushes do not block sight, they add camo to sight lines
  through them; playable area estimated from zones, spawns and bushes plus climbable slopes; observers every 8 m;
  results for camo 0 / 25 / 40 (heavies / mediums / scouts, before firing)
"""
import json, os, sys, struct, subprocess
import numpy as np
from scipy.ndimage import distance_transform_edt, label, grey_dilation, binary_fill_holes
from scipy.spatial import Delaunay
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
DS = 2
EYE, TGT, VISION_M, STRIDE = 2.5, 2.5, 400.0, 4
MAX_CAMO, BUSH_CAMO, BUSH_R_M, SEE_THROUGH_M = 80.0, 40.0, 3.25, 15.0
CAMOS = [0.0, 25.0, 40.0]
ZONE_KINDS = ('CaptureZone', 'HealZone', 'AmmunitionZone', 'AbilityResourceZone')

def pool(a, f, how):
    H, W = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:H, :W].reshape(H // f, f, W // f, f)
    return b.max((1, 3)) if how == 'max' else b.mean((1, 3))

def prepare(name):
    d = os.path.join(ROOT, 'extract/maps', name)
    g = json.load(open(os.path.join(d, 'grid.json'))); z = np.load(os.path.join(d, 'grid.npz'))
    res = g['res'] * DS / 100.0
    dsm = pool(z['dsm'] / 100, DS, 'max').astype(np.float32)
    bushm = pool(z['bush'].astype(np.float32), DS, 'max') > 0
    H, W = dsm.shape
    ox, oy = g['origin']
    cell = lambda o: ((o['x'] - ox) / 100 / res, (o['y'] - oy) / 100 / res)
    # tanks drive on terrain, on meshes and into bushes (bush meshes are not ground)
    ground = dsm.copy()
    if bushm.any():
        idx = distance_transform_edt(bushm, return_distances=False, return_indices=True)
        ground = ground[tuple(idx)]
    block = np.where(bushm, ground, dsm).astype(np.float32)        # bushes don't block sight
    anchors = [cell(o) for o in g['objects'] if o['kind'] in ZONE_KINDS + ('Bush', 'PlayerStart', 'SpawnWall')]
    hull = Delaunay(np.array(anchors))
    YY, XX = np.mgrid[0:H, 0:W]
    inside = (hull.find_simplex(np.stack([XX.ravel(), YY.ravel()], 1)) >= 0).reshape(H, W)
    near = distance_transform_edt(~inside) * res <= 80
    gy, gx = np.gradient(ground, res)
    walk = near & (np.degrees(np.arctan(np.hypot(gx, gy))) < 35)
    lab, _ = label(walk)
    zones = [o for o in g['objects'] if o['kind'] in ZONE_KINDS]
    keep = set(); rr = int(15 / res)
    for o in zones:
        cx, cy = int(round(cell(o)[0])), int(round(cell(o)[1]))
        keep |= set(np.unique(lab[max(0, cy - rr):cy + rr + 1, max(0, cx - rr):cx + rr + 1]).tolist())
    play = np.isin(lab, list(keep - {0}))
    zc = [(int(round(cell(o)[0])), int(round(cell(o)[1]))) for o in zones]
    bushes = [cell(o) for o in g['objects'] if o['kind'] == 'Bush']
    f32 = lambda v: struct.unpack('<I', struct.pack('<f', float(v)))[0]
    with open(os.path.join(d, 'grid.bin'), 'wb') as f:
        f.write(struct.pack('<II', W, H)); f.write(struct.pack('<I', f32(res)))
        f.write(struct.pack('<I', int(VISION_M / res))); f.write(struct.pack('<II', f32(EYE), f32(TGT))); f.write(struct.pack('<I', STRIDE))
        f.write(struct.pack('<IIIII', f32(VISION_M), f32(MAX_CAMO), f32(BUSH_CAMO), f32(BUSH_R_M), f32(SEE_THROUGH_M)))
        f.write(struct.pack('<I', len(CAMOS))); f.write(b''.join(struct.pack('<I', f32(c)) for c in CAMOS))
        f.write(struct.pack('<I', len(zc))); f.write(b''.join(struct.pack('<II', x, y) for x, y in zc))
        f.write(struct.pack('<I', len(bushes))); f.write(b''.join(struct.pack('<II', f32(x), f32(y)) for x, y in bushes))
        f.write(ground.astype(np.float32).tobytes()); f.write(block.tobytes()); f.write(play.astype(np.uint8).tobytes())
    meta = dict(map=name, res=res, shape=[H, W], origin=g['origin'], zones=[dict(kind=o['kind'], x=x, y=y) for o, (x, y) in zip(zones, zc)],
                spawns=[cell(o) for o in g['objects'] if o['kind'] == 'PlayerStart'], bushes=bushes, playable_km2=float(play.sum() * res * res / 1e6))
    return d, ground, dsm, bushm, play, meta

def export_web(name, d, ground, dsm, bushm, play, meta):
    H, W = ground.shape; res = meta['res']
    gy, gx = np.gradient(dsm)
    shade = np.clip(0.55 + (gx * -0.6 + gy * -0.6) * 0.5, 0.15, 1)
    base = np.stack([shade * 0.55, shade * 0.58, shade * 0.55], -1)
    base[(dsm - ground) > 1.5] = [0.45, 0.32, 0.25]
    base[bushm] = base[bushm] * 0.5 + np.array([0.15, 0.45, 0.15]) * 0.5
    ys, xs = np.where(play); m = int(40 / res)
    y0, y1, x0, x1 = max(0, ys.min() - m), min(H, ys.max() + m), max(0, xs.min() - m), min(W, xs.max() + m)
    out = os.path.join(ROOT, 'site/maps', name.lower()); os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        if f.endswith('.png'): os.remove(os.path.join(out, f))
    crop = lambda a: a[y0:y1, x0:x1][::-1]
    Image.fromarray((np.clip(crop(base), 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, 'base.jpg'), quality=82)
    def layer(v, mask, ramp, alpha=0.72):
        v = np.clip(v, 0, 1); rgb = np.stack([np.interp(v, [0, .5, 1], c) for c in ramp], -1)
        return Image.fromarray((np.dstack([rgb, np.where(mask, alpha, 0.0)]) * 255).astype(np.uint8), 'RGBA')
    seq = ([0.80, 0.33, 0.05], [0.89, 0.60, 0.21], [0.98, 0.91, 0.42])     # channel ramps at 0 / .5 / 1: #cde2fb #5598e7 #0d366b
    div = ([0.82, 0.62, 0.16], [0.30, 0.62, 0.47], [0.25, 0.60, 0.84])     # red - grey - blue
    to_px = lambda x, y: [round(float(x - x0), 1), round(float(y1 - 1 - y), 1)]
    inner = distance_transform_edt(binary_fill_holes(play)) * res >= 40
    bush_xy = np.array(meta['bushes']) if meta['bushes'] else np.zeros((0, 2))
    web = dict(map=name, size=[int(x1 - x0), int(y1 - y0)], m_per_px=res, camos=CAMOS,
               zones=[dict(kind=z['kind'], px=to_px(z['x'], z['y'])) for z in meta['zones']],
               spawns=[to_px(x, y) for x, y in meta['spawns']], bushes=[to_px(x, y) for x, y in meta['bushes']], playable_km2=meta['playable_km2'],
               rules=dict(vision_m=VISION_M, max_camo=MAX_CAMO, bush_camo=BUSH_CAMO, bush_radius_m=BUSH_R_M, see_through_m=SEE_THROUGH_M),
               zone_layers=[k for k, z in enumerate(meta['zones']) if z['kind'] == 'CaptureZone'], spots={})
    cell_m2 = (STRIDE * res) ** 2
    for k, camo in enumerate(CAMOS):
        sees = np.fromfile(os.path.join(d, f'sees_{k}.f32'), np.float32).reshape(H, W)
        seen = np.fromfile(os.path.join(d, f'seen_{k}.f32'), np.float32).reshape(H, W)
        obs = ~np.isnan(sees)
        s_s = grey_dilation(np.where(obs, sees, -1.0), size=(STRIDE, STRIDE)); n_s = grey_dilation(np.where(play, seen, -1.0), size=(2, 2))
        for key, v in (('sees', s_s), ('seen', n_s)):
            mk = v >= 0
            layer(crop(v / (np.percentile(v[mk], 98) + 1e-9)), crop(mk), seq).save(os.path.join(out, f'{key}_{k}.png'), optimize=True)
        oy_, ox_ = np.where(obs)
        adv = np.full((H, W), np.nan)
        adv[oy_, ox_] = np.log2((sees[oy_, ox_] + cell_m2) / (seen[oy_, ox_] * cell_m2 + cell_m2))
        a_s = grey_dilation(np.where(obs, adv, -99.0), size=(STRIDE, STRIDE)); mk = a_s > -50
        layer(crop((np.clip(a_s, -1, 1) + 1) / 2), crop(mk), div).save(os.path.join(out, f'advantage_{k}.png'), optimize=True)
        zmap = np.fromfile(os.path.join(d, f'zones_{k}.u8'), np.uint8).reshape(len(meta['zones']), H, W)
        for zi in web['zone_layers']:
            cov = grey_dilation(np.where(obs, zmap[zi].astype(float), -1.0), size=(STRIDE, STRIDE)); mk = cov > 0.5
            img = np.zeros(cov.shape + (4,)); img[mk] = [0.95, 0.75, 0.10, 0.6]
            Image.fromarray((crop(img) * 255).astype(np.uint8), 'RGBA').save(os.path.join(out, f'zone{zi}_{k}.png'), optimize=True)
        floor = np.percentile(sees[obs], 60)
        def near_bush(x, y):
            return len(bush_xy) > 0 and bool((((bush_xy[:, 0] - x) ** 2 + (bush_xy[:, 1] - y) ** 2) <= (SEE_THROUGH_M / res) ** 2).any())
        def pick(cond, nmax=8, by='adv'):
            score = (lambda x, y: adv[y, x]) if by == 'adv' else (lambda x, y: sees[y, x])
            cand = sorted(((score(x, y), x, y) for y, x in zip(oy_, ox_) if sees[y, x] >= floor and inner[y, x] and cond(x, y)), reverse=True)
            got = []
            for a, x, y in cand:
                if all((x - sx) ** 2 + (y - sy) ** 2 > (40 / res) ** 2 for _, sx, sy in got): got.append((a, x, y))
                if len(got) >= nmax: break
            return got
        spots = []
        # open ground: spotting is symmetric there, so rank overlooks by how much they see; bush spots by see/seen
        for kind, lst in (('open', pick(lambda x, y: not near_bush(x, y), by='sees')), ('bush', pick(near_bush))):
            for a, x, y in lst:
                spots.append(dict(kind=kind, px=to_px(x, y), sees_m2=round(float(sees[y, x])), seen_m2=round(float(seen[y, x]) * cell_m2),
                                  ratio=round(float(2 ** adv[y, x]), 2), height_m=round(float(ground[y, x] - np.percentile(ground[play], 50)), 1)))
        web['spots'][str(k)] = spots
        print(f"  camo {camo:>4.0f}: best open x{next((s['ratio'] for s in spots if s['kind'] == 'open'), '-')}, "
              f"best near-bush x{next((s['ratio'] for s in spots if s['kind'] == 'bush'), '-')}")
    json.dump(web, open(os.path.join(out, 'meta.json'), 'w'))

if __name__ == '__main__':
    exe = os.path.join(ROOT, 'tools/los/target/release/los')
    for name in sys.argv[1:]:
        d, ground, dsm, bushm, play, meta = prepare(name)
        r = subprocess.run(['nice', '-n', '19', exe, d], capture_output=True, text=True, env=dict(os.environ, RAYON_NUM_THREADS='4'))
        print(name, (r.stderr.strip().splitlines() or [''])[0], f'| playable {meta["playable_km2"]:.2f} km2')
        if r.returncode: print(r.stderr); continue
        export_web(name, d, ground, dsm, bushm, play, meta)
