"""Combat derived stats -> data/combat.json and site/combat_data.js

1. shots to kill (core builds), expected shots with even-spread and aimed hits, alpha breakpoints + levers
2. aimed weak spots: best aim point damage chance for a circular Gaussian spread sigma (m), per view and pen
3. hull-down: exposure above the gun line from the front, its armor
4. ammo: per attacker x ammo x defender, damage per shot fired at the front
5. turret yaw armor (from armor.json)
6. ram: kinetic energy and momentum at top speed
7. tread area per direction (radar)
8. size vs camouflage
"""
import json, os, sys, math
import numpy as np
from scipy.ndimage import gaussian_filter
sys.path.insert(0, os.path.dirname(__file__))
import optimize as O

ROOT = O.ROOT
D = O.D
ARM = json.load(open(os.path.join(ROOT, 'data/armor.json')))
AUTO, OVER, FIFTY = 80.0, 4.0, 1.25
SIGMAS = [0.1, 0.25, 0.5, 1.0, 2.0]          # metres, 1-sigma of a circular Gaussian spread around the aim point
AIM_PENS = [50, 60, 70, 80, 85, 90, 100, 120, 135]
REF_SIGMA = 0.5
CRIT = {2: 'bonus', 3: 'fire', 4: 'engine', 5: 'gun', 6: 'turret', 7: 'ability'}
BONUS_DMG = 0.5          # BPC_ModuleBonusComponent.BonusDamageAmount
FIRE_DMG = 20.0 * 8.0    # BPC_ModuleFireComponent: 20 per second until repaired, first repair 8 s (then 4, 2, 0 within 10 s)
CRIT_SIGMAS = [0.25, 0.5]

def core_stats(tank):
    F = O.front(tank, ['dps', 'alpha', 'hp', 'speed'], 31)
    best = max(F, key=lambda r: tuple(r[0]))
    st = dict(tank['stats']); st.update(best[3])
    clip = max(1, st['ClipSize'])
    st['DPS'] = st['ShellDamage'] * clip / (st['ReloadTime'] + (clip - 1) * st['IntraClipReloadTime'])
    return st

TANKS = {t['name']: t for t in D['tanks'].values()}
CORE = {n: core_stats(t) for n, t in TANKS.items()}
NAMES = list(TANKS)

def dchance(name, az, pen, el=0):
    """damage chance at arbitrary pen by interpolating the pen grid"""
    a = ARM[name]; ei = a['el'].index(el); ai = a['az'].index(az % 360)
    return float(np.interp(pen, a['pen'], np.array(a['dchance'])[ei, ai]))

def damage_map(view, pen):
    eff = np.array(view['eff'], float).reshape(view['h'], view['w']); mod = np.array(view['mod']).reshape(view['h'], view['w'])
    inside = eff >= 0
    p = np.where(eff <= pen, 1.0, np.where(eff <= pen * FIFTY, 0.5, 0.0))
    p = np.where(eff == 999, 0.0, p)
    if 't' in view:                       # overmatch: pen >= 4x raw thickness goes through at any angle
        t = np.array(view['t'], float).reshape(view['h'], view['w'])
        p = np.where(inside & (pen >= OVER * t), 1.0, p)
    p = np.where(mod == 1, 0.0, p)        # treads: no HP damage (crit modules follow the normal rule)
    return np.where(inside, p, 0.0), inside

def pen_map(view, pen):
    """per-pixel penetration chance including crit modules (treads still count as penetrable here)"""
    eff = np.array(view['eff'], float).reshape(view['h'], view['w'])
    p = np.where(eff <= pen, 1.0, np.where(eff <= pen * FIFTY, 0.5, 0.0))
    p = np.where(eff == 999, 0.0, p)
    if 't' in view:
        t = np.array(view['t'], float).reshape(view['h'], view['w'])
        p = np.where((eff >= 0) & (pen >= OVER * t), 1.0, p)
    return np.where(eff >= 0, p, 0.0)

def crit_best(view, pen, sigma_m, res_cm):
    mod = np.array(view['mod']).reshape(view['h'], view['w']); p = pen_map(view, pen); s = sigma_m * 100 / res_cm
    return {name: float(gaussian_filter(p * (mod == k), s, mode='constant').max()) for k, name in CRIT.items() if (mod == k).any()}

def aimed_damage(view, pen, alpha, sigma_m, res_cm):
    """expected HP damage per shot at the best aim point, counting bonus crits (+50%) and the first fire (160)"""
    mod = np.array(view['mod']).reshape(view['h'], view['w']); p = pen_map(view, pen) * (mod != 1)
    dmg = p * alpha * (1 + BONUS_DMG * (mod == 2)) + p * FIRE_DMG * (mod == 3)
    return float(gaussian_filter(dmg, sigma_m * 100 / res_cm, mode='constant').max())

def aimed(view, pen, sigma_m, res_cm):
    """best aim point: max over pixels of the Gaussian-blurred damage map (misses off the silhouette count as no damage)"""
    p, inside = damage_map(view, pen)
    s = sigma_m * 100 / res_cm
    blurred = gaussian_filter(p, s, mode='constant')
    return float(blurred.max())

out = dict(sigmas=SIGMAS, aim_pens=AIM_PENS, ref_sigma=REF_SIGMA, tanks={})
# ---- per tank derived ----
for n, t in TANKS.items():
    a = ARM[n]; st = CORE[n]; base = t['stats']; res = a['res_cm']
    el0 = a['el'].index(0)
    views = a['views']
    aim = {}
    for vk in ('front', 'front30', 'left', 'rear'):
        if vk in views:
            aim[vk] = [[round(aimed(views[vk], pen, s, res), 4) for s in SIGMAS] for pen in AIM_PENS]
    # hull-down: front view rows above (gun height - 25 cm)
    fv = views['front']; H, W = fv['h'], fv['w']
    gun_z = a['bone_z_cm'].get('jnt_gun', a['bone_z_cm'].get('jnt_turret', 0))
    line = gun_z - 25
    rows_z = fv['y0_cm'] + (H - 1 - np.arange(H) + 0.5) * res        # view rows were flipped so row 0 is the top
    expose = (rows_z >= line)[:, None] & (np.array(fv['eff']).reshape(H, W) >= 0)
    full_area = (np.array(fv['eff']) >= 0).sum() * (res / 100) ** 2
    hd_area = expose.sum() * (res / 100) ** 2
    hd = {}
    for pen in AIM_PENS:
        pm, _ = damage_map(fv, pen)
        hd[pen] = round(float(pm[expose].mean()) if expose.any() else 0.0, 4)
    crit = {vk: {str(pen): {str(sg): crit_best(views[vk], pen, sg, res) for sg in CRIT_SIGMAS} for pen in AIM_PENS}
            for vk in ('front', 'front30', 'left', 'rear') if vk in views}
    crit_area = {}
    for vk in ('front', 'left', 'rear'):
        md = np.array(views[vk]['mod'])
        crit_area[vk] = {name: round(float((md == k).sum()) * (res / 100) ** 2, 3) for k, name in CRIT.items() if (md == k).any()}
    tread_area = [round(a['tread'][el0][i] * a['area'][el0][i], 3) for i in range(len(a['az']))]
    v_ms = st['MaxSpeed'] / 3.6; m_kg = base['Mass']
    out['tanks'][n] = dict(
        aim=aim, crit=crit, crit_area=crit_area,
        hulldown=dict(gun_height_m=round(gun_z / 100, 2), exposed_m2=round(hd_area, 2), full_m2=round(full_area, 2),
                      exposed_share=round(hd_area / max(full_area, 1e-6), 3), dchance=hd, depression_deg=-base['GunMaxDepression']),
        yaw=a['yaw'], tread=dict(az=a['az'], area=tread_area),
        ram=dict(mass_t=m_kg / 1000, speed_kph=st['MaxSpeed'], ke_mj=round(0.5 * m_kg * v_ms ** 2 / 1e6, 3), momentum_t_ms=round(m_kg * v_ms / 1000, 1)),
        size=dict(front_m2=a['area'][el0][0], side_m2=a['area'][el0][a['az'].index(90)], height_m=a['height_m'], camo=base['CamoPercentage'],
                  side_exposure=round(a['area'][el0][a['az'].index(90)] * (1 - base['CamoPercentage'] / 100), 2)),
    )
    print(f"{n:9s} hull-down exposes {hd_area:4.1f} of {full_area:4.1f} m2 (gun at {gun_z/100:.2f} m) dmg@70 {hd[70]:.2f} | aimed front @0.5m vs70 {aim['front'][AIM_PENS.index(70)][SIGMAS.index(0.5)]:.2f}", flush=True)

# ---- shots to kill, expected shots, breakpoints, levers ----
LEVERS_ATT = [  # (name, kind, value): alpha changes an attacker can make
    ('Duplicator (+5)', 'add', 5.0), ('Shell Stabilizer, stationary (+10)', 'add', 10.0),
    ('Shell Charger, 3 stacks (+25.5)', 'add', 25.5), ('Momentum Imparter, over 40 kph (+30)', 'add', 30.0),
    ('Hot Chamber (x1.12)', 'mul', 0.12), ('HE / Gargantuan / HighPen ammo (x1.2)', 'ammo', 1.2),
    ('Momentum ammo (x1.3)', 'ammo', 1.3), ('Unstable ammo (x1.1)', 'ammo', 1.1)]
LEVERS_DEF = [('Bulkheads (x1.085 HP)', 'mul', 0.085), ('Mobility Surger (+100 HP)', 'add', 100.0)]
stk = {}
for A in NAMES:
    sa = CORE[A]; alpha = sa['ShellDamage']; pen = TANKS[A]['stats']['ShellPenetration']
    row = {}
    for B in NAMES:
        if A == B: continue
        hp = CORE[B]['MaxHealth']
        k = math.ceil(hp / alpha - 1e-9)
        dc_even = dchance(B, 0, pen)
        fa = out['tanks'][B]['aim']['front']
        dc_aim = float(np.interp(pen, AIM_PENS, [r[SIGMAS.index(REF_SIGMA)] for r in fa]))
        need = hp / (k - 1) if k > 1 else None
        levers = []
        if need:
            base_add = TANKS[A]['stats']['ShellDamage']
            for name, kind, v in LEVERS_ATT:
                if name.startswith('Momentum Imparter') and sa['MaxSpeed'] <= 40: continue
                new = alpha + v if kind == 'add' else alpha * (1 + v) if kind == 'mul' else alpha * v
                if new >= need - 1e-9: levers.append(name)
        safe = []
        for name, kind, v in LEVERS_DEF:
            hp2 = hp + v if kind == 'add' else hp * (1 + v)
            if math.ceil(hp2 / alpha - 1e-9) > k: safe.append(name)
        row[B] = dict(stk=k, even=round(k / max(dc_even, 1e-3), 2), aimed=round(k / max(dc_aim, 1e-3), 2),
                      dc_even=round(dc_even, 3), dc_aim=round(dc_aim, 3), next_alpha=round(need, 1) if need else None,
                      levers=levers, def_levers=safe)
    stk[A] = row
out['stk'] = stk
aimdmg = {}
for A in NAMES:
    alpha = CORE[A]['ShellDamage']; pen = TANKS[A]['stats']['ShellPenetration']
    aimdmg[A] = {}
    for B in NAMES:
        if A == B: continue
        v = ARM[B]['views']; res = ARM[B]['res_cm']
        aimdmg[A][B] = {f'{vk}_{sg}': round(aimed_damage(v[vk], pen, alpha, sg, res), 1) for vk in ('front', 'left') for sg in CRIT_SIGMAS}
        aimdmg[A][B]['plain_front'] = round(alpha * dchance(B, 0, pen), 1)
out['aimed_damage'] = aimdmg
out['crit_values'] = dict(bonus=BONUS_DMG, fire_total=FIRE_DMG, repair=[8, 4, 2, 0])
out['levers_att'] = [l[0] for l in LEVERS_ATT]; out['levers_def'] = [l[0] for l in LEVERS_DEF]

# ---- ammo layer: damage per shot fired at the front ----
AM = json.load(open(os.path.join(ROOT, 'extract/json/Tyr/Content/DataTables/DT_AmmunitionUIData.json')))[0]['Rows']
ammo = {}
for k, r in AM.items():
    nm = k.split('.')[-1]
    if r['PenetrationModifier'] == 0: continue
    ammo[nm] = dict(dmg=r['DamageModifier'], pen=r['PenetrationModifier'], disp=r['DispersionModifier'], vel=r['VelocityModifier'],
                    selectable=bool(r['bIsSelectable'] and not r['bIsHidden']), secondary=bool(r['bCanBeLoadedInSecondary']))
out['ammo'] = ammo
amat = {}
for A in NAMES:
    alpha = CORE[A]['ShellDamage']; pen = TANKS[A]['stats']['ShellPenetration']
    amat[A] = {am: {B: round(alpha * v['dmg'] * dchance(B, 0, pen * v['pen']), 1) for B in NAMES if B != A} for am, v in ammo.items()}
out['ammo_vs_front'] = amat

json.dump(out, open(os.path.join(ROOT, 'data/combat.json'), 'w'))
open(os.path.join(ROOT, 'site/combat_data.js'), 'w').write('window.TYR_COMBAT = ' + json.dumps(out, separators=(',', ':')) + ';\n')
print('stk example: Arbalest vs Atlas', stk['Arbalest']['Atlas'])
print('Ikarus vs Alecto', stk['Ikarus']['Alecto'])
