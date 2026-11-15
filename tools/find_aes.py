"""Decode imm stores ([REX] C7/C6 modrm [sib] [disp] imm) incl. rsp/rbp/r8+ bases, group nearby, test 32-byte keys."""
import struct, sys, re
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
exe, pak = sys.argv[1], sys.argv[2]
with open(pak, 'rb') as f:
    f.seek(0, 2); size = f.tell(); f.seek(size - 221); foot = f.read(221)
idx_off = struct.unpack_from('<q', foot, 25)[0]
with open(pak, 'rb') as f:
    f.seek(idx_off); block = f.read(16)
def test(key):
    d = Cipher(algorithms.AES(key), modes.ECB()).decryptor().update(block)
    n = struct.unpack_from('<i', d)[0]
    return 0 < n < 256 and d[4:7] == b'../'
data = open(exe, 'rb').read()
text_end = 0x400 + 151044096  # raw .text approx
def decode(p):
    """return (length, base_reg, disp, width, imm) or None"""
    q = p; rexb = 0
    if 0x40 <= data[q] <= 0x4F:
        if data[q] & 0x08: return None  # REX.W -> qword store, imm32 sign-extended; skip
        rexb = data[q] & 1; q += 1
    op = data[q]
    if op not in (0xC6, 0xC7): return None
    w = 1 if op == 0xC6 else 4
    modrm = data[q+1]; mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    if reg != 0 or mod == 3: return None
    q += 2; base = rm | (rexb << 3)
    if rm == 4:
        sib = data[q]; q += 1
        if (sib >> 3) & 7 != 4: return None
        base = (sib & 7) | (rexb << 3)
    if mod == 0:
        if rm == 5: return None
        disp = 0
    elif mod == 1: disp = struct.unpack_from('<b', data, q)[0]; q += 1
    else: disp = struct.unpack_from('<i', data, q)[0]; q += 4
    imm = data[q:q+w]; q += w
    return (q - p, base, disp, w, imm)
stores = []
for m in re.finditer(rb'[\xC6\xC7]', data[:text_end]):
    p = m.start()
    for start in (p - 1, p):
        r = decode(start) if start >= 0 else None
        if r: stores.append((start,) + r); break
print('stores', len(stores))
tested = 0
# group by proximity
groups = []; cur = []
for s in stores:
    if cur and s[0] - cur[-1][0] > 64:
        if len(cur) >= 8: groups.append(cur)
        cur = []
    cur.append(s)
print('groups', len(groups))
for g in groups:
    by = {}
    for (_, _, base, disp, w, imm) in g:
        for i, b in enumerate(imm): by[(base, disp + i)] = b
    keys = {k[0] for k in by}
    for base in keys:
        offs = sorted(o for (bb, o) in by if bb == base)
        for o in offs:
            if all((base, o + j) in by for j in range(32)):
                k = bytes(by[(base, o + j)] for j in range(32)); tested += 1
                if test(k): print('KEY 0x' + k.hex().upper(), 'near', hex(g[0][0])); sys.exit(0)
print('tested', tested, 'none')
