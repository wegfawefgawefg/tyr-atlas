"""Follow a function's code (byte-wise, approximate): rip-relative lea/mov targets and call/jmp targets.
Stops at 'ret; int3' padding. Call detection never skips bytes, so it can't swallow a real lea."""
import struct
def scan(p, va, n=200):
    o = p.off(va); d = p.d; leas = []; calls = []
    if o is None: return leas, calls
    if d[o] == 0xE9:
        return scan(p, p.va(o) + 5 + struct.unpack_from('<i', d, o+1)[0], n)
    i = o; end = o + n
    while i < end:
        b = d[i]
        if b in (0x48, 0x4C) and d[i+1] in (0x8D, 0x8B) and (d[i+2] & 0xC7) == 0x05:
            t = p.va(i) + 7 + struct.unpack_from('<i', d, i+3)[0]
            leas.append((d[i+1], ((d[i+2] >> 3) & 7) | (8 if b == 0x4C else 0), t)); i += 7; continue
        if b in (0xE8, 0xE9):
            calls.append((b, p.va(i) + 5 + struct.unpack_from('<i', d, i+1)[0]))
        if b == 0xC3 and d[i+1] == 0xCC: break
        i += 1
    return leas, calls
