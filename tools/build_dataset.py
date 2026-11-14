"""Normalize extracted Tyr data into data/tyr.json (tanks, talent trees, components, ammo, effects).
inputs: extract/json (CUE4Parse dumps), extract/cdn/talent-trees-*.json (live tree layout)"""
import json, glob, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from ge_summary import summarize
ROOT = os.path.join(os.path.dirname(__file__), '..')
J = os.path.join(ROOT, 'extract/json/Tyr')

def rows(path):
    for e in json.load(open(path)):
        if e.get('Rows') is not None: return e['Rows']
    return {}

def string_table(asset_path):
    """'/TyrVehicleRam/ST_Vehicle_Ram.ST_Vehicle_Ram' or '/Game/Text/X.X' -> dict"""
    p = asset_path.split('.')[0]
    f = os.path.join(J, 'Content', p[len('/Game/'):]) if p.startswith('/Game/') else \
        os.path.join(J, 'Plugins/GameFeatures/Vehicles', p.strip('/').split('/')[0], 'Content', *p.strip('/').split('/')[1:])
    f += '.json'
    if not os.path.exists(f): return {}
    def find(o):
        if isinstance(o, dict):
            if 'KeysToEntries' in o: return o['KeysToEntries']
            for v in o.values():
                r = find(v)
                if r: return r
        if isinstance(o, list):
            for v in o:
                r = find(v)
                if r: return r
    return find(json.load(open(f))) or {}
_st = {}
def text(t):
    if not isinstance(t, dict): return t
    if t.get('SourceString'): return t['SourceString']
    if t.get('TableId'):
        tid = t['TableId']
        if tid not in _st: _st[tid] = string_table(tid)
        return _st[tid].get(t.get('Key'), t.get('Key'))
    return t.get('CultureInvariantString')

GE_INDEX = {os.path.basename(f)[:-5]: f for f in glob.glob(J + '/**/GE_*.json', recursive=True)}
GES = {}
def ge(path):
    n = path.split('/')[-1].split('.')[0]
    if not n: return None
    if n not in GES:
        GES[n] = summarize(GE_INDEX[n]) if n in GE_INDEX else {'name': n, 'missing': True}
    return n
def effects(row, prefix):
    out = []
    g = row.get(prefix + 'GameplayEffect', {}).get('AssetPathName')
    if g: out.append({'event': 'Direct', 'ge': ge(g)})
    for p in row.get('EventEffectPairs', []):
        out.append({'event': p['EventTag']['TagName'].replace('Gameplay.Event.', ''),
                    'ge': ge(p[prefix + 'GameplayEffect']['AssetPathName']) if p[prefix + 'GameplayEffect']['AssetPathName'] else None})
    return out

trees_file = sorted(glob.glob(os.path.join(ROOT, 'extract/cdn/talent-trees-*.json')))[-1]
TREES = json.load(open(trees_file))
tanks = {}
for d in sorted(glob.glob(J + '/Plugins/GameFeatures/Vehicles/*/Content')):
    tf = d + '/DT_TankData.json'
    if not os.path.exists(tf): continue
    for tag, r in rows(tf).items():
        base = {k: v for k, v in r.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        t = dict(tag=tag, plugin=d.split('/')[-2], name=text(r['VehicleName']), pilot=text(r['DisplayName']),
                 cls=r['VehicleClass'], wip=r['bIsWorkInProgress'], description=text(r['TankDescription']),
                 ability=text(r['AbilityDescription']), stats=base, tree=None)
        talents = rows(d + '/DT_TalentTreeData.json') if os.path.exists(d + '/DT_TalentTreeData.json') else {}
        tr = TREES['trees'].get(tag)
        if tr:
            nodes = []
            for n in tr['tech_nodes']:
                row = talents.get(n['gameplay_tag'], {})
                nodes.append(dict(tag=n['gameplay_tag'], tier=n['tier'], row=n['row'], max=n['max_points'],
                                  prereq=n['prerequisites'], keystone=n['is_keystone'],
                                  name=text(row.get('TalentName')), desc=text(row.get('TalentDescription')),
                                  values=row.get('TalentPointValues'), effects=effects(row, 'Talent') if row else [],
                                  missing_row=not row))
            t['tree'] = dict(meta=tr['metadata'], nodes=sorted(nodes, key=lambda n: (n['tier'], n['row'])))
        attrs = d + '/DT_VehicleSpecificAttributeData.json'
        if os.path.exists(attrs): t['vehicle_attrs'] = rows(attrs)
        tanks[tag] = t

comps = {}
for tag, r in rows(J + '/Content/DataTables/DT_ComponentData.json').items():
    comps[tag] = dict(tag=tag, name=text(r['ComponentName']), desc=text(r['ComponentDescription']),
                      note=text(r['ComponentSupplementalDescription']), values=r['ComponentPointValues'],
                      categories=[c.split('.')[-1] for c in r['Categories']], effects=effects(r, 'Component'))
ammo = {}
for tag, r in rows(J + '/Content/DataTables/DT_AmmunitionUIData.json').items():
    ammo[tag] = {k: (text(v) if isinstance(v, dict) and ('SourceString' in v or 'TableId' in v) else v)
                 for k, v in r.items() if not (isinstance(v, dict) and 'AssetPathName' in v)}
out = dict(source=dict(steam_buildid=26309825, talent_tree_version=TREES['version'], trees_file=os.path.basename(trees_file)),
           tanks=tanks, components=comps, ammo=ammo, effects=GES)
os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'data/tyr.json'), 'w'), indent=1)
print('tanks', len(tanks), 'with trees', sum(1 for t in tanks.values() if t['tree']), 'components', len(comps), 'ammo', len(ammo), 'effects', len(GES),
      'missing GE', sum(1 for g in GES.values() if g.get('missing')))
for t in tanks.values():
    s = t['stats']
    print(f"{t['plugin'][10:]:10s} {str(t['name']):12s} {t['cls']:11s} wip={int(t['wip'])} HP {s['MaxHealth']:6.0f} dmg {s['ShellDamage']:5.0f} pen {s['ShellPenetration']:4.0f} reload {s['ReloadTime']:4.1f} clip {s['ClipSize']} spd {s['MaxSpeed']:4.0f} camo {s['CamoPercentage']:4.1f} view {s['VisionRadius']:4.0f}")
