"""Build a .usmap from the static reflection scan (tools/reflect_scan.py pickle).
usage: make_usmap.py <stage1.pkl> <out.usmap>"""
import sys, pickle, struct, re
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from pe import PE
import xfunc

EXE = '/path/to/SteamLibrary/steamapps/common/Tyr/Tyr/Binaries/Win64/TyrClient-Win64-Shipping.exe'
p = PE(EXE); d = p.d
R = pickle.load(open(sys.argv[1], 'rb'))
S, C = R['structs'], R['classes']
U64 = lambda o: struct.unpack_from('<Q', d, o)[0]

def utf16_ident(va):
    o = p.off(va)
    if o is None: return None
    out = []
    for k in range(128):
        c = struct.unpack_from('<H', d, o + 2 * k)[0]
        if c == 0: break
        if c > 127: return None
        out.append(chr(c))
    s = ''.join(out)
    return s if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', s) else None

# --- function -> params
fn_cache = {}
def fn_target(f, kinds):
    """first lea rdx target among known params of given kinds"""
    key = (f, kinds)
    if key in fn_cache: return fn_cache[key]
    r = None
    leas, _ = xfunc.scan(p, f)
    for op, reg, t in leas:
        if op == 0x8D and reg == 2:
            if 's' in kinds and t in S: r = ('s', t); break
            if 'c' in kinds and t in C: r = ('c', t); break
            if 'e' in kinds: r = ('e', t); break
    fn_cache[key] = r; return r

# --- enums
enums = {}
def enum_from_fn(f):
    r = fn_target(f, 'e')
    if not r: return None
    o = p.off(r[1])
    if o is None: return None
    name = p.cstr(U64(o + 16))
    if not name or name in enums: return name
    ep, n = U64(o + 32), struct.unpack_from('<H', d, o + 44)[0]
    eo = p.off(ep)
    if eo is None or n > 4000: return None
    vals = []
    for k in range(n):
        nm, val = struct.unpack_from('<Qq', d, eo + 16 * k)
        vals.append((val, p.cstr(nm)))
    enums[name] = vals
    return name

# --- class names
def class_name(cv):
    c = C[cv]
    if 'name' in c: return c['name']
    name = None; ndepth = 9
    seen = set(); todo = [(c['noreg'], 0)]
    while todo and not name:
        f, depth = todo.pop(0)
        if f in seen: continue
        seen.add(f)
        leas, calls = xfunc.scan(p, f, 200)
        for op, reg, t in leas:
            if op == 0x8D and reg == 2:
                s = utf16_ident(t)
                if s: name = s; ndepth = depth; break
        if depth < 2: todo += [(t, depth + 1) for _, t in calls]
    c['name'] = name; c['ndepth'] = ndepth
    return name

def struct_name_fn(f):
    r = fn_target(f, 's')
    return S[r[1]]['name'] if r else None

# --- property types
def ptype(props, i):
    """parse property at index i (walking backward consumption); return (typeobj, next_i)"""
    pr = props[i]; g = pr['gen'] & 0x3f
    simple = {0x01: 23, 0x02: 22, 0x03: 2, 0x04: 21, 0x05: 20, 0x06: 19, 0x07: 18, 0x0a: 3, 0x0b: 7, 0x0c: 1,
              0x0d: 33, 0x0e: 14, 0x0f: 15, 0x10: 17, 0x11: 31, 0x12: 4, 0x13: 12, 0x14: 5, 0x15: 10,
              0x1a: 6, 0x1b: 32, 0x1c: 13, 0x1d: 11, 0x1f: 27, 0x20: 7, 0x23: 29, 0x24: 30}
    if g == 0x00:
        en = enum_from_fn(pr['extra']) if pr['extra'] else None
        return ((26, (0,), en) if en else (0,)), i - 1
    if g in simple: return (simple[g],), i - 1
    if g == 0x19: return (9, struct_name_fn(pr['extra']) or 'Unknown'), i - 1
    if g == 0x1e:
        en = enum_from_fn(pr['extra'])
        inner, j = ptype(props, i - 1)
        return (26, inner, en), j
    if g in (0x16, 0x18, 0x21):
        inner, j = ptype(props, i - 1)
        return ({0x16: 8, 0x18: 25, 0x21: 28}[g], inner), j
    if g == 0x17:
        key, j = ptype(props, i - 1)
        val, j = ptype(props, j)
        return (24, key, val), j
    return (0xFF,), i - 1

def top_props(props):
    out = []; i = len(props) - 1
    while i >= 0:
        t, j = ptype(props, i)
        out.append((props[i]['name'], props[i]['dim'], t)); i = j
    out.reverse()
    return out

types = []  # (name, super, props)
for v, s in S.items():
    sup = struct_name_fn(s['super']) if s['super'] else None
    types.append((s['name'], sup, top_props(s['props']), -1))
nameless = 0
for v, c in C.items():
    n = class_name(v)
    if not n: nameless += 1; continue
    sup = None
    if c['deps']:
        r = fn_target(c['deps'][0], 'c')
        if r: sup = class_name(r[1])
    types.append((n, sup, top_props(c['props']), c['ndepth']))
print('types', len(types), 'nameless classes', nameless, 'enums', len(enums))

# --- write usmap (version ExplicitEnumValues, uncompressed)
names = {}; nl = []
def ni(s):
    if s is None: return 0xFFFFFFFF
    if s not in names: names[s] = len(nl); nl.append(s)
    return names[s]
body = bytearray()
def wtype(t):
    body.append(t[0])
    if t[0] == 26: wtype(t[1]); body.extend(struct.pack('<I', ni(t[2])))
    elif t[0] == 9: body.extend(struct.pack('<I', ni(t[1])))
    elif t[0] in (8, 25, 28): wtype(t[1])
    elif t[0] == 24: wtype(t[1]); wtype(t[2])
eb = bytearray(struct.pack('<I', len(enums)))
for en, vals in enums.items():
    eb += struct.pack('<IH', ni(en), len(vals))
    for val, nm in vals: eb += struct.pack('<QI', val & 0xFFFFFFFFFFFFFFFF, ni(nm or '?'))
best = {}
for t in types:
    k = t[0]
    if k not in best or (t[3], -len(t[2])) < (best[k][3], -len(best[k][2])): best[k] = t
tb = bytearray(); cnt = 0
for n, sup, props, _ in best.values():
    cnt += 1
    body.clear()
    idx = 0
    for pn, dim, t in props:
        body.extend(struct.pack('<HBI', idx, min(dim, 255), ni(pn))); wtype(t); idx += dim
    tb += struct.pack('<IIHH', ni(n), ni(sup), idx, len(props)) + body
tb = struct.pack('<I', cnt) + tb
nb = bytearray(struct.pack('<I', len(nl)))
for s in nl:
    e = s.encode(); nb += struct.pack('<H', len(e)) + e
data = bytes(nb + eb + tb)
with open(sys.argv[2], 'wb') as f:
    f.write(struct.pack('<HB', 0x30C4, 4))  # version 4 = ExplicitEnumValues
    f.write(struct.pack('<I', 0))  # no package versioning (UE bool = 4 bytes)
    f.write(b'\0' + struct.pack('<II', len(data), len(data)) + data)
print('wrote', sys.argv[2], len(data), 'bytes;', cnt, 'types')
for n, sup, props, _ in types:
    if n in ('TankDataTableStruct',): print(n, sup, props[:8])
