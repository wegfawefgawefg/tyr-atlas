"""Toilet-flush ending: swirl the frames into a drain vortex and shrink them into the plughole.

python3 tools/memes/flush.py <frame dir> <out dir> <fps> <flush start s> [flush length s]
Frames before the flush are copied unchanged; the vortex spins faster near the middle, like water going down.
"""
import sys, os, glob, shutil, math
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

src, dst, fps, t0 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
length = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
os.makedirs(dst, exist_ok=True)
files = sorted(glob.glob(os.path.join(src, 'f_*.png')))
grid = None
for k, f in enumerate(files):
    t = k / fps; out = os.path.join(dst, os.path.basename(f))
    u = (t - t0) / length
    if u <= 0: shutil.copyfile(f, out); continue
    im = np.asarray(Image.open(f).convert('RGB')).astype(np.float32)
    h, w = im.shape[:2]
    if grid is None:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); cy, cx = h / 2, w / 2
        dx, dy = xx - cx, yy - cy; r = np.hypot(dx, dy); th = np.arctan2(dy, dx); R = math.hypot(cx, cy)
        grid = True
    u = min(u, 1.0); e = u * u * (3 - 2 * u)
    twist = 14.0 * e ** 1.3 / (r / R + 0.18)                     # spins harder near the drain
    shrink = max(1e-3, 1 - e ** 1.6)                              # picture sucked into the hole
    rs = r / shrink; ts = th + twist
    sx = cx + rs * np.cos(ts); sy = cy + rs * np.sin(ts)
    inside = (sx >= 0) & (sx <= w - 1) & (sy >= 0) & (sy <= h - 1)
    o = np.stack([map_coordinates(im[..., c], [sy, sx], order=1, mode='nearest') for c in range(3)], -1)
    water = np.array([18, 40, 70], np.float32)                    # dark toilet-water blue around it
    o[~inside] = water
    o = o * (1 - 0.6 * e) + water * 0.6 * e * (r / R)[..., None]
    if u >= 1.0: o[:] = 0
    Image.fromarray(np.clip(o, 0, 255).astype(np.uint8)).save(out)
print('flushed', len(files), 'frames from', t0, 's')
