"""Benny Hill chase on the Fields minimap: a conga of toy-scale tanks laps the middle road clockwise, screeches to a stop,
everyone spins round, and they chase the other way. The toilet-flush swirl is added afterwards (tools/memes/flush.py).

blender -b -t 16 -P tools/memes/chase_fields.py -- <out dir> [preview|final] ["a,b,c"]
Needs extract/tex/.../T_Minimap_Fields.png (extract.dll tex extract/tex 'Textures/Minimap/T_Minimap_').
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meme_lib import *

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else os.path.join(REPO, 'extract/memes/chase_fields')
PREVIEW = len(argv) > 1 and argv[1] == 'preview'
FPS = 24; DUR = 15.0; F = int(DUR * FPS)
sc = reset(FPS, F, 640, 360, samples=8 if PREVIEW else 32, scale=50 if PREVIEW else int(os.environ.get('MEME_SCALE', 200)))
sc.render.use_motion_blur = not PREVIEW
D = math.radians

# ---------- the map: 1024 px minimap on a 1024 m plane, 1 px = 1 m, image north = +Y ----------
MINIMAP = os.path.join(REPO, 'extract/tex/Tyr/Content/UI/_Shared/Textures/Minimap/T_Minimap_Fields.png')
bpy.ops.mesh.primitive_plane_add(size=1024, location=(0, 0, 0)); ground = bpy.context.active_object
m = bpy.data.materials.new('minimap'); m.use_nodes = True; N = m.node_tree.nodes; b = N['Principled BSDF']
tx = N.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(MINIMAP); tx.interpolation = 'Cubic'
m.node_tree.links.new(tx.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.85
m.node_tree.links.new(tx.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 0.35
ground.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(size=8000, location=(0, 0, -0.5)); bpy.context.active_object.data.materials.append(material('beyond', (0.035, 0.03, 0.04), rough=0.9))
def px(u, v): return Vector((u - 512, 512 - v, 0))

sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = D(3); sun.rotation_euler = (D(40), D(-25), D(30))
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.55, 0.7, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6

# ---------- the lap: Catmull-Rom through road points (minimap pixels), arc-length parametrised ----------
CTRL = [(450, 95), (600, 115), (700, 200), (720, 320), (650, 450), (600, 560), (640, 680), (560, 800), (430, 880),
        (330, 800), (340, 650), (360, 540), (300, 400), (320, 230), (370, 140)]
def _cr(P, n=60):
    out = []
    for i in range(len(P)):
        p0, p1, p2, p3 = (Vector(P[(i + k) % len(P)]) for k in (-1, 0, 1, 2))
        for j in range(n):
            t = j / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return out
PATH = [px(p.x, p.y) for p in _cr(CTRL)]
SEG = [(PATH[(i + 1) % len(PATH)] - PATH[i]).length for i in range(len(PATH))]
CUM = [0.0]
for s_ in SEG: CUM.append(CUM[-1] + s_)
LAP = CUM[-1]
def along(s):
    """Position and unit tangent (clockwise direction) at arc length s (wraps)."""
    s %= LAP; lo, hi = 0, len(PATH) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if CUM[mid] <= s: lo = mid
        else: hi = mid - 1
    i = lo; u = (s - CUM[i]) / SEG[i]; a, b_ = PATH[i], PATH[(i + 1) % len(PATH)]
    return a.lerp(b_, u), (b_ - a).normalized()

# ---------- cast: toy scale ----------
K = 9.0
CAST = [('Blink', 'Alecto', 7.4), ('Sonar', 'Atlas', 12.6), ('Ram', 'Maul', 8.2)] + [('Healer', f'Valor{i}', 7.4) for i in range(5)]
tanks = []
off = 0.0
for i, (veh, label, length) in enumerate(CAST):
    T = Tank(veh, label); T.arm.scale = (K, K, K)
    if i: off += (CAST[i - 1][2] + length) / 2 * K + 14
    tanks.append((T, off, i))

# ---------- motion: one shared distance D(t) along the lap; forward clockwise, then a stop, a spin, and back ----------
T_GO, T_STOP, T_SPIN0, T_SPIN1, T_BACK, T_END = 0.3, 6.6, 7.0, 7.9, 8.4, DUR
V1 = LAP / 5.6; V2 = LAP / 4.6
def dist(t):
    if t < T_GO: return 0.0
    if t < T_GO + 0.5: u = t - T_GO; return V1 * u * u / 1.0                      # floor it
    if t < T_STOP: return V1 * 0.25 + V1 * (t - T_GO - 0.5)
    d_stop = V1 * 0.25 + V1 * (T_STOP - T_GO - 0.5)
    if t < T_STOP + 0.35: u = t - T_STOP; return d_stop + V1 * (u - u * u / 0.7)  # screech: 0.35 s to zero
    d_halt = d_stop + V1 * 0.175
    if t < T_BACK: return d_halt
    if t < T_BACK + 0.4: u = t - T_BACK; return d_halt - V2 * u * u / 0.8
    return d_halt - V2 * 0.2 - V2 * (t - T_BACK - 0.4)
S0 = LAP * 0.62          # leader starts on the west road, heading north over the bridge

def tank_mat(T, off, i, t):
    pos, tan = along(S0 + dist(t) - off)
    yaw = math.atan2(tan.y, tan.x)
    spin = ease_out_back((t - (T_SPIN0 + 0.06 * i)) / 0.45, 1.4) if t > T_SPIN0 + 0.06 * i else 0.0
    yaw += math.pi * spin * (1 if i % 2 else -1)
    running = (T_GO < t < T_STOP + 0.2) or t > T_BACK
    hop = abs(math.sin(2 * math.pi * 3.2 * t + i * 1.3)) * 2.2 * K * 0.25 if running else 0.0
    wob = D(6) * math.sin(2 * math.pi * 3.2 * t + i * 1.3) if running else 0.0
    skid = D(10) * math.sin(math.pi * clamp((t - T_STOP) / 0.45)) if T_STOP < t < T_STOP + 0.45 else 0.0
    slide = D(25) * math.sin(math.pi * clamp((t - T_STOP) / 0.6)) * (1 if i % 2 else -1) if T_STOP < t < T_STOP + 0.6 else 0.0
    look = 0.0
    if T_SPIN1 < t < T_BACK: look = D(25) * math.sin((t - T_SPIN1) * 18 + i)                # "uh oh" look around
    return mat_from(pos + Vector((0, 0, hop)), yaw + slide, -skid, wob), look

cam = camera(30); cam.data.clip_end = 20000; cam.data.clip_start = 1.0
LOOP_CTR = px(510, 490)
def cam_at(t):
    # wide 3/4 view from the west (map north points right), slow push-in on the stop
    push = ramp(t, T_STOP - 0.2, T_SPIN1) - ramp(t, T_BACK, T_BACK + 1.2)
    target = LOOP_CTR.lerp(along(S0 + dist(t) - 150)[0], 0.55 * push) + Vector((0, 0, 0))
    d = lerp(1050, 650, push)
    return target, d
for f in range(F):
    t = f / FPS; sc.frame_set(f)
    for T, off, i in tanks:
        M, look = tank_mat(T, off, i, t); put(T.arm, M)
        T.pose('jnt_turret', rot=T.rot('jnt_turret', yaw=look + D(12) * math.sin(t * 7 + i)))
        T.key(f)
    c, d = cam_at(t); aim(cam, c, (-1.0, 0.0, 1.25), d)
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)

os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
if len(argv) > 2:
    for f in map(int, argv[2].split(',')):
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f'f_{f:04d}'); bpy.ops.render.render(write_still=True)
else:
    sc.render.filepath = os.path.join(OUT, 'f_'); bpy.ops.render.render(animation=True)
print('DONE', OUT, 'lap m', round(LAP))
