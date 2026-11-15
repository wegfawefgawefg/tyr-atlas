"""One Maul sitting on a big white couch, five Valors standing up behind it, guns tilted down at it.

blender -b -t 16 -P tools/memes/maul_valors.py -- <out dir> [preview|final] [frames "a,b,c" | still]
The last frame is the meme still. Frames go to <out dir>/f_0000.png ...
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meme_lib import *

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else os.path.join(REPO, 'extract/memes/maul_valors')
PREVIEW = len(argv) > 1 and argv[1] == 'preview'
FPS = 24; DUR = 6.0; F = int(DUR * FPS)
sc = reset(FPS, F, 960, 640, samples=8 if PREVIEW else 48, scale=50 if PREVIEW else int(os.environ.get('MEME_SCALE', 200)))
sc.render.use_motion_blur = not PREVIEW
D = math.radians

# ---------- the room ----------
def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=bm.verts, vec=(x1 - x0, y1 - y0, z1 - z0))
    bmesh.ops.translate(bm, verts=bm.verts, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    o = obj_from_bm(name, bm, mat)
    for p in o.data.polygons: p.use_smooth = False
    if bevel:
        m = o.modifiers.new('bevel', 'BEVEL'); m.width = bevel; m.segments = 6; m.limit_method = 'NONE'
        o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
    return o

m_wall = material('wall', (0.86, 0.86, 0.84), rough=0.9)
m_floor = material('floor_room', (0.62, 0.6, 0.58), rough=0.5)
m_couch = material('couch', (0.88, 0.87, 0.85), rough=0.95)
m_pillow = material('pillow', (0.0, 0.55, 0.62), rough=0.9)
m_window = material('window', (1, 1, 1), rough=1.0, emit=2.5, emit_col=(0.97, 0.98, 1.0))
m_frame = material('frame', (0.92, 0.92, 0.9), rough=0.6)

box('floor', -80, 80, -80, 30, -0.2, 0, m_floor)
box('wall', -80, 80, 22, 23, 0, 40, m_wall)
box('window', -11, 11, 21.9, 22.0, 6.5, 19, m_window)
for x in (-11.3, -3.7, 3.7, 11.0):                                   # mullions + frame
    box(f'mull{x}', x, x + 0.6, 21.6, 21.95, 6.2, 19.3, m_frame)
box('sill', -12, 12, 21.0, 22.0, 5.8, 6.5, m_frame); box('head', -12, 12, 21.3, 22.0, 19.0, 19.8, m_frame)
box('mid', -11, 11, 21.6, 21.95, 12.3, 12.7, m_frame)
# couch: base, three seat cushions, back, arms (sized for tanks)
box('couch_base', -16, 16, -3.0, 8.6, 0, 0.8, m_couch, 0.3)
for i, (x0, x1) in enumerate(((-16, -5.4), (-5.3, 5.3), (5.4, 16))):
    box(f'seat{i}', x0, x1, -3.2, 6.4, 0.8, 1.9, m_couch, 0.5)
    box(f'back{i}', x0, x1, 6.3, 8.6, 1.9, 4.1, m_couch, 0.7)
box('arm_l', -18.2, -15.9, -3.2, 8.6, 0, 3.0, m_couch, 0.6); box('arm_r', 15.9, 18.2, -3.2, 8.6, 0, 3.0, m_couch, 0.6)
for sx in (-1, 1):
    p = box(f'pillow{sx}', -2.2, 2.2, -0.7, 0.7, -2.2, 2.2, m_pillow, 0.9); p.location = (sx * 12.6, 5.4, 3.6)
    p.rotation_euler = (D(-14), D(sx * 8), D(sx * 10))
    sd = p.modifiers.new('sub', 'SUBSURF'); sd.levels = 2; sd.render_levels = 2

# light: soft and bright like the photo
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.95, 0.96, 1.0, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.35
def area(name, loc, energy, size, target=(0, 4, 4), colour=(1, 0.98, 0.95)):
    L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.size = size; L.color = colour
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
area('front', (6, -40, 22), 45000, 30)
area('fill', (-30, -20, 12), 9000, 20)
area('window_spill', (0, 20, 14), 9000, 22, target=(0, 0, 3), colour=(0.95, 0.97, 1.0))
vt = [v.identifier for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
sc.view_settings.view_transform = 'AgX' if 'AgX' in vt else 'Filmic'
try: sc.view_settings.look = 'AgX - Punchy'
except Exception: pass

cam = camera(34)
cam.location = (0, -36, 4.8); cam.rotation_euler = (Vector((0, 5, 7.4)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

# ---------- tanks ----------
maul = Tank('Ram', 'Maul')
MAUL_M = mat_from((0, 1.85, 1.96), -math.pi / 2, D(-6), 0)          # on the middle cushion, facing the camera, leaning back a bit
valors = [Tank('Healer', f'Valor{i}') for i in range(5)]
VX = [-17.0, -8.5, 0.0, 8.5, 17.0]
LEAN = [D(101), D(97), D(103), D(98), D(100)]
YAW_JIT = [D(4), D(-3), D(0), D(3), D(-5)]
RISE = [0.7, 1.15, 1.6, 2.05, 2.5]                                   # each Valor stands up from lying flat behind the couch
NOSE_LOCAL = Vector((4.37, 0, 0.09)); VS = 1.55
for v in valors: v.arm.scale = (VS, VS, VS)
SUB = [v for v in valors[0].verts[::25]]

def on_floor(M):
    zmin = min((M @ v).z for v in SUB); return Matrix.Translation((0, 0, -zmin)) @ M

def valor_mat(i, t):
    s = ease_out_back((t - RISE[i]) / 0.45, 2.2) if t > RISE[i] else 0.0
    pitch = lerp(D(2), -LEAN[i], s)                                      # nose down, butt up: turret ends up on top like a head
    r = mat_from((0, 0, 0), -math.pi / 2 + YAW_JIT[i], pitch, 0) @ Matrix.Diagonal((VS, VS, VS, 1))
    M = Matrix.Translation(Vector((VX[i], 10.6, 0)) - (r @ NOSE_LOCAL)) @ r
    return on_floor(M)

def aim(T, M, target):
    """Turret yaw + gun pitch (bone eulers) that point T's gun at `target` (world), tank at world matrix M."""
    g = M @ T.rest_bone('jnt_turret').translation; d = (target - g).normalized()      # from the turret pivot: the gun swings with it
    dl = (M.to_3x3().inverted() @ d).normalized()
    return math.atan2(dl.y, dl.x), math.asin(max(-1, min(1, dl.z)))

def maul_turret(t):
    # deadpan at the camera, nervous glances up left and right, back to the camera
    look = 0.0; up = D(4)
    look += D(28) * (ramp(t, 3.3, 3.55) - ramp(t, 3.75, 4.0)) - D(28) * (ramp(t, 4.0, 4.25) - ramp(t, 4.45, 4.7))
    up += D(14) * (ramp(t, 3.3, 3.55) - ramp(t, 4.45, 4.7))
    return look, up

def scene_at(f):
    t = f / FPS; sc.frame_set(f)
    put(maul.arm, MAUL_M)
    ly, gp = maul_turret(t); maul.pose('jnt_turret', rot=maul.rot('jnt_turret', yaw=ly)); maul.pose('jnt_gun', rot=maul.rot('jnt_gun', pitch=gp))
    maul.key(f)
    target = MAUL_M @ Vector((-0.5, 0, 2.6))
    for i, v in enumerate(valors):
        M = valor_mat(i, t); put(v.arm, M)
        yaw_a, pit_a = aim(v, M, target)
        yaw_a = (yaw_a + math.pi) % (2 * math.pi) - math.pi
        if i == 2: yaw_a, pit_a = math.pi, D(-128)                     # straight behind Maul: gun up over its head, curling down at it
        s = ramp(t, 2.75 + 0.08 * i, 3.25 + 0.08 * i)
        v.pose('jnt_turret', rot=v.rot('jnt_turret', yaw=s * yaw_a)); v.pose('jnt_gun', rot=v.rot('jnt_gun', pitch=s * pit_a))
        v.key(f)

for f in range(F): scene_at(f)

os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
sel = argv[2] if len(argv) > 2 else None
if sel:
    frames = [F - 1] if sel == 'still' else list(map(int, sel.split(',')))
    for f in frames:
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f'f_{f:04d}'); bpy.ops.render.render(write_still=True)
else:
    sc.render.filepath = os.path.join(OUT, 'f_'); bpy.ops.render.render(animation=True)
print('DONE', OUT)
