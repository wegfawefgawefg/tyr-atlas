"""Tiny PE helper: file offset <-> VA, read pointers/strings."""
import struct
class PE:
    def __init__(self, path):
        self.d = d = open(path, 'rb').read()
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        n = struct.unpack_from('<H', d, pe+6)[0]; opt = struct.unpack_from('<H', d, pe+20)[0]
        self.base = struct.unpack_from('<Q', d, pe+24+24)[0]
        s = pe + 24 + opt; self.secs = []
        for i in range(n):
            name, vsz, va, rsz, rptr = struct.unpack_from('<8sIIII', d, s + 40*i)
            self.secs.append((name.rstrip(b'\0').decode(), va, vsz, rptr, rsz))
    def off(self, va):
        rva = va - self.base
        for _, sva, vsz, rptr, rsz in self.secs:
            if sva <= rva < sva + max(vsz, rsz):
                o = rva - sva
                return rptr + o if o < rsz else None
        return None
    def va(self, off):
        for _, sva, vsz, rptr, rsz in self.secs:
            if rptr <= off < rptr + rsz: return self.base + sva + off - rptr
    def sec(self, name):
        for s in self.secs:
            if s[0] == name: return s
    def q(self, va): o = self.off(va); return struct.unpack_from('<Q', self.d, o)[0] if o is not None else None
    def cstr(self, va, n=256):
        o = self.off(va)
        if o is None: return None
        e = self.d.find(b'\0', o, o+n)
        if e < 0: return None
        try: return self.d[o:e].decode('utf-8')
        except UnicodeDecodeError: return None
