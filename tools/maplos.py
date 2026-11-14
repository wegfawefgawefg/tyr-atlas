"""Line-of-sight analysis per map: prepares grid.bin for tools/los (Rust), runs it, renders PNG maps.

Assumptions (shown on the site):
  analysis cells 2 m; obstacles keep their highest point when downsampling (thin walls survive)
  observer eye = gun height 2.5 m; target = a 2.5 m tall column; each sight line counts the exposed share of that column
  (lowest visible point up to the top), so a tank behind a crest counts as partly seen
  vision radius 400 m (TankData VisionRadius = 400 on every tank; assumed metres)
  bushes block sight like a 3 m wall; a tank inside a bush is hidden beyond 50 m
  playable area: within 80 m of the convex hull of bushes, zones and spawns, slope under 35 deg, not inside structures,
  connected to the zones. Observers every 8 m.
"""
import json, os, sys, struct, subprocess
import numpy as np
from scipy.ndimage import distance_transform_edt, label, zoom
from scipy.spatial import Delaunay
from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(__file__), '..')
DS = 2                     # 1 m -> 2 m cells
EYE, TGT, RADIUS_M, STRIDE, BUSH_M, BUSH_CONCEAL = 2.5, 2.5, 400, 4, 3.0, 50.0
ZONE_KINDS = ('CaptureZone', 'HealZone', 'AmmunitionZone', 'AbilityResourceZone')

def pool(a, f, how):
    H, W = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:H, :W].reshape(H // f, f, W // f, f)
    return b.max((1, 3)) if how == 'max' else b.mean((1, 3))

def prepare(name):
    d = os.path.join(ROOT, 'extract/maps', name)
    g = json.load(open(os.path.join(d, 'grid.json'))); z = np.load(os.path.join(d, 'grid.npz'))
    res = g['res'] * DS / 100.0                                     # metres per analysis cell
    dtm = pool(z['dtm'] / 100, DS, 'mean').astype(np.float32)
    dsm = pool(z['dsm'] / 100, DS, 'max').astype(np.float32)
    bush = pool(z['bush'].astype(np.float32), DS, 'max') > 0
    H, W = dtm.shape
    ox, oy = g['origin']
    cell = lambda o: ((o['x'] - ox) / 100 / res, (o['y'] - oy) / 100 / res)
    anchors = [cell(o) for o in g['objects'] if o['kind'] in ZONE_KINDS + ('Bush', 'PlayerStart', 'SpawnWall')]
    hull = Delaunay(np.array(anchors))
    YY, XX = np.mgrid[0:H, 0:W]
    inside = hull.find_simplex(np.stack([XX.ravel(), YY.ravel()], 1)) >= 0
    inside = inside.reshape(H, W)
    near = distance_transform_edt(~inside) * res <= 80
    ground = dsm.copy()                                            # tanks drive on terrain and on top of meshes
    gy, gx = np.gradient(ground, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    walk = near & (slope < 35)
    lab, _ = label(walk)
    zones = [o for o in g['objects'] if o['kind'] in ZONE_KINDS]
    keep = set()
    rr = int(15 / res)
    for o in zones:   # zone centres can sit on a steep platform: take every walkable region within 15 m
        cx, cy = int(round(cell(o)[0])), int(round(cell(o)[1]))
        keep |= set(np.unique(lab[max(0, cy - rr):cy + rr + 1, max(0, cx - rr):cx + rr + 1]).tolist())
    keep -= {0}
    play = np.isin(lab, list(keep))
    vis = np.maximum(dsm, np.where(bush, dtm + BUSH_M, dsm)).astype(np.float32)
    zc = [(int(round(cell(o)[0])), int(round(cell(o)[1]))) for o in zones]
    with open(os.path.join(d, 'grid.bin'), 'wb') as f:
        f.write(struct.pack('<IIfIffIfI', W, H, res, int(RADIUS_M / res), EYE, TGT, STRIDE, BUSH_CONCEAL, len(zc)))
        for x, y in zc: f.write(struct.pack('<II', x, y))
        f.write(ground.astype(np.float32).tobytes()); f.write(vis.tobytes()); f.write(dsm.tobytes()); f.write(play.astype(np.uint8).tobytes()); f.write(bush.astype(np.uint8).tobytes())
    meta = dict(map=name, res=res, shape=[H, W], origin=g['origin'], zones=[dict(kind=o['kind'], x=x, y=y) for o, (x, y) in zip(zones, zc)],
                spawns=[cell(o) for o in g['objects'] if o['kind'] == 'PlayerStart'], playable_km2=float(play.sum() * res * res / 1e6),
                assumptions=dict(eye_m=EYE, target_m=TGT, radius_m=RADIUS_M, observer_spacing_m=STRIDE * res, bush_height_m=BUSH_M, bush_conceal_m=BUSH_CONCEAL))
    json.dump(meta, open(os.path.join(d, 'los.json'), 'w'))
    return d, ground.astype(np.float32), dsm, bush, play, meta

def render(name, d, dtm, dsm, bush, play, meta):
    H, W = dtm.shape
    n = H * W
    sees = np.fromfile(os.path.join(d, 'sees.f32'), np.float32).reshape(H, W)
    seen = np.fromfile(os.path.join(d, 'seen.f32'), np.float32).reshape(H, W)
    gy, gx = np.gradient(dsm)
    shade = np.clip(0.55 + (gx * -0.6 + gy * -0.6) * 0.5, 0.15, 1)
    base = np.stack([shade * 0.55, shade * 0.58, shade * 0.55], -1)
    base[(dsm - dtm) > 1.5] = [0.45, 0.32, 0.25]
    base[bush] = base[bush] * 0.5 + np.array([0.15, 0.45, 0.15]) * 0.5
    obs = ~np.isnan(sees)
    # spread observer values to their neighbourhood for display
    from scipy.ndimage import grey_dilation
    def spread(v):
        a = np.where(obs, v, -1.0)
        return grey_dilation(a, size=(STRIDE, STRIDE))
    def colour(v, cmap):
        v = np.clip(v, 0, 1)
        return np.stack([np.interp(v, [0, .5, 1], c) for c in cmap], -1)
    out = {}
    sees_s = spread(sees); seen_s = grey_dilation(np.where(play, seen, -1), size=(2, 2))
    hot = ([0.1, 0.9, 1.0], [0.2, 0.75, 0.25], [0.6, 0.2, 0.05])   # cool -> warm, as r,g,b channel ramps
    for key, v, mask in (('sees', sees_s, sees_s >= 0), ('seen', seen_s, seen_s >= 0)):
        vv = v / (np.percentile(v[mask], 98) + 1e-9)
        img = base.copy(); c = colour(vv, hot)
        img[mask] = img[mask] * 0.35 + c[mask] * 0.65
        out[key] = img
    # advantage: percentile of what a spot sees minus percentile of how often it is seen (observer spots only)
    oy_, ox_ = np.where(obs)
    def pct(v):
        r = np.argsort(np.argsort(v)); return r / max(len(v) - 1, 1)
    cell_m2 = (STRIDE * meta['res']) ** 2          # each observer spot stands for this much ground
    adv_v = np.log2((sees[oy_, ox_] + cell_m2) / (seen[oy_, ox_] * cell_m2 + cell_m2)) / 0.5   # +-0.5 (x1.41) spans the colour scale
    adv = np.full(sees.shape, np.nan); adv[oy_, ox_] = adv_v
    adv_s = grey_dilation(np.where(obs, adv, -9), size=(STRIDE, STRIDE))
    m = adv_s > -5
    t = np.clip(adv_s, -1, 1)
    neg = np.array([0.80, 0.25, 0.20]); mid = np.array([0.62, 0.62, 0.60]); pos = np.array([0.15, 0.45, 0.90])
    c = np.where(t[..., None] < 0, mid + (neg - mid) * (-t[..., None]), mid + (pos - mid) * t[..., None])
    img = base.copy(); img[m] = img[m] * 0.3 + c[m] * 0.7
    out['advantage'] = img
    for key, img in out.items():
        im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)[::-1])
        dr = ImageDraw.Draw(im)
        for zz in meta['zones']:
            x, y = zz['x'], H - 1 - zz['y']
            dr.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(255, 230, 0) if zz['kind'] == 'CaptureZone' else (255, 255, 255), width=3)
        im.save(os.path.join(ROOT, 'extract/maps/png', f'{name.lower()}_{key}.png'))
    # top advantage spots (observer cells), spread apart by 40 m
    floor = np.percentile(sees[obs], 60)
    cand = sorted(((adv[y, x], x, y) for y, x in zip(oy_, ox_) if sees[y, x] >= floor), reverse=True)
    spots = []
    for a, x, y in cand:
        if all((x - sx) ** 2 + (y - sy) ** 2 > (40 / meta['res']) ** 2 for _, sx, sy in spots):
            spots.append((a, x, y))
        if len(spots) >= 12: break
    export_web(name, d, dtm, dsm, bush, play, meta, sees, seen, adv, obs, base)
    meta['top_spots'] = [dict(x=int(x), y=int(y), sees_m2=float(sees[y, x]), seen_by=float(seen[y, x]), score=float(a)) for a, x, y in spots]
    json.dump(meta, open(os.path.join(d, 'los.json'), 'w'))
    print(f"{name}: playable {meta['playable_km2']:.2f} km2; best spot sees {spots[0] and sees[spots[0][2], spots[0][1]]:.0f} m2, seen by {seen[spots[0][2], spots[0][1]]:.0f} observers")

def export_web(name, d, dtm, dsm, bush, play, meta, sees, seen, adv, obs, base):
    """site/maps/<name>/: base.jpg (terrain), RGBA overlays (sees, seen, advantage, zone<i>), meta.json; cropped to playable + 40 m"""
    from scipy.ndimage import grey_dilation
    H, W = dtm.shape; res = meta['res']
    ys, xs = np.where(play)
    m = int(40 / res)
    y0, y1, x0, x1 = max(0, ys.min() - m), min(H, ys.max() + m), max(0, xs.min() - m), min(W, xs.max() + m)
    out = os.path.join(ROOT, 'site/maps', name.lower()); os.makedirs(out, exist_ok=True)
    crop = lambda a: a[y0:y1, x0:x1][::-1]          # +Y up
    Image.fromarray((np.clip(crop(base), 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, 'base.jpg'), quality=82)
    def layer(v, mask, ramp):
        v = np.clip(v, 0, 1)
        rgb = np.stack([np.interp(v, [0, .5, 1], c) for c in ramp], -1)
        a = np.where(mask, 0.72, 0.0)
        return Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), 'RGBA')
    # channel ramps at v = 0, 0.5, 1 -- sequential blue (#cde2fb -> #5598e7 -> #0d366b)
    seq = ([0.80, 0.33, 0.05], [0.89, 0.60, 0.21], [0.98, 0.91, 0.42])
    def spread(v, size): return grey_dilation(np.where(obs, v, -1.0), size=(size, size))
    s_s = spread(sees, STRIDE); n_s = grey_dilation(np.where(play, seen, -1.0), size=(2, 2))
    for key, v in (('sees', s_s), ('seen', n_s)):
        mk = v >= 0; vv = v / (np.percentile(v[mk], 98) + 1e-9)
        layer(crop(vv), crop(mk), seq).save(os.path.join(out, f'{key}.png'), optimize=True)
    a_s = grey_dilation(np.where(obs, adv, -9.0), size=(STRIDE, STRIDE)); mk = a_s > -5
    t = (np.clip(a_s, -1, 1) + 1) / 2
    # red (seen more) - grey - blue (sees more)
    layer(crop(t), crop(mk), ([0.82, 0.62, 0.16], [0.30, 0.62, 0.47], [0.25, 0.60, 0.84])).save(os.path.join(out, 'advantage.png'), optimize=True)
    zmap = np.fromfile(os.path.join(d, 'zones.u8'), np.uint8).reshape(len(meta['zones']), H, W)
    zl = []
    for k, z in enumerate(meta['zones']):
        if z['kind'] != 'CaptureZone': continue
        cov = grey_dilation(np.where(obs, zmap[k].astype(float), -1.0), size=(STRIDE, STRIDE))
        mk = cov > 0.5
        img = np.zeros(cov.shape + (4,)); img[mk] = [0.95, 0.75, 0.10, 0.6]
        Image.fromarray((crop(img) * 255).astype(np.uint8), 'RGBA').save(os.path.join(out, f'zone{k}.png'), optimize=True)
        zl.append(k)
    to_px = lambda x, y: [round(float(x - x0), 1), round(float((y1 - 1 - y)), 1)]
    web = dict(map=name, size=[int(x1 - x0), int(y1 - y0)], m_per_px=res, layers=['sees', 'seen', 'advantage'],
               zone_layers=zl, zones=[dict(kind=z['kind'], px=to_px(z['x'], z['y'])) for z in meta['zones']],
               spawns=[to_px(x, y) for x, y in meta['spawns']], playable_km2=meta['playable_km2'], assumptions=meta['assumptions'])
    oy_, ox_ = np.where(obs)
    floor = np.percentile(sees[obs], 60)      # a strong spot has to see a lot as well as be seen little
    inner = distance_transform_edt(play) * res >= 40   # edge spots have fewer possible viewers and may be out of bounds
    def pick(cond, n=8):
        cand = sorted(((adv[y, x], x, y) for y, x in zip(oy_, ox_) if sees[y, x] >= floor and inner[y, x] and cond(x, y)), reverse=True)
        out_ = []
        for a, x, y in cand:
            if all((x - sx) ** 2 + (y - sy) ** 2 > (40 / res) ** 2 for _, sx, sy in out_): out_.append((a, x, y))
            if len(out_) >= n: break
        return out_
    def near_bush(x, y):
        r = 2; return bool(bush[max(0, y - r):y + r + 1, max(0, x - r):x + r + 1].any())
    web['spots'] = []
    for kind, lst in (('open', pick(lambda x, y: not near_bush(x, y))), ('bush', pick(near_bush))):
        for a, x, y in lst:
            web['spots'].append(dict(kind=kind, px=to_px(x, y), sees_m2=round(float(sees[y, x])), seen_m2=round(float(seen[y, x]) * (STRIDE * res) ** 2),
                                     ratio=round(float((sees[y, x] + 64) / (seen[y, x] * (STRIDE * res) ** 2 + 64)), 2),
                                     height_m=round(float(dtm[y, x] - np.percentile(dtm[play], 50)), 1)))
    json.dump(web, open(os.path.join(out, 'meta.json'), 'w'))

if __name__ == '__main__':
    exe = os.path.join(ROOT, 'tools/los/target/release/los')
    for name in sys.argv[1:]:
        d, dtm, dsm, bush, play, meta = prepare(name)
        r = subprocess.run(['nice', '-n', '19', exe, d], capture_output=True, text=True, env=dict(os.environ, RAYON_NUM_THREADS='4'))
        print(r.stderr.strip())
        render(name, d, dtm, dsm, bush, play, meta)
