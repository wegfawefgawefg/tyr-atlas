"""Summarize GameplayEffect assets: duration, period, stacking, modifiers (attribute/op/calc), executions, granted tags.
usage: ge_summary.py <json root> -> prints one line per GE; importable: summarize(path)"""
import json, sys, os, glob
def short(s): return s.split('::')[-1] if isinstance(s, str) else s
def objname(o):
    if not o: return None
    if isinstance(o, dict):
        return (o.get('ObjectName') or o.get('AssetPathName') or '').split("'")[-2 if "'" in (o.get('ObjectName') or '') else -1].split('.')[-1]
    return str(o)
def summarize(path):
    j = json.load(open(path))
    cdo = next((e for e in j if e.get('Name', '').startswith('Default__')), None)
    if not cdo: return None
    P = cdo.get('Properties', {})
    out = dict(name=os.path.basename(path)[:-5], duration=short(P.get('DurationPolicy', 'Instant')))
    dm = P.get('DurationMagnitude', {}).get('ScalableFloatMagnitude', {}).get('Value')
    if dm: out['dur_s'] = dm
    per = P.get('Period', {}).get('Value')
    if per: out['period'] = per
    mods = []
    for m in P.get('Modifiers', []):
        mm = m.get('ModifierMagnitude', {})
        calc = short(mm.get('MagnitudeCalculationType', 'ScalableFloat'))
        mag = None
        if calc == 'ScalableFloat': mag = mm.get('ScalableFloatMagnitude', {}).get('Value')
        elif calc == 'CustomCalculationClass': mag = objname(mm.get('CustomMagnitude', {}).get('CalculationClassMagnitude'))
        elif calc == 'AttributeBased':
            ab = mm.get('AttributeBasedMagnitude', {})
            mag = f"{ab.get('Coefficient',{}).get('Value')}*{ab.get('BackingAttribute',{}).get('AttributeToCapture',{}).get('AttributeName')}"
        elif calc == 'SetByCaller': mag = 'SetByCaller:' + str(mm.get('SetByCallerMagnitude', {}).get('DataTag', {}).get('TagName'))
        mods.append((m['Attribute'].get('AttributeName'), short(m.get('ModifierOp')), mag))
    if mods: out['mods'] = mods
    ex = [objname(e.get('CalculationClass')) for e in P.get('Executions', [])]
    if ex: out['exec'] = ex
    st = short(P.get('StackingType'))
    if st and st != 'None': out['stack'] = (st, P.get('StackLimitCount'))
    comps = [objname(c) for c in P.get('GEComponents', [])]
    if comps: out['comps'] = comps
    return out
if __name__ == '__main__':
    for f in sorted(glob.glob(sys.argv[1] + '/**/GE_*.json', recursive=True)):
        s = summarize(f)
        if s: print(json.dumps(s))
