"""Component model: score talent build + 3 components per tank under named scenarios.

Everything numeric comes from data/tyr.json (component point values, fixed GE magnitudes, tank stats,
class energy rates). Trigger semantics are hand-coded per component from the GE structure (see
docs/components.md) because events like "OnBounceEnemyShot" need a rate model, not a flag.

Stat aggregation follows GAS: (base + sum add) * (1 + sum(mult - 1)) / (1 + sum(div - 1)) * prod(compound).
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
import optimize as O

D = O.D
ROOT = O.ROOT
COMP = D['components']
cv = lambda name: COMP['Gameplay.Components.' + name]['values'][0]
CLASS_ENERGY = {'DamageDealt': 0.035, 'DamageTaken': 0.005, 'DamageBlocked': 0.005, 'Assist': 0.03}  # DT_VehicleClassData, same for all classes

# ---- reference engagement (explicit assumptions, shown on the site) ----
def median(xs):
    xs = sorted(xs); n = len(xs); return (xs[n // 2] + xs[(n - 1) // 2]) / 2
def base_dps(st):
    clip = max(1, st['ClipSize']); return st['ShellDamage'] * clip / (st['ReloadTime'] + (clip - 1) * st['IntraClipReloadTime'])
REF = dict(
    fight_s=60.0,                                     # engagement length
    enemy_dps=median([base_dps(t['stats']) for t in D['tanks'].values()]),
    enemy_alpha=median([t['stats']['ShellDamage'] for t in D['tanks'].values()]),
    incoming_bounce=0.25,                             # share of enemy shots that bounce off you
    incoming_module=0.30,                             # share of enemy hits that damage one of your modules
    our_pen=0.80,                                     # share of our shots that penetrate
    our_module=0.30,                                  # share of our hits that damage an enemy module
    alt_share=0.0,                                    # share of shots that are alt shells (set per scenario)
)
SCENARIOS = {
    'static':   dict(label='Static only', desc='Only always-on effects. Nothing situational counts.', flags=set()),
    'sniping':  dict(label='Sniping', desc='Stationary, unspotted, firing as soon as the reload ends, not under fire.',
                     flags={'stationary', 'unspotted', 'snap_fire'}),
    'brawling': dict(label='Brawling', desc='Spotted for 20 s or more, under fire from the reference enemy, moving under 40 kph, snap firing.',
                     flags={'spotted_long', 'taking_fire', 'snap_fire', 'pen_streak', 'ability_cycle'}),
    'flanking': dict(label='Flanking', desc='Moving over 40 kph (if the tank can), unspotted, cruising more than 10 s, snap firing.',
                     flags={'over40', 'unspotted', 'cruising', 'snap_fire', 'pen_streak'}),
}

ATTRS = ['ShellDamage', 'ReloadTime', 'IntraClipReloadTime', 'MaxHealth', 'MaxSpeed', 'MaxReverseSpeed', 'CamoPercentage',
         'DispersionReductionSpeed', 'BaseDispersionPenalty', 'HullTraverseSpeed', 'AbilityCost', 'AbilityCooldownTwo',
         'MaxAbilityResource', 'InitialAbilityResource', 'SpottedTime', 'ModuleRepairTimeMultiplier', 'ExtraDamageToModulesPercent']

def talent_mods(tank, alloc):
    """(attr, op, value) list for an allocation [(tag, points)], unconditional talent effects only"""
    nodes = {n['tag']: n for n in tank['tree']['nodes']}
    out = []
    for tag, k in alloc:
        n = nodes[tag]
        for ef in n['effects']:
            g = D['effects'].get(ef['ge']) if ef['ge'] else None
            if ef['event'] not in O.UNCONDITIONAL or not g or not g.get('mods'): continue
            for attr, op, mag in g['mods']:
                if mag == 'TyrTalentMagCalculation' and n['values']:
                    out.append((attr, op, n['values'][min(k, len(n['values'])) - 1]))
    return out

def aggregate(base, mods):
    st = dict(base)
    st['AbilityCooldownTwo'] = base.get('AbilityCooldown', 0)
    for a in ATTRS + ['AbilityCooldownTwo']:
        add = sum(v for x, op, v in mods if x == a and op == 'Additive')
        mul = sum(v - 1 for x, op, v in mods if x == a and op == 'Multiplicitive')
        div = sum(v - 1 for x, op, v in mods if x == a and op == 'Division')
        cmp = math.prod(v for x, op, v in mods if x == a and op == 'MultiplyCompound')
        st[a] = (st.get(a, 0) + add) * (1 + mul) / (1 + div) * cmp
    return st

def evaluate(tank, alloc, comps, scen, ref=REF):
    """metrics dict for one talent allocation + component set in one scenario"""
    f = SCENARIOS[scen]['flags']
    base = tank['stats']
    if scen == 'static':   # always-on effects only: drop every event-triggered component
        comps = [c for c in comps if c not in EVENT_ONLY]
    can40 = base['MaxSpeed'] > 40
    over40 = 'over40' in f and can40
    mods = talent_mods(tank, alloc)
    has = set(comps)
    notes = []
    # ---- stat modifiers ----
    if 'EnergyExpander' in has: mods += [('MaxAbilityResource', 'Multiplicitive', cv('EnergyExpander')), ('InitialAbilityResource', 'Multiplicitive', cv('EnergyExpander'))]
    if 'CamoWeb' in has and 'stationary' in f: mods.append(('CamoPercentage', 'Multiplicitive', cv('CamoWeb')))
    if 'ShiftCloak' in has and 'unspotted' in f: mods.append(('CamoPercentage', 'Additive', cv('ShiftCloak')))
    if 'RepairMechanism' in has: mods.append(('ModuleRepairTimeMultiplier', 'Multiplicitive', cv('RepairMechanism')))
    if 'HotChamber' in has and 'snap_fire' in f: pass  # handled per shot below
    if 'SenseOverdrive' in has and ('spotted_long' in f): mods += [('MaxSpeed', 'Additive', cv('SenseOverdrive')), ('MaxReverseSpeed', 'Additive', cv('SenseOverdrive'))]
    if 'CoreInjector' in has: mods.append(('AbilityCost', 'Multiplicitive', cv('CoreInjector')))
    if 'SensitiveSights' in has and 'unspotted' in f: mods += [('DispersionReductionSpeed', 'Multiplicitive', cv('SensitiveSights')), ('ReloadTime', 'Multiplicitive', 0.85)]
    if 'Duplicator' in has: mods.append(('ShellDamage', 'Additive', 5.0))
    if 'Bulkheads' in has: mods.append(('MaxHealth', 'Multiplicitive', cv('Bulkheads')))
    if 'Synchronizer' in has: mods.append(('InitialAbilityResource', 'Additive', 7.5))
    if 'PowerConverter' in has: mods.append(('AbilityCooldownTwo', 'Multiplicitive', cv('PowerConverter')))
    if 'Agitator' in has: mods += [('DispersionReductionSpeed', 'Multiplicitive', cv('Agitator')), ('BaseDispersionPenalty', 'Multiplicitive', 0.9)]
    if 'ModuleSurger' in has: mods.append(('MaxHealth', 'Additive', cv('ModuleSurger')))
    if 'ShellStabilizer' in has and 'stationary' in f: mods.append(('ShellDamage', 'Additive', cv('ShellStabilizer')))
    if 'MomentumImparter' in has and over40: mods.append(('ShellDamage', 'Additive', cv('MomentumImparter')))
    if 'ExtendedGearing' in has and 'cruising' in f: mods.append(('MaxSpeed', 'Multiplicitive', cv('ExtendedGearing')))
    if 'FrictionCapacitor' in has: mods.append(('MaxSpeed', 'Additive', cv('FrictionCapacitor')))
    if 'SignatureObscurer' in has: mods.append(('SpottedTime', 'Additive', cv('SignatureObscurer')))
    if 'RedirectorGear' in has: mods.append(('HullTraverseSpeed', 'Multiplicitive', cv('RedirectorGear')))
    if 'SidescrapeGear' in has and 'stationary' in f: mods.append(('HullTraverseSpeed', 'Multiplicitive', cv('SidescrapeGear')))
    if 'VulnBreaker' in has: mods.append(('ExtraDamageToModulesPercent', 'Additive', cv('VulnBreaker')))
    if 'QuickSlot' in has and ref['alt_share'] > 0: mods.append(('ReloadTime', 'Multiplicitive', 1 - (1 - cv('QuickSlot')) * ref['alt_share']))
    st = aggregate(base, mods)

    # ---- damage per shot ----
    clip = max(1, int(base['ClipSize']))
    shot = st['ShellDamage']
    if 'ShellCharger' in has and 'pen_streak' in f:
        p = ref['our_pen']; P1, P2, P3 = p * (1 - p), p * p * (1 - p), p ** 3
        shot += cv('ShellCharger') * (P1 + 2 * P2 + 3 * P3)
    hot_share = 0.0
    if 'HotChamber' in has and 'snap_fire' in f:
        within = 1 + (int(2.0 // st['IntraClipReloadTime']) if clip > 1 and st['IntraClipReloadTime'] > 0 else 0)
        hot_share = min(clip, within) / clip
    shot_mult = 1 + (cv('HotChamber') - 1) * hot_share   # HotChamber is Multiplicitive on base ShellDamage

    # ---- reload with active-reload reductions ----
    reload = st['ReloadTime']
    speedup = 0.0   # extra reload seconds removed per real second while reloading
    taking = 'taking_fire' in f
    in_rate = ref['enemy_dps'] / ref['enemy_alpha'] if taking else 0.0      # enemy shots per second at us
    if 'PhaseModule' in has and over40: speedup += -cv('PhaseModule')
    if 'KineticAbsorber' in has: speedup += -cv('KineticAbsorber') * in_rate * ref['incoming_bounce']
    if 'WeaknessAnalyzer' in has:
        cycle0 = reload + (clip - 1) * st['IntraClipReloadTime']
        mod_rate = clip / cycle0 * ref['our_pen'] * ref['our_module']
        speedup += cv('WeaknessAnalyzer') * min(mod_rate, 1 / 6.0)
    reload_eff = reload / (1 + speedup)
    cycle = reload_eff + (clip - 1) * st['IntraClipReloadTime']
    # Overflow Shunt: +0.1% outgoing damage per energy held; use the scenario's average held energy (computed below, one pass)
    hit_share = ref['our_pen']
    shots_per_s = clip / cycle

    # ---- energy economy (per second) ----
    flat_per_gain = cv('CoreBooster') if 'CoreBooster' in has else 0.0
    e_rate = None
    def energy_rate(dps_out):
        r = dps_out * CLASS_ENERGY['DamageDealt'] + shots_per_s * hit_share * flat_per_gain
        if taking:
            r += ref['enemy_dps'] * (1 - ref['incoming_bounce']) * CLASS_ENERGY['DamageTaken']
            r += ref['enemy_dps'] * ref['incoming_bounce'] * CLASS_ENERGY['DamageBlocked']
            r += in_rate * flat_per_gain
        if 'CatalyticReservoir' in has: r += shots_per_s * hit_share * cv('CatalyticReservoir') * 0.5   # only above 50 energy: assume half the time
        return r

    dps_raw = shot * shot_mult * clip / cycle * hit_share
    e_rate = energy_rate(dps_raw)
    cost = st['AbilityCost']; cd = st['AbilityCooldownTwo']
    if 'CascadeGate' in has: e_rate *= 1 + cv('CascadeGate') * min(1.0, 15.0 / max(cd, cost / max(e_rate, 1e-6)))
    if 'CoreAmp' in has: e_rate_amp = cv('CoreAmp') * ref['our_pen']
    else: e_rate_amp = 0.0
    # ability cycle: limited by cooldown or by energy (start with InitialAbilityResource)
    def uses_in(T):
        # expected uses over the fight (continuous, so tiny energy changes give tiny changes):
        # limited by energy (start + income, Core Amp refunds part of each use) and by cooldown
        per_use = max(cost - e_rate_amp, 1e-6)
        by_energy = max(0.0, (st['InitialAbilityResource'] + e_rate * T)) / per_use
        by_cd = T / max(cd, 1e-6) + 1
        return min(by_energy, by_cd)
    uses = uses_in(ref['fight_s'])
    # Overflow Shunt: average energy held. If the ability is used, energy hovers between 0 and cost; otherwise it fills up.
    if 'OverflowShunt' in has:
        held = min(st['MaxAbilityResource'], (cost / 2 if uses else st['InitialAbilityResource'] + e_rate * ref['fight_s'] / 2))
        shot_mult *= 1 + 0.001 * held
        notes.append(f'Overflow Shunt at ~{held:.0f} energy held')
    dps = shot * shot_mult * clip / cycle * hit_share

    # ---- survivability over the reference fight ----
    hp = st['MaxHealth']
    flat = cv('MicroPlating') if 'MicroPlating' in has else 0.0
    dr = 0.0
    if 'AdaptiveHardening' in has and 'spotted_long' in f: dr += 0.12
    alpha_in = ref['enemy_alpha']
    per_hit_scale = max(0.0, (alpha_in - flat) / alpha_in) * (1 - dr)
    heal = 0.0
    hits_in = in_rate * (1 - ref['incoming_bounce']) * ref['fight_s'] if taking else 0.0
    bounces_in = in_rate * ref['incoming_bounce'] * ref['fight_s'] if taking else 0.0
    if 'Densifier' in has: heal += 16 * bounces_in + 8 * hits_in; hp += 0  # max HP grows and heals the same: counts as healing here
    if 'RelentlessAdapter' in has: heal += cv('RelentlessAdapter') * hits_in * ref['incoming_module']
    if 'PowerConverter' in has and scen != 'static': heal += cost * uses
    if 'PropagationDrive' in has: heal += cv('PropagationDrive') * uses; shot_bonus_pd = 2 * uses / 2  # average over fight
    else: shot_bonus_pd = 0.0
    if shot_bonus_pd: dps += shot_bonus_pd * shot_mult * clip / cycle * hit_share
    ehp = hp / max(per_hit_scale, 1e-6) + heal / max(per_hit_scale, 1e-6) if per_hit_scale > 0 else float('inf')
    speed = st['MaxSpeed']
    if 'SenseOverdrive' in has and 'spotted_long' not in f: pass
    return dict(dps=dps, alpha=shot * shot_mult, ehp=ehp, hp=st['MaxHealth'], speed=speed, camo=st['CamoPercentage'],
                aim=st['DispersionReductionSpeed'], reload=reload_eff, uses=uses, energy_s=e_rate, cost=cost, cd=cd,
                heal=heal, duel=dps * ehp, notes=notes)

COMP_IDS = [k.split('.')[-1] for k in COMP]
# no effect on damage or survivability in this model (speed bursts, ram heals, alt-shell supply, precision aim timing)
NOT_SCORED = {'DriftSparker', 'EnergyVent', 'Fabricator', 'HullBellows', 'ReactiveModules', 'StableRangefinder'}
# components whose whole effect needs an in-fight event (hit, bounce, ability use, module damage...)
EVENT_ONLY = {'KineticAbsorber', 'Fabricator', 'WeaknessAnalyzer', 'CoreAmp', 'ReactiveModules', 'RelentlessAdapter',
              'ShellCharger', 'CatalyticReservoir', 'CascadeGate', 'Densifier', 'HullBellows', 'EnergyVent', 'PropagationDrive',
              'HotChamber', 'StableRangefinder', 'DriftSparker'}

def core_alloc(tank):
    F = O.front(tank, ['dps', 'alpha', 'hp', 'speed'], 31)
    return max(F, key=lambda r: tuple(r[0]))[2]

if __name__ == '__main__':
    import time
    out = {}
    for tag, tank in D['tanks'].items():
        alloc = core_alloc(tank)
        t0 = time.time()
        res = {}
        for scen in SCENARIOS:
            base = evaluate(tank, alloc, [], scen)
            single = {c: evaluate(tank, alloc, [c], scen) for c in COMP_IDS}
            res[scen] = dict(base=base, single=single)
        out[tank['name']] = res
        b = res['brawling']
        best = sorted(COMP_IDS, key=lambda c: -b['single'][c]['duel'])[:4]
        print(f"{tank['name']:9s} brawl duel x{''} " + ', '.join(f"{c} {b['single'][c]['duel']/b['base']['duel']-1:+.1%}" for c in best), f'{time.time()-t0:.1f}s')
