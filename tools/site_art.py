"""Tank renders (extract/renders/<id>_<angle>.png, transparent) -> site/art/<id>_<angle>.webp, trimmed and sized for the web.

Trims to the alpha bounding box plus a small margin, caps the width, writes WebP with alpha, and a small thumbnail
(<id>_<angle>_s.webp) for pickers and cards. Ids are the site tank ids (they match the vehicle folder names).
"""
import glob, json, os
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
SRC, OUT = os.path.join(ROOT, 'extract/renders'), os.path.join(ROOT, 'site/art')

def main():
    os.makedirs(OUT, exist_ok=True)
    index = {}
    for f in sorted(glob.glob(os.path.join(SRC, '*_*.png'))):
        stem = os.path.basename(f)[:-4]
        tid, ang = stem.rsplit('_', 1)
        if not ang.isdigit(): continue
        im = Image.open(f).convert('RGBA')
        box = im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()
        if not box: continue
        pad = int(0.03 * max(box[2] - box[0], box[3] - box[1]))
        im = im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))
        for suffix, w, q in (('', 1100, 84), ('_s', 280, 80)):
            k = im.copy()
            if k.width > w: k = k.resize((w, round(k.height * w / k.width)), Image.LANCZOS)
            k.save(os.path.join(OUT, f'{stem}{suffix}.webp'), 'WEBP', quality=q, method=6)
        index.setdefault(tid, {})[ang] = [im.width, im.height]
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w'), indent=1)
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, '*.webp')))
    print(f'{len(index)} tanks, {total / 1e6:.1f} MB of webp in site/art')

if __name__ == '__main__':
    main()
