"""Build site/data.js: per-tank base + 31-point core-maxed stats, PCA map, distance matrix, cluster order."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import optimize as O
D = O.D
# key, label, unit, higher_is_better, group
STATS = [
    ('MaxHealth', 'Health', 'HP', 1, 'Survival'),
    ('Mass', 'Mass', 't', 1, 'Survival'),
    ('ShellDamage', 'Shell damage', 'dmg', 1, 'Firepower'),
    ('ClipDamage', 'Clip damage', 'dmg', 1, 'Firepower'),
    ('DPS', 'Damage per second', 'dmg/s', 1, 'Firepower'),
    ('ShellPenetration', 'Penetration', 'mm', 1, 'Firepower'),
    ('ReloadTime', 'Reload', 's', -1, 'Firepower'),
    ('ClipSize', 'Clip size', 'shells', 1, 'Firepower'),
    ('IntraClipReloadTime', 'Between-shot reload', 's', -1, 'Firepower'),
    ('ShellVelocity', 'Shell velocity', 'm/s', 1, 'Firepower'),
    ('AltAmmoCountOne', 'Alt shells carried', 'shells', 1, 'Firepower'),
    ('ShellSwapTime', 'Shell swap time', 's', -1, 'Firepower'),
    ('BaseDispersionPenalty', 'Base dispersion', '', -1, 'Accuracy'),
    ('DispersionReductionSpeed', 'Aim speed', '', 1, 'Accuracy'),
    ('MovementDispersionPenalty', 'Moving dispersion', '', -1, 'Accuracy'),
    ('HullTraverseDispersionPenalty', 'Hull-turn dispersion', '', -1, 'Accuracy'),
    ('TurretTraverseDispersionPenalty', 'Turret-turn dispersion', '', -1, 'Accuracy'),
    ('FiringDispersionPenalty', 'Firing dispersion', '', -1, 'Accuracy'),
    ('PreciseDispersionTime', 'Time to precision aim', 's', -1, 'Accuracy'),
    ('TurretTraverseSpeed', 'Turret traverse', 'deg/s', 1, 'Gun handling'),
    ('MaxTurretRotation', 'Turret arc', 'deg', 1, 'Gun handling'),
    ('GunTraverseSpeed', 'Gun elevation speed', 'deg/s', 1, 'Gun handling'),
    ('GunMaxDepression', 'Gun depression', 'deg', -1, 'Gun handling'),
    ('GunMaxElevation', 'Gun elevation', 'deg', 1, 'Gun handling'),
    ('GunMaxHoverTilt', 'Hover tilt', 'deg', 1, 'Gun handling'),
    ('MaxSpeed', 'Top speed', 'kph', 1, 'Mobility'),
    ('MaxReverseSpeed', 'Reverse speed', 'kph', 1, 'Mobility'),
    ('MaxStrafingSpeed', 'Strafe speed', 'kph', 1, 'Mobility'),
    ('AccelerationTime', 'Acceleration time', 's', -1, 'Mobility'),
    ('HullTraverseSpeed', 'Hull traverse', 'deg/s', 1, 'Mobility'),
    ('CamoPercentage', 'Camouflage', '%', 1, 'Scouting'),
    ('DetectionRadius', 'Detection radius', 'm', 1, 'Scouting'),
    ('AbilityCost', 'Ability cost', 'energy', -1, 'Ability'),
    ('AbilityCooldown', 'Ability cooldown', 's', -1, 'Ability'),
    ('AbilityDuration', 'Ability duration', 's', 1, 'Ability'),
    ('AbilityWindUpTime', 'Ability wind-up', 's', -1, 'Ability'),
    ('AbilityWindDownTime', 'Ability wind-down', 's', -1, 'Ability'),
    ('InitialAbilityResource', 'Starting energy', 'energy', 1, 'Ability'),
    ('FrontBounce70', 'Front: no-damage chance vs 70 pen', '%', 1, 'Armor'),
    ('FrontBounce85', 'Front: no-damage chance vs 85 pen', '%', 1, 'Armor'),
    ('AngledBounce70', 'Front angled 30°: vs 70 pen', '%', 1, 'Armor'),
    ('SideBounce70', 'Side: no-damage chance vs 70 pen', '%', 1, 'Armor'),
    ('RearBounce70', 'Rear: no-damage chance vs 70 pen', '%', 1, 'Armor'),
    ('RoundBounce70', 'All-round: no-damage chance vs 70 pen', '%', 1, 'Armor'),
    ('FrontEHP70', 'Front effective HP vs 70 pen', 'HP', 1, 'Armor'),
    ('TreadShareSide', 'Side hits landing on treads', '%', 1, 'Armor'),
    ('FrontWeak70', 'Front weak-spot area vs 70 pen', 'm²', -1, 'Armor'),
    ('FrontArea', 'Front silhouette', 'm²', -1, 'Size'),
    ('SideArea', 'Side silhouette', 'm²', -1, 'Size'),
    ('Height', 'Height', 'm', -1, 'Size'),
    ('FirepowerRating', 'Firepower rating', '/10', 1, 'Designer ratings'),
    ('DurabilityRating', 'Durability rating', '/10', 1, 'Designer ratings'),
    ('ScoutingRating', 'Scouting rating', '/10', 1, 'Designer ratings'),
    ('AbilityRating', 'Ability rating', '/10', 1, 'Designer ratings'),
    ('DifficultyRating', 'Difficulty rating', '/5', -1, 'Designer ratings'),
]
def derived(st):
    st = dict(st)
    clip = max(1, st['ClipSize'])
    st['DPS'] = st['ShellDamage'] * clip / (st['ReloadTime'] + (clip - 1) * st['IntraClipReloadTime'])
    st['ClipDamage'] = st['ShellDamage'] * clip
    st['Mass'] = st['Mass'] / 1000
    return st
ALL = ['MovementDispersionPenalty', 'FiringDispersionPenalty', 'HullTraverseDispersionPenalty', 'TurretTraverseDispersionPenalty',
       'MaxStrafingSpeed', 'ShellSwapTime', 'MaxHealth', 'ShellDamage', 'ReloadTime', 'IntraClipReloadTime', 'MaxSpeed', 'MaxReverseSpeed', 'CamoPercentage',
       'BaseDispersionPenalty', 'DispersionReductionSpeed', 'PreciseDispersionTime', 'GunMaxDepression', 'TurretTraverseSpeed',
       'AccelerationTime', 'HullTraverseSpeed', 'ShellVelocity', 'AbilityCost', 'InitialAbilityResource']
# ceilings: lower-is-better stats are minimised (objectives must rise as each oriented channel improves)
OBJ = {k: ([k], (lambda k, sgn: lambda st: sgn * st[k])(k, -1 if k in O.LOWER_BETTER else 1)) for k in ALL}
O.OBJECTIVES.update(OBJ)
ARM = json.load(open(os.path.join(O.ROOT, 'data/armor.json')))
def armor_stats(name, hp):
    a = ARM[name]; el = a['el'].index(0); az = a['az']; pens = a['pen']
    dc = np.array(a['dchance'])[el]                      # (az, pen)
    def mean_dc(azs, pen): return float(np.mean([dc[az.index(x % 360), pens.index(pen)] for x in azs]))
    front = lambda pen: mean_dc([-10, -5, 0, 5, 10], pen)
    out = dict(FrontBounce70=100 * (1 - front(70)), FrontBounce85=100 * (1 - front(85)),
               AngledBounce70=100 * (1 - mean_dc([30, -30], 70)), SideBounce70=100 * (1 - mean_dc([80, 85, 90, 95, 100, -80, -85, -90, -95, -100], 70)),
               RearBounce70=100 * (1 - mean_dc([170, 175, 180, 185, 190], 70)), RoundBounce70=100 * (1 - float(dc[:, pens.index(70)].mean())),
               FrontEHP70=hp / max(front(70), 1e-3), FrontWeak70=front(70) * np.array(a['area'])[el][0], TreadShareSide=100 * float(np.mean([np.array(a['tread'])[el][az.index(x)] for x in (90, 270)])),
               FrontArea=np.array(a['area'])[el][0], SideArea=np.mean([np.array(a['area'])[el][az.index(90)], np.array(a['area'])[el][az.index(270)]]),
               Height=a['height_m'])
    return {k: float(v) for k, v in out.items()}
tanks = []
for tag, t in D['tanks'].items():
    base = derived(t['stats']); base.update(armor_stats(t['name'], base['MaxHealth']))
    # core-maxed: maximize each stat independently is not one build; use the single core front build (dps,alpha,hp,speed),
    # then also record per-stat talent ceilings (max reachable for that stat alone at 31 points).
    core = O.front(t, ['dps', 'alpha', 'hp', 'speed'], 31)
    best = max(core, key=lambda r: tuple(r[0]))
    cst = dict(t['stats']); cst.update(best[3])
    cst = derived(cst); cst.update(armor_stats(t['name'], cst['MaxHealth']))
    ceil = {}
    for k in ALL:
        F = O.front(t, [k], 31)
        st = dict(t['stats']); st.update(F[0][3]); ceil[k] = derived(st)[k]
    ceil['ClipDamage'] = ceil['ShellDamage'] * max(1, t['stats']['ClipSize'])
    ceil.update(armor_stats(t['name'], ceil['MaxHealth']))
    ceil['DPS'] = derived({**t['stats'], **max(O.front(t, ['dps'], 31), key=lambda r: r[0][0])[3]})['DPS']
    tanks.append(dict(id=t['plugin'].replace('TyrVehicle', ''), name=t['name'], pilot=t['pilot'], cls=t['cls'].replace('Tank', ''),
                      wip=t['wip'], base={s[0]: base[s[0]] for s in STATS}, core={s[0]: cst[s[0]] for s in STATS},
                      ceiling={s[0]: ceil.get(s[0], cst[s[0]]) for s in STATS}, core_points=sum(k for _, k in best[2]),
                      core_build=[(n['name'], k) for a, k in best[2] for n in t['tree']['nodes'] if n['tag'] == a]))
vary = lambda k: len({round(tk[m][k], 6) for tk in tanks for m in ('base', 'core', 'ceiling')}) > 1
STATS = [s for s in STATS if vary(s[0])]
# PCA on oriented z-scores of base stats (constant columns dropped)
keys = [s[0] for s in STATS if s[4] != 'Designer ratings' and s[0] not in ('Mass', 'ClipDamage')]
X = np.array([[tk['base'][k] for k in keys] for tk in tanks], float)
sd = X.std(0); keep = sd > 1e-9
keys = [k for k, m in zip(keys, keep) if m]; X = X[:, keep]
Z = (X - X.mean(0)) / X.std(0)
U, S, Vt = np.linalg.svd(Z, full_matrices=False)
var = S ** 2 / (S ** 2).sum()
# orient: camouflage pulls right on PC1, turret arc pulls up on PC2 (stable across patches)
for ax, k in ((0, 'CamoPercentage'), (1, 'MaxTurretRotation')):
    if k in keys and Vt[ax, keys.index(k)] < 0: Vt[ax] *= -1
P = Z @ Vt[:2].T
load = Vt[:2].T * S[:2] / np.sqrt(len(Z))   # correlations of stats with PCs
for tk, p in zip(tanks, P): tk['pca'] = [float(p[0]), float(p[1])]
Dm = np.sqrt(((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1)) / np.sqrt(Z.shape[1])
# average-linkage agglomerative order
clusters = [[i] for i in range(len(tanks))]
def cd(a, b): return np.mean([Dm[i, j] for i in a for j in b])
while len(clusters) > 1:
    i, j = min(((i, j) for i in range(len(clusters)) for j in range(i + 1, len(clusters))), key=lambda ij: cd(clusters[ij[0]], clusters[ij[1]]))
    clusters[i] = clusters[i] + clusters[j]; del clusters[j]
order = clusters[0]
def duel(angle):
    M = []
    for A in tanks:
        row = []
        for B in tanks:
            def ttk(att, dfn):
                a = ARM[dfn['name']]; el = a['el'].index(0); azs = [angle % 360, -angle % 360]
                pen = D_STATS[att['name']]['ShellPenetration']
                dch = float(np.mean([np.array(a['dchance'])[el][a['az'].index(x)][a['pen'].index(pen)] for x in azs]))
                return dfn['core']['MaxHealth'] / max(att['core']['DPS'] * dch, 1e-6)
            row.append(float(np.log2(ttk(B, A) / ttk(A, B))))   # >0: A kills B faster than B kills A
        M.append(row)
    return M
D_STATS = {t['name']: t['stats'] for t in D['tanks'].values()}
out_duel = dict(front=duel(0), angled=duel(30))
out = dict(duel=out_duel, source=D['source'], stats=[dict(key=k, label=l, unit=u, better=b, group=g) for k, l, u, b, g in STATS],
           tanks=tanks, pca=dict(keys=keys, var=[float(v) for v in var[:2]], loadings=[[float(a), float(b)] for a, b in load]),
           dist=[[float(x) for x in row] for row in Dm], order=order)
# armor detail for the armor charts (big: views are per-pixel effective armor)
open(os.path.join(O.ROOT, 'site/armor_data.js'), 'w').write('window.TYR_ARMOR = ' + json.dumps({n: {k: a[k] for k in ('az', 'el', 'pen', 'dchance', 'area', 'tread', 'crit', 'views', 'res_cm', 'dims_m', 'height_m')} for n, a in ARM.items()}, separators=(',', ':')) + ';\n')
open(os.path.join(O.ROOT, 'site/data.js'), 'w').write('window.TYR = ' + json.dumps(out, separators=(',', ':')) + ';\n')
print('tanks', len(tanks), 'pca var', var[:3].round(3), 'keys', len(keys))
for k, (a, b) in sorted(zip(keys, load), key=lambda x: -abs(x[1][0]))[:6]: print(f'  PC1 {k:28s} {a:+.2f}')
for k, (a, b) in sorted(zip(keys, load), key=lambda x: -abs(x[1][1]))[:6]: print(f'  PC2 {k:28s} {b:+.2f}')
print('order', [tanks[i]['name'] for i in order])
for i, tk in enumerate(tanks):
    j = min((j for j in range(len(tanks)) if j != i), key=lambda j: Dm[i, j]); print(f"  nearest {tk['name']:9s} -> {tanks[j]['name']:9s} {Dm[i, j]:.2f}")
