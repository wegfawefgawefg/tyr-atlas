"""Static UE5 reflection scan of the shipping exe: find UHT-generated struct/class/enum params.
Stage 1: locate StructParams and print property type histogram so the gen-flag mapping can be checked."""
import sys, struct, re, collections, pickle
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from pe import PE

EXE = '/path/to/SteamLibrary/steamapps/common/Tyr/Tyr/Binaries/Win64/TyrClient-Win64-Shipping.exe'
p = PE(EXE)
d = p.d
_, tva, tvs, _, _ = p.sec('.text')
TEXT = (p.base + tva, p.base + tva + tvs)
DATA = []
for n in ('.rdata', '.data'):
    _, va, vs, _, _ = p.sec(n); DATA.append((p.base + va, p.base + va + vs))
def in_text(v): return TEXT[0] <= v < TEXT[1]
def in_data(v): return any(a <= v < b for a, b in DATA)
IDENT = re.compile(rb'[A-Za-z_][A-Za-z0-9_]*\Z')
_sc = {}
def ident(v):
    if v in _sc: return _sc[v]
    r = None
    if in_data(v):
        o = p.off(v)
        if o is not None:
            e = d.find(b'\0', o, o + 200)
            if e > o and IDENT.match(d[o:e]): r = d[o:e].decode()
    _sc[v] = r; return r
U64 = lambda o: struct.unpack_from('<Q', d, o)[0]

def prop_at(v):
    """parse FPropertyParams at VA v; None if implausible"""
    o = p.off(v)
    if o is None: return None
    name = ident(U64(o))
    if not name: return None
    rep = U64(o + 8)
    if rep and not ident(rep): return None
    gen = d[o + 24]
    if (gen & 0x3f) > 0x26: return None
    objf = struct.unpack_from('<I', d, o + 28)[0]
    if objf & ~0xFFFF: return None
    dim = struct.unpack_from('<H', d, o + 48)[0]
    if not 1 <= dim <= 4096: return None
    extra = U64(o + 56)
    return dict(name=name, gen=gen, dim=dim, extra=extra, pflags=U64(o + 16))

def prop_array(v, n):
    if n == 0: return []
    o = p.off(v)
    if o is None: return None
    out = []
    for i in range(n):
        pv = U64(o + 8 * i)
        pr = prop_at(pv)
        if not pr: return None
        pr['va'] = pv; out.append(pr)
    return out

rd_name, rva, rvs, rptr, rsz = p.sec('.rdata')
dd_name, dva, dvs, dptr, dsz = p.sec('.data')
structs, classes, enums = {}, {}, {}
for sptr, ssz in ((rptr, rsz), (dptr, dsz)):
    for o in range(sptr, sptr + ssz - 64, 8):
        a = U64(o)
        if not in_text(a): continue
        v = p.va(o)
        # StructParams: Outer, Super, StructOps, Name, PropArray, u16 N, u16 SizeOf, u8 Align, ObjF@48, StructFlags@52
        sup, ops, nm, pa = U64(o + 8), U64(o + 16), U64(o + 24), U64(o + 32)
        if (sup == 0 or in_text(sup)) and (ops == 0 or in_text(ops)):
            name = ident(nm)
            if name:
                n, size, align = struct.unpack_from('<HHB', d, o + 40)
                objf = struct.unpack_from('<I', d, o + 48)[0]
                if (n == 0 or in_data(pa)) and 1 <= align <= 64 and objf < 0x10000:
                    props = prop_array(pa, n)
                    if props is not None:
                        structs[v] = dict(name=name, super=sup, outer=a, props=props, size=size)
                        continue
        # ClassParams: NoReg, ConfigName, CppInfo, DepArray, FuncLinks, PropArray, Ifaces, packed u32 @56, ClassFlags @60
        cfg, cpp, dep, fl, pa, ifc = (U64(o + 8 * k) for k in range(1, 7))
        if (cfg == 0 or ident(cfg)) and in_data(cpp) and (dep == 0 or in_data(dep)):
            bits = struct.unpack_from('<I', d, o + 56)[0]
            ndep, nfun, nprop, nifc = bits & 15, (bits >> 4) & 0x7ff, (bits >> 15) & 0x7ff, (bits >> 26) & 63
            if (nprop == 0 or in_data(pa)) and (nfun == 0 or in_data(fl)) and (nifc == 0 or in_data(ifc)) and (ndep == 0) == (dep == 0):
                props = prop_array(pa, nprop)
                if props is not None:
                    deps = [U64(p.off(dep) + 8 * k) for k in range(ndep)] if ndep else []
                    if all(in_text(x) for x in deps):
                        classes[v] = dict(noreg=a, deps=deps, props=props)
                        continue
        # EnumParams: Outer, DisplayNameFunc, Name, CppType, Enumerators, ...
        dn, nm, cppt, en = U64(o + 8), U64(o + 16), U64(o + 24), U64(o + 32)
        if (dn == 0 or in_text(dn)) and ident(nm) and ident(cppt) and in_data(en):
            enums[v] = dict(name=ident(nm), cpp=ident(cppt), raw=d[o + 40:o + 56])
print('structs', len(structs), 'classes', len(classes), 'enum-cands', len(enums))
hist = collections.Counter(); ex = collections.defaultdict(list)
for coll in (structs, classes):
    for s in coll.values():
        for pr in s['props']:
            g = pr['gen'] & 0x3f; hist[g] += 1
            if len(ex[g]) < 6: ex[g].append(pr['name'])
for g in sorted(hist): print(f'{g:#04x} {hist[g]:6d}', ex[g])
for v, e in list(enums.items())[:5]: print(hex(v), e['name'], e['cpp'], e['raw'].hex())
pickle.dump(dict(structs=structs, classes=classes, enums=enums), open(sys.argv[1], 'wb'))
