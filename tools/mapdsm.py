"""Build a 2.5D surface model per map from extract/maps/<Map>/ (tools/extract `map` mode).

Outputs extract/maps/<Map>/grid.npz:
  dtm  terrain height (cm) from landscape heightmaps
  dsm  max(terrain, solid structures) (cm)  -- what blocks line of sight and movement
  bush bush concealment mask (gameplay bushes, by radius)
  origin, res (cm), plus zones/spawns/no-go lists in grid.json
Heightmap texel: height = ((R << 8) | G - 32768) / 128 in landscape units, times the component's Z scale.
"""
import json, os, sys, glob, hashlib
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
RES = 100.0   # cm per cell

def qrot(q, v):
    x, y, z, w = q; u = np.array([x, y, z])
    return v + 2 * np.cross(u, np.cross(u, v) + w * v)

def apply(xf, P):
    """UE transform: scale, then rotate, then translate"""
    P = np.asarray(P, float) * np.array(xf['s'])
    x, y, z, w = xf['q']; u = np.array([x, y, z])
    P = P + 2 * np.cross(u, np.cross(u, P) + w * P)
    return P + np.array(xf['t'])

def landscape_points(d, m):
    pts = []
    for c in m['land']:
        hm = m['heightmaps'].get(c['hm'])
        if not hm: continue
        f = glob.glob(os.path.join(d, f"hm_{c['hm']}.*.raw"))
        if not f: continue
        tex = np.frombuffer(open(f[0], 'rb').read(), np.uint8).reshape(hm['h'], hm['w'], 4)
        h16 = (tex[:, :, 2].astype(np.int32) << 8) | tex[:, :, 1]      # BGRA: R high byte, G low byte
        sub, nsub, size = c['sub'], c['nsub'], c['size']
        ox, oy = int(round(c['hsb'][2] * hm['w'])), int(round(c['hsb'][3] * hm['h']))
        q = np.arange(size + 1)
        sx = np.minimum(q // sub, nsub - 1); t = sx * (sub + 1) + (q - sx * sub)
        TX, TY = np.meshgrid(ox + t, oy + t)
        H = (h16[TY, TX] - 32768) / 128.0
        X, Y = np.meshgrid(q, q)
        local = np.stack([X.ravel(), Y.ravel(), H.ravel()], 1).astype(float)
        pts.append(apply(c['xf'], local))
    return np.concatenate(pts) if pts else np.zeros((0, 3))

def mesh_file(d, path):
    return os.path.join(d, 'meshes', hashlib.sha1(path.encode()).hexdigest().upper()[:16] + '.json')

def is_obstacle(path, ext):
    p = path.lower()
    if any(k in p for k in ('/foliages/grass', 'wildgrass', 'tallflower', '/decal', 'skysphere', 'engine/engine', 'capturezone', 'symbol', 'glow', '/vfx/')): return False
    return ext[2] >= 120          # at least 1.2 m tall in world scale

CAP_CM = 6000   # ignore geometry more than 60 m above the terrain (roofs, overhead structures)

def raster_max(grid, origin, res, tris, cap=None):
    """rasterize world triangles (T,3,3) top-down, keep the max z per cell (sampled at cell centres)"""
    H, W = grid.shape
    tx = (tris[:, :, 0] - origin[0]) / res; ty = (tris[:, :, 1] - origin[1]) / res; tz = tris[:, :, 2]
    bx0 = np.floor(tx.min(1)).astype(int); bx1 = np.ceil(tx.max(1)).astype(int)
    by0 = np.floor(ty.min(1)).astype(int); by1 = np.ceil(ty.max(1)).astype(int)
    keep = (bx1 >= 0) & (by1 >= 0) & (bx0 < W) & (by0 < H) & ((bx1 - bx0) < 600) & ((by1 - by0) < 600)   # drop absurd footprints (sky domes, bad scales)
    tx, ty, tz, bx0, bx1, by0, by1 = tx[keep], ty[keep], tz[keep], bx0[keep], bx1[keep], by0[keep], by1[keep]
    bw = bx1 - bx0 + 1; bh = by1 - by0 + 1; n = bw * bh
    if not len(n): return
    # chunk to bound memory
    for lo in range(0, len(n), 20000):
        sl = slice(lo, lo + 20000); nn = n[sl]
        tri = np.repeat(np.arange(lo, lo + len(nn)), nn)
        k = np.arange(nn.sum()) - np.repeat(np.cumsum(nn) - nn, nn)
        px = bx0[tri] + k % bw[tri]; py = by0[tri] + k // bw[tri]
        cx, cy = px + 0.5, py + 0.5
        ax, ay, bxx, byy, qx, qy = tx[tri, 0], ty[tri, 0], tx[tri, 1], ty[tri, 1], tx[tri, 2], ty[tri, 2]
        den = (byy - qy) * (ax - qx) + (qx - bxx) * (ay - qy)
        ok = np.abs(den) > 1e-12; den = np.where(ok, den, 1)
        w0 = ((byy - qy) * (cx - qx) + (qx - bxx) * (cy - qy)) / den
        w1 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / den
        w2 = 1 - w0 - w1
        ins = ok & (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02) & (px >= 0) & (py >= 0) & (px < W) & (py < H)
        z = w0 * tz[tri, 0] + w1 * tz[tri, 1] + w2 * tz[tri, 2]
        if cap is not None:
            ins = ins & (z <= cap[np.clip(py, 0, H - 1), np.clip(px, 0, W - 1)])
        np.maximum.at(grid, (py[ins], px[ins]), z[ins])

def build(name):
    d = os.path.join(ROOT, 'extract/maps', name)
    m = json.load(open(os.path.join(d, 'map.json')))
    L = landscape_points(d, m)
    x0, y0 = L[:, 0].min(), L[:, 1].min(); x1, y1 = L[:, 0].max(), L[:, 1].max()
    W = int((x1 - x0) / RES) + 2; H = int((y1 - y0) / RES) + 2
    dtm = np.full((H, W), -1e9)
    ix = ((L[:, 0] - x0) / RES).astype(int); iy = ((L[:, 1] - y0) / RES).astype(int)
    np.maximum.at(dtm, (iy, ix), L[:, 2])
    # fill any holes from neighbours
    hole = dtm < -1e8
    if hole.any():
        from scipy.ndimage import distance_transform_edt
        idx = distance_transform_edt(hole, return_distances=False, return_indices=True)
        dtm = dtm[tuple(idx)]
    dsm = dtm.copy()
    geo = {}
    n_obs = n_skip = 0
    for p in m['placements']:
        f = mesh_file(d, p['mesh'])
        if not os.path.exists(f): continue
        if p['mesh'] not in geo:
            g = json.load(open(f))
            geo[p['mesh']] = (np.array(g['pos'], float).reshape(-1, 3), np.array(g['idx'], int).reshape(-1, 3)) if g.get('idx') else None
        if geo[p['mesh']] is None: continue
        P, I = geo[p['mesh']]
        xfs = p['inst'] if 'inst' in p else [p['xf']]
        for xf in xfs:
            WP = apply(xf, P)
            ext = WP.max(0) - WP.min(0)
            if not is_obstacle(p['mesh'], ext) or ext[0] > 300000 or ext[1] > 300000: n_skip += 1; continue
            raster_max(dsm, (x0, y0), RES, WP[I], cap=dtm + CAP_CM); n_obs += 1
    # gameplay objects
    acts = {}
    for a in m['actors']:
        acts.setdefault(a['owner'], []).append(a)
    objs = []
    bush = np.zeros((H, W), bool)
    YY, XX = np.mgrid[0:H, 0:W]
    for owner, comps in acts.items():
        cls = comps[0]['cls']
        root = comps[0]['xf']['t']
        kind = next((k for k in ('CaptureZone', 'HealZone', 'AmmunitionZone', 'AbilityResourceZone', 'NoGoZone', 'SpawnWall', 'PlayerStart', 'Bush', 'SpawnPoint') if k in cls or k in owner), None)
        if not kind: continue
        r = max([c['sphere'] or 0 for c in comps] + [max(c['box']['X'], c['box']['Y']) if c.get('box') else 0 for c in comps])
        objs.append(dict(kind=kind, owner=owner, x=root[0], y=root[1], z=root[2], r=r))
        if kind == 'Bush':
            rr = (r or 300) / RES
            cx, cy = (root[0] - x0) / RES, (root[1] - y0) / RES
            bush |= (XX - cx) ** 2 + (YY - cy) ** 2 <= rr ** 2
    np.savez_compressed(os.path.join(d, 'grid.npz'), dtm=dtm.astype(np.float32), dsm=dsm.astype(np.float32), bush=bush)
    json.dump(dict(map=name, origin=[x0, y0], res=RES, shape=[H, W], objects=objs), open(os.path.join(d, 'grid.json'), 'w'))
    kinds = {}
    for o in objs: kinds[o['kind']] = kinds.get(o['kind'], 0) + 1
    print(f"{name:11s} {W}x{H} cells ({W*RES/100000:.1f} x {H*RES/100000:.1f} km), obstacles {n_obs}, skipped {n_skip}, "
          f"structure cells {(dsm - dtm > 150).sum()}, objects {kinds}")

if __name__ == '__main__':
    for n in sys.argv[1:] or sorted(os.listdir(os.path.join(ROOT, 'extract/maps'))):
        if os.path.exists(os.path.join(ROOT, 'extract/maps', n, 'map.json')): build(n)
