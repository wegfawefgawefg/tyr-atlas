import struct, sys, math, collections
d = open(sys.argv[1], 'rb').read()
pe = struct.unpack_from('<I', d, 0x3c)[0]
n = struct.unpack_from('<H', d, pe+6)[0]; opt = struct.unpack_from('<H', d, pe+20)[0]
s = pe + 24 + opt
for i in range(n):
    name, vsz, va, rsz, rptr = struct.unpack_from('<8sIIII', d, s + 40*i)
    chunk = d[rptr:rptr+min(rsz, 4_000_000)]
    c = collections.Counter(chunk); t = len(chunk) or 1
    ent = -sum(v/t*math.log2(v/t) for v in c.values())
    print(name.rstrip(b'\0'), hex(va), 'vsz', vsz, 'raw', rsz, f'entropy {ent:.2f}')
