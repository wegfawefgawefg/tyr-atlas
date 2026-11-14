"""Armor analysis by ray casting the per-triangle armor meshes.

Data (extract/armor, from `extract.dll armor`):
  <veh>__SK_*_Armor_01.json  mesh: pos (cm, +X forward, +Z up), idx, bone per vertex, bones
  <veh>__T_*_Armor.PF_B8G8R8A8.WxH.raw  one BGRA pixel per triangle: B = thickness (mm), G = flag, A = plate id
Penetration rule (TyrArmorRuntimeSettings: constructor defaults in the exe + DefaultGame.ini):
  AutoBounceThreshold 80 deg, PenetrationOvermatching 4.0, FiftyFiftyThreshold 1.25 (ini; default 1.2)
  pen >= 4 * t           -> penetrates (overmatch, angle ignored)
  impact angle > 80 deg  -> bounce
  t / cos(angle) <= pen  -> penetrates
  <= 1.25 * pen          -> 50 % (assumed direction of the fifty-fifty band)
  otherwise              -> bounce
  t == 0                 -> no armor, counts as a penetration
Orthographic rays: every direction is sampled with a grid of parallel rays; the first triangle hit decides.
"""
import json, glob, os, sys, time
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
AUTO_BOUNCE = 80.0
OVERMATCH = 4.0
FIFTY = 1.25
RES = 6.0                      # cm per ray
AZ = np.arange(0, 360, 5)      # 0 = shooter straight ahead of the tank, 90 = shooter on the tank's left (+Y)
EL = np.array([-10, 0, 10, 20, 30, 45, 60, 75])
PEN = list(range(30, 205, 5))   # every base pen x every ammo modifier lands within this grid (interpolate between steps)
YAWS = [0, 45, 90, 135, 180]   # turret yaw for the turret-angle study (front view)

PLUGIN_TO_NAME = {t['plugin']: t['name'] for t in json.load(open(os.path.join(ROOT, 'data/tyr.json')))['tanks'].values()}

def load(veh):
    m = json.load(open(glob.glob(os.path.join(ROOT, f'extract/armor/{veh}__SK_*Armor_01.json'))[0]))
    f = glob.glob(os.path.join(ROOT, f'extract/armor/{veh}__T_*_Armor.PF_B8G8R8A8.*.raw'))[0]
    px = np.frombuffer(open(f, 'rb').read(), np.uint8).reshape(-1, 4)
    P = np.array(m['pos'], np.float64).reshape(-1, 3)
    I = np.array(m['idx'], np.int64).reshape(-1, 3)
    px = px[:len(I)]
    thick = px[:, 0].astype(np.float64)
    bad = px[:, 1] > 1                      # stray bytes (seen on wheel suspension triangles)
    names = [b['name'] for b in m['bones']]
    vb = np.array(m['bone'])
    tri_bone = np.array([names[vb[a]] for a in I[:, 0]])
    turret = np.isin(tri_bone, ['jnt_turret', 'jnt_gun_mantle', 'jnt_gun', 'jnt_gun_barrel', 'jnt_muzzle_brake', 'jnt_muzzle'])
    wheel = np.char.find(tri_bone.astype(str), 'wheel') >= 0
    fm = glob.glob(os.path.join(ROOT, f'extract/armor/{veh}__T_*_Module.PF_B8G8R8A8.*.raw'))[0]
    mo = np.frombuffer(open(fm, 'rb').read(), np.uint8).reshape(-1, 4)[:len(I)]
    # module type: DT_ModuleData row names end in round(B/255*1e5); map each triangle's B value to its row's module tag
    rows = json.load(open(os.path.join(ROOT, f'extract/json/Tyr/Plugins/GameFeatures/Vehicles/{veh}/Content/DT_ModuleData.json')))[0]['Rows']
    by_code = {int(k.rsplit('_', 1)[1]): r['ModuleIdentifierTag']['TagName'] for k, r in rows.items()}
    CODE = {'Track': 1, 'Bonus': 2, 'Fire': 3, 'Engine': 4, 'Gun': 5, 'Turret': 6, 'Ability': 7}
    module = np.zeros(len(mo), int)
    for b in set(mo[:, 0].tolist()):
        if not b: continue
        code = b / 255 * 1e5
        if not by_code: continue
        near = min(by_code, key=lambda k: abs(k - code))
        if abs(near - code) > 2: continue
        tag = by_code[near]
        kind = tag.split('.')[2]
        module[mo[:, 0] == b] = CODE.get(kind, 0)
    keep = ~bad
    NV = np.array(m['nrm'], np.float64).reshape(-1, 3)
    NV /= np.maximum(np.linalg.norm(NV, axis=1, keepdims=True), 1e-9)
    return dict(bones=bone_world(m), P=P, NV=NV, I=I[keep], t=thick[keep], plate=px[keep, 3], turret=turret[keep], wheel=wheel[keep], flag=px[keep, 1],
                module=module[keep], name=m['name'])

def bone_world(m):
    def qmul(a, b):
        ax, ay, az, aw = a; bx, by, bz, bw = b
        return np.array([aw*bx + ax*bw + ay*bz - az*by, aw*by - ax*bz + ay*bw + az*bx, aw*bz + ax*by - ay*bx + az*bw, aw*bw - ax*bx - ay*by - az*bz])
    def rot(q, v):
        u = np.array(q[:3]); w = q[3]; return v + 2 * np.cross(u, np.cross(u, v) + w * v)
    W = []
    for b in m['bones']:
        q, t = np.array(b['q'], float), np.array(b['t'], float)
        if b['parent'] < 0: W.append((q, t))
        else:
            pq, pt = W[b['parent']]; W.append((qmul(pq, q), pt + rot(pq, t)))
    return {b['name']: W[i][1] for i, b in enumerate(m['bones'])}

def yaw_turret(mesh, deg):
    """copy of mesh with turret-chain triangles' vertices rotated about the turret pivot"""
    if not deg: return mesh
    P = mesh['P'].copy(); piv = mesh['bones'].get('jnt_turret')
    if piv is None: return mesh
    verts = np.unique(mesh['I'][mesh['turret']])
    a = np.radians(deg); c, s_ = np.cos(a), np.sin(a)
    x, y = P[verts, 0] - piv[0], P[verts, 1] - piv[1]
    P[verts, 0] = piv[0] + c * x - s_ * y; P[verts, 1] = piv[1] + s_ * x + c * y
    return dict(mesh, P=P)

def basis(az, el):
    a, e = np.radians(az), np.radians(el)
    s = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])   # tank -> shooter
    d = -s                                                                    # ray direction
    up = np.array([0, 0, 1.0]) if abs(s[2]) < 0.99 else np.array([1.0, 0, 0])
    u = np.cross(up, d); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return d, u, v

def raster(mesh, d, u, v, res=RES):
    """first-hit triangle per pixel: returns (tri index grid or -1), grid origin"""
    P, I = mesh['P'], mesh['I']
    x, y, z = P @ u, P @ v, P @ d
    x0, y0 = x.min() - res, y.min() - res
    W = int((x.max() - x0) / res) + 2; H = int((y.max() - y0) / res) + 2
    X = (x - x0) / res; Y = (y - y0) / res
    tx, ty, tz = X[I], Y[I], z[I]                    # (T,3)
    bx0 = np.floor(tx.min(1)).astype(int); bx1 = np.ceil(tx.max(1)).astype(int)
    by0 = np.floor(ty.min(1)).astype(int); by1 = np.ceil(ty.max(1)).astype(int)
    bw = bx1 - bx0 + 1; bh = by1 - by0 + 1; n = bw * bh
    tri = np.repeat(np.arange(len(I)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    pxs = bx0[tri] + k % bw[tri]; pys = by0[tri] + k // bw[tri]
    cx, cy = pxs + 0.5, pys + 0.5
    ax, ay = tx[tri, 0], ty[tri, 0]; bx, by = tx[tri, 1], ty[tri, 1]; qx, qy = tx[tri, 2], ty[tri, 2]
    den = (by - qy) * (ax - qx) + (qx - bx) * (ay - qy)
    ok = np.abs(den) > 1e-12
    den = np.where(ok, den, 1.0)
    w0 = ((by - qy) * (cx - qx) + (qx - bx) * (cy - qy)) / den
    w1 = ((qy - ay) * (cx - qx) + (ax - qx) * (cy - qy)) / den
    w2 = 1 - w0 - w1
    inside = ok & (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9) & (pxs >= 0) & (pys >= 0) & (pxs < W) & (pys < H)
    tri, pxs, pys = tri[inside], pxs[inside], pys[inside]
    w0, w1, w2 = w0[inside], w1[inside], w2[inside]
    depth = (w0 * tz[tri, 0] + w1 * tz[tri, 1] + w2 * tz[tri, 2])
    pix = pys * W + pxs
    order = np.lexsort((depth, pix))
    pix_s = pix[order]
    first = np.ones(len(pix_s), bool); first[1:] = pix_s[1:] != pix_s[:-1]
    grid = np.full(W * H, -1, np.int64)
    grid[pix_s[first]] = tri[order][first]
    wts = np.zeros((W * H, 3)); sel = order[first]
    wts[pix_s[first]] = np.stack([w0[sel], w1[sel], w2[sel]], 1)
    raster.origin = (x0, y0); raster.weights = wts.reshape(H, W, 3)
    return grid.reshape(H, W)

def hit_normals(mesh, g, d):
    """|cos impact angle| per hit pixel using interpolated vertex normals (game: bUseSoftArmorNormals = true on BP_BaseTank)"""
    m = g >= 0; tri = g[m]; w = raster.weights[m]
    Nv = mesh['NV'][mesh['I'][tri]]                      # (n,3,3)
    n = (w[:, :, None] * Nv).sum(1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    return np.abs(n @ d)

def face_normals(mesh):
    P, I = mesh['P'], mesh['I']
    n = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]])
    L = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(L > 0, L, 1)

def pen_chance(t, cosang, pen):
    """per-hit penetration probability for thickness t (mm), cos impact angle, penetration pen"""
    ang = np.degrees(np.arccos(np.clip(cosang, 0, 1)))
    eff = t / np.maximum(cosang, 1e-6)
    p = np.where(eff <= pen, 1.0, np.where(eff <= pen * FIFTY, 0.5, 0.0))
    p = np.where(ang > AUTO_BOUNCE, 0.0, p)
    p = np.where(pen >= OVERMATCH * t, 1.0, p)
    p = np.where(t <= 0, 1.0, p)
    return p

def analyse(veh):
    mesh = load(veh)
    N = face_normals(mesh)
    out = dict(name=PLUGIN_TO_NAME.get(veh, veh), plugin=veh, az=AZ.tolist(), el=EL.tolist(), pen=PEN, res_cm=RES)
    area = np.zeros((len(EL), len(AZ))); pchance = np.zeros((len(EL), len(AZ), len(PEN))); dchance = np.zeros_like(pchance)
    tread = np.zeros((len(EL), len(AZ))); crit = np.zeros((len(EL), len(AZ)))
    eff_med = np.zeros((len(EL), len(AZ))); turret_share = np.zeros((len(EL), len(AZ)))
    views = {}
    for ei, el in enumerate(EL):
        for ai, az in enumerate(AZ):
            d, u, v = basis(az, el)
            g = raster(mesh, d, u, v)
            hit = g[g >= 0]
            if not len(hit): continue
            cosang = hit_normals(mesh, g, d)
            t = mesh['t'][hit]
            area[ei, ai] = len(hit) * (RES / 100) ** 2
            eff = np.where(t > 0, t / np.maximum(cosang, 1e-6), 0)
            eff_med[ei, ai] = float(np.median(eff))
            turret_share[ei, ai] = float(mesh['turret'][hit].mean())
            mod = mesh['module'][hit]
            is_tread = mod == 1
            tread[ei, ai] = float(is_tread.mean()); crit[ei, ai] = float((mod >= 2).mean())
            for pi, pen in enumerate(PEN):
                pc = pen_chance(t, cosang, pen)
                pchance[ei, ai, pi] = float(pc.mean())
                dchance[ei, ai, pi] = float((pc * ~is_tread).mean())     # treads: no HP damage
            key = {(0, 0): 'front', (0, 30): 'front30', (0, 90): 'left', (0, 180): 'rear', (75, 0): 'top'}.get((el, az))
            if key:
                img = np.full(g.shape, -1.0)
                m = g >= 0
                ca = hit_normals(mesh, g, d)
                tt = mesh['t'][g[m]]
                bounce = np.degrees(np.arccos(np.clip(ca, 0, 1))) > AUTO_BOUNCE
                img[m] = np.where(bounce, 999, np.where(tt > 0, tt / np.maximum(ca, 1e-6), 0))
                md = mesh['module'][g[m]]
                modimg = np.zeros(g.shape, int); modimg[m] = md   # 0 none, 1 tread, 2 bonus, 3 fire, 4 engine, 5 gun, 6 turret, 7 ability
                views[key] = dict(w=int(g.shape[1]), h=int(g.shape[0]), y0_cm=float(raster.origin[1]),
                                  eff=[int(min(999, round(x))) if x >= 0 else -1 for x in img[::-1].ravel()],   # flip so up is up
                                  mod=modimg[::-1].ravel().tolist(),
                                  t=[int(x) for x in np.where(m, np.where(g >= 0, mesh['t'][np.maximum(g, 0)], 0), -1)[::-1].ravel()])
    out.update(area=area.round(3).tolist(), pchance=pchance.round(4).tolist(), dchance=dchance.round(4).tolist(),
               tread=tread.round(3).tolist(), crit=crit.round(4).tolist(), eff_med=eff_med.round(1).tolist(),
               turret_share=turret_share.round(3).tolist(), views=views)
    yaw = np.zeros((len(YAWS), len(PEN))); yaw_turret_only = np.zeros((len(YAWS), len(PEN)))
    d, u, v = basis(0, 0)
    for yi, deg in enumerate(YAWS):
        mm = yaw_turret(mesh, deg); NN = face_normals(mm)
        g = raster(mm, d, u, v); hit = g[g >= 0]
        ca = hit_normals(mm, g, d) if not deg else np.abs(NN[hit] @ d); t = mm['t'][hit]; md = mm['module'][hit]; tur = mm['turret'][hit]
        nt = md != 1
        for pi_, pen in enumerate(PEN):
            pc = pen_chance(t, ca, pen) * nt
            yaw[yi, pi_] = float(pc.mean()); yaw_turret_only[yi, pi_] = float(pc[tur].mean()) if tur.any() else 0.0
    out['yaw'] = dict(deg=YAWS, dchance=yaw.round(4).tolist(), turret_dchance=yaw_turret_only.round(4).tolist())
    out['bone_z_cm'] = {k: float(mesh['bones'][k][2]) for k in ('jnt_turret', 'jnt_gun', 'jnt_gun_mantle', 'jnt_muzzle') if k in mesh['bones']}
    P = mesh['P']
    out['dims_m'] = (np.ptp(P, 0) / 100).round(2).tolist()
    out['height_m'] = float(P[:, 2].max() / 100)
    out['plates'] = int(len(set(mesh['plate'].tolist())))
    out['thickness_hist'] = {int(k): int(v) for k, v in zip(*np.unique(mesh['t'], return_counts=True))}
    return out

if __name__ == '__main__':
    vehs = sys.argv[1:] or sorted({os.path.basename(f).split('__')[0] for f in glob.glob(os.path.join(ROOT, 'extract/armor/*__SK_*.json'))})
    res = {}
    for veh in vehs:
        t0 = time.time()
        a = analyse(veh)
        res[a['name']] = a
        el0 = a['el'].index(0); i70 = a['pen'].index(70)
        print('   turret yaw dmg@70 front:', [round(r[a['pen'].index(70)], 2) for r in a['yaw']['dchance']])
        pc = np.array(a['dchance'])[el0, :, i70]
        print(f"{a['name']:9s} {time.time()-t0:5.1f}s  front {a['area'][el0][0]:.1f} m2 side {a['area'][el0][18]:.1f} m2  "
              f"dmg@70: front {pc[0]:.2f} side {pc[18]:.2f} rear {pc[36]:.2f}  height {a['height_m']:.2f} m", flush=True)
    if not sys.argv[1:]:
        json.dump(res, open(os.path.join(ROOT, 'data/armor.json'), 'w'))
