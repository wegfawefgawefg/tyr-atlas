"""Alecto spins around Atlas really fast, humps it, kisses it; Atlas's gun turns into a cigarette, it smokes and blushes.

blender -b -t 16 -P tools/memes/alecto_atlas.py -- <out dir> [preview]
Writes PNG frames <out dir>/f_0000.png ... ; tools/memes/encode.sh turns them into a GIF and an MP4.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from meme_lib import *

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else os.path.join(REPO, 'extract/memes/alecto_atlas')
PREVIEW = len(argv) > 1 and argv[1] == 'preview'
FPS = 24; DUR = 8.8; F = int(DUR * FPS)
sc = reset(FPS, F, 640, 360, samples=8 if PREVIEW else 40, scale=50 if PREVIEW else 200)
if PREVIEW: sc.render.use_motion_blur = False
stage((0, 0, 2), 8.0)
cam = camera(50)

A = Tank('Sonar', 'Atlas')      # Atlas: heavy, faces +X, at the origin
B = Tank('Blink', 'Alecto')     # Alecto: light hover tank
NOSE = B.tip(0, 1, 0.3)                       # Alecto's nose, its armature space
REAR = Vector((-5.12, 0, 1.3))                # Atlas rear plate (Atlas space)
CHIN = Vector((2.16, 0, 2.86))                # Atlas turret front under the gun
D = math.radians

# ---------- props ----------
m_puff = material('puff', (0.9, 0.88, 0.95), rough=1.0, emit=0.25, emit_col=(0.9, 0.85, 1.0), alpha_from_object=True)
m_heart = material('heart', (1.0, 0.1, 0.4), rough=0.3, emit=4.0, emit_col=(1.0, 0.15, 0.45), alpha_from_object=True)
m_blush = material('blush', (1.0, 0.3, 0.5), rough=0.6, emit=2.5, emit_col=(1.0, 0.25, 0.5), alpha_from_object=True)
m_blush_line = material('blush_line', (0.7, 0.05, 0.25), rough=0.6, emit=1.5, emit_col=(0.8, 0.05, 0.3), alpha_from_object=True)
m_filter = material('filter', (0.85, 0.45, 0.12), rough=0.7)
m_paper = material('paper', (0.95, 0.95, 0.93), rough=0.8)
m_ash = material('ash', (0.25, 0.25, 0.25), rough=1.0)
m_ember = material('ember', (1.0, 0.3, 0.05), rough=0.6, emit=6.0, emit_col=(1.0, 0.35, 0.05))
ember_strength = m_ember.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']

CIG_R, CIG0, CIG1 = 0.27, 0.55, 4.0           # along the gun bone's +X from the gun pivot
cig = [cylinder_x('cig_filter', CIG_R, CIG0, 1.45, m_filter), cylinder_x('cig_paper', CIG_R, 1.45, CIG1 - 0.12, m_paper),
       cylinder_x('cig_ember', CIG_R * 0.98, CIG1 - 0.12, CIG1 - 0.03, m_ember), cylinder_x('cig_ash', CIG_R * 0.85, CIG1 - 0.03, CIG1, m_ash)]
for o in cig: o.rotation_mode = 'QUATERNION'

def make_blush(side):
    d = sphere(f'blush{side}', 1.0, m_blush, 24); d.scale = (0.8, 0.45, 0.06); d.rotation_mode = 'QUATERNION'
    root = bpy.data.objects.new(f'blush_root{side}', None); sc.collection.objects.link(root); root.rotation_mode = 'QUATERNION'
    d.parent = root
    lines = []
    for i in range(3):
        l = cylinder_x(f'blush_line{side}{i}', 0.045, -0.22, 0.22, m_blush_line, 8); l.parent = root
        l.rotation_mode = 'XYZ'; l.location = (-0.35 + 0.35 * i, 0, 0.07); l.rotation_euler = (0, 0, D(65))
        lines.append(l)
    # cheek on the turret side: sloped panel, normal (0, -0.92, 0.39) on the -Y side
    n = Vector((0, side * 0.92, 0.39)).normalized(); p = Vector((0.75, side * 1.93, 2.86)) + n * 0.04
    z = n; x = Vector((1, 0, 0)); y = z.cross(x)
    W = Matrix((x, y, z)).transposed().to_4x4(); W.translation = p
    return root, [d] + lines, A.rest_bone('jnt_turret').inverted() @ W

blush = [make_blush(-1), make_blush(1)]
hearts = [heart(f'heart{i}', 1.0, 0.25, m_heart) for i in range(5)]
for h in hearts: h.rotation_mode = 'QUATERNION'
tip_smoke = Puffs('smoke', 26, m_puff); exhale = Puffs('exhale', 12, m_puff); poof = Puffs('poof', 12, m_puff)

# ---------- timeline (seconds) ----------
T_ORBIT, T_SETTLE, T_HUMP, T_FLIP, T_KISS, T_CIG = 0.45, 2.0, 2.6, 4.7, 5.3, 6.0
OMEGA = 2 * math.pi * 2.5 / (T_SETTLE - T_ORBIT)
C, RAD, HOVER = Vector((-1, 0, 0)), 11.0, 1.6
SETTLE_LEN = T_HUMP - T_SETTLE
PHI2 = math.pi - OMEGA * SETTLE_LEN / 2       # so the decelerating spin stops right behind Atlas

def phi(t):
    if t <= T_SETTLE: return PHI2 - OMEGA * (T_SETTLE - t)
    tau = min(t - T_SETTLE, SETTLE_LEN); return PHI2 + OMEGA * tau - OMEGA * tau * tau / (2 * SETTLE_LEN)

def orbit_mat(t):
    p = phi(t); pos = C + Vector((RAD * math.cos(p), RAD * math.sin(p), HOVER)); yaw = p + math.pi / 2
    if t < T_ORBIT:                                   # fly in along the tangent
        pos = C + Vector((RAD * math.cos(p), RAD * math.sin(p), HOVER)) - Vector((math.cos(yaw), math.sin(yaw), 0)) * OMEGA * RAD * (T_ORBIT - t)
    bank = -D(35) * (1 - ramp(t, T_SETTLE, T_HUMP))
    return mat_from(pos, yaw, D(-4), bank)

def by_nose(P, yaw, pitch=0.0, roll=0.0):
    r = mat_from((0, 0, 0), yaw, pitch, roll); return mat_from(P - (r @ NOSE), yaw, pitch, roll)

def hump_psi(t):
    u = max(0.0, t - T_HUMP); return 2 * math.pi * (2.4 * u + 0.65 * u * u)

def atlas_mat(t):
    jolt = 0.0
    if T_HUMP <= t < T_FLIP + 0.1: jolt = 0.16 * max(0.0, -math.cos(hump_psi(t))) ** 4 * ramp(t, T_HUMP, T_HUMP + 0.3)
    bump = 0.12 * math.sin(math.pi * clamp((t - 5.45) / 0.25)) if 5.45 < t < 5.7 else 0.0      # pushed back by the kiss
    wob = D(1.5) * math.sin(t * 9) * (1 - ramp(t, 1.8, 2.6)) * ramp(t, 0.5, 0.9)              # dizzy while being circled
    return mat_from((jolt - bump, 0, 0), 0, -jolt * 0.25 + bump * 0.1, wob)

def hump_mat(t, M_atlas, gap=None):
    psi = hump_psi(t)
    if gap is None: gap = -0.08 + 0.95 * (0.5 + 0.5 * math.cos(psi))
    target = M_atlas @ REAR - Vector((gap, 0, 0)); return by_nose(target, 0.0, D(8) + D(3) * math.sin(psi), 0.0)

def kiss_gap(t):
    if t < 5.5: return lerp(1.8, 0.0, smooth((t - T_KISS) / 0.2))
    if t < 5.78: return 0.0
    return lerp(0.0, 5.0, smooth((t - 5.78) / 0.7))

def kiss_mat(t, M_atlas):
    g = kiss_gap(t); nuzzle = D(4) * math.sin((t - 5.5) * 30) if 5.5 < t < 5.78 else 0.0
    rise = 1.2 * ramp(t, 5.8, 6.5); bob = 0.25 * math.sin(t * 4.5) * ramp(t, 6.2, 6.8)
    P = M_atlas @ CHIN + Vector((g, 0, rise + bob))
    return by_nose(P, math.pi, D(-3) + nuzzle - D(4) * ramp(t, 5.8, 6.5), 0.0)

def alecto_mat(t, M_atlas):
    if t < T_SETTLE: return orbit_mat(t)
    if t < T_HUMP: return blend(orbit_mat(t), hump_mat(T_HUMP, M_atlas, gap=1.4), smooth((t - T_SETTLE) / SETTLE_LEN))
    if t < T_FLIP: return hump_mat(t, M_atlas)
    if t < T_KISS:                                   # leap over Atlas with a barrel roll, turning around
        s = smooth((t - T_FLIP) / (T_KISS - T_FLIP))
        a = hump_mat(T_FLIP, M_atlas, gap=0.9).translation; b = kiss_mat(T_KISS, M_atlas).translation
        pos = a.lerp(b, s) + Vector((0, 0, 7.0 * math.sin(math.pi * s)))
        return mat_from(pos, math.pi * s, D(8) * (1 - s) + D(6) * s + D(25) * math.sin(math.pi * s), 2 * math.pi * s)
    return kiss_mat(t, M_atlas)

CAM_KEYS = [(0.0, (-1, 0, 1.5), 40, (0.2, -1, 0.8)), (2.0, (-1, 0, 1.5), 40, (0.2, -1, 0.8)), (2.7, (-5.5, 0, 2.2), 25, (0.28, -1, 0.34)),
            (4.6, (-4.5, 0, 2.4), 23, (0.28, -1, 0.34)), (5.3, (4.0, 0, 3.0), 21, (0.28, -1, 0.34)), (6.0, (3.6, 0, 3.2), 20, (0.28, -1, 0.3)),
            (8.8, (3.2, 0, 3.4), 17.5, (0.22, -1, 0.26))]

def cam_at(t):
    for (t0, p0, d0, o0), (t1, p1, d1, o1) in zip(CAM_KEYS, CAM_KEYS[1:]):
        if t <= t1:
            s = smooth((t - t0) / (t1 - t0))
            return Vector(p0).lerp(Vector(p1), s), lerp(d0, d1, s), Vector(o0).normalized().lerp(Vector(o1).normalized(), s)
    return Vector(CAM_KEYS[-1][1]), CAM_KEYS[-1][2], Vector(CAM_KEYS[-1][3])

# turret tracking during the orbit: follow Alecto with a lag, then unwind to the nearest full turn
LAG = 0.15
K_TURNS = round((phi(T_HUMP - LAG) - math.pi) / (2 * math.pi)) * 2 * math.pi
def atlas_turret_yaw(t):
    track = phi(t - LAG) - math.pi                    # Alecto starts the orbit behind-ish; 0 = facing forward
    if t < T_SETTLE: return track * ramp(t, 0.3, 0.7)
    if t < 2.9: return lerp(track, K_TURNS, smooth((t - T_SETTLE) / 0.9))
    shy = D(16) * ramp(t, 6.3, 6.9) + D(3) * math.sin(t * 3) * ramp(t, 6.9, 7.3)
    return K_TURNS + shy

# smoke: thin wisps off the ember from 6.35 s, an exhale out of the mantle at 7.25 s, a poof when the gun turns
for i in range(len(tip_smoke.objs)): tip_smoke.specs[i] = None
POOF_T = T_CIG
import random
rnd = random.Random(7)

def scene_at(f):
    t = f / FPS
    sc.frame_set(f)
    MA = atlas_mat(t); put(A.arm, MA)
    put(B.arm, alecto_mat(t, MA))
    # Atlas parts
    gun_pitch = D(28) * ramp(t, 3.1, 4.5) + D(2.5) * math.sin(hump_psi(t)) * ramp(t, 3.1, 3.5) * (1 - ramp(t, T_FLIP, T_FLIP + 0.2))
    gun_pitch = lerp(gun_pitch, D(11) + D(2) * math.sin(t * 2), ramp(t, T_CIG, T_CIG + 0.4))
    A.pose('jnt_turret', rot=(0, atlas_turret_yaw(t), 0))
    A.pose('jnt_gun', rot=(0, 0, gun_pitch))
    sb = max(0.001, 1 - ramp(t, T_CIG, T_CIG + 0.12)); A.pose('jnt_gun_barrel', scale=(sb, sb, sb))
    radar = 2.0 * t + 25 * max(0.0, t - 2.9) ** 1.6 * (1 - ramp(t, 5.0, 6.5)) + 6 * ramp(t, 5.0, 6.5) * t
    A.pose('jnt_Radar_Center', rot=(0, radar, 0))
    A.pose('jnt_Antnenna_Spinny1', rot=(0, radar * 1.7, 0))
    A.pose('jnt_Antnenna_Spinning2_Base', rot=(0, -radar * 1.3, 0))
    ext = 1.4 * ramp(t, 3.0, 4.4)
    A.pose('jnt_Antnenna_Extend_1', loc=(0, ext * 0.5, 0)); A.pose('jnt_Antnenna_Extend_2', loc=(0, ext * 0.5, 0))
    # Alecto parts: thruster fans always spinning, spoiler flaps while humping, wags after the kiss
    fan = 40 * t
    B.pose('jnt_right_thruster_blade', rot=(0, 0, fan)); B.pose('jnt_left_thruster_blade', rot=(0, 0, -fan))
    sp = D(15)
    if T_HUMP <= t < T_FLIP: sp = D(20) + D(28) * math.sin(hump_psi(t))
    elif t >= T_KISS + 0.4: sp = D(15) + D(30) * math.sin(t * 14) * ramp(t, 5.7, 6.0)
    B.pose('jnt_spoiler', rot=(0, 0, sp))
    B.pose('jnt_turret', rot=(0, D(10) * math.sin(t * 5) * ramp(t, 6.2, 6.6), 0))
    A.key(f); B.key(f)
    bpy.context.view_layer.update()

    # cigarette on the gun bone
    MG = A.bone_world('jnt_gun'); cs = ease_out_back((t - (T_CIG + 0.06)) / 0.3) if t > T_CIG + 0.06 else 0.0
    for o in cig:
        k = max(cs, 1e-4); l, q, _ = MG.decompose(); o.location = l; o.rotation_quaternion = q; o.scale = (k, k, k)
        key_obj(o, f)
    drag = math.exp(-((t - 6.95) / 0.25) ** 2)
    ember_strength.default_value = 5 + 30 * drag + 3 * math.sin(t * 13); ember_strength.keyframe_insert('default_value', frame=f)
    # blush on the turret cheeks
    MT = A.bone_world('jnt_turret'); bl = ease_out_back((t - 6.35) / 0.35) if t > 6.35 else 0.0
    pulse = 1 + 0.06 * math.sin(t * 8)
    for root, parts, off in blush:
        k = max(bl * pulse, 0.0001); M = MT @ off @ Matrix.Diagonal((k, k, k, 1)); l, q, s = M.decompose()
        root.location = l; root.rotation_quaternion = q; root.scale = s; key_obj(root, f)
        for p in parts: p.color[3] = 0.9 * clamp(bl); p.keyframe_insert('color', frame=f)
    # hearts: three pop out of the kiss, two drift up while smoking
    contact = MA @ CHIN
    hspecs = [(5.52, contact + Vector((0, -0.6, 1.0)), (0.0, -0.2, 2.2), 1.3), (5.62, contact + Vector((0.6, -0.4, 1.5)), (0.6, -0.1, 2.0), 1.0),
              (5.72, contact + Vector((-0.5, -0.4, 1.4)), (-0.5, -0.2, 2.4), 0.8),
              (7.4, MA @ Vector((-1.5, -1.0, 4.6)), (-0.2, -0.1, 1.4), 0.9), (7.9, MA @ Vector((-0.5, -1.0, 4.7)), (0.3, -0.1, 1.5), 0.7)]
    for h, (t0, p0, v, size) in zip(hearts, hspecs):
        u = (t - t0) / 1.6
        if 0 <= u <= 1:
            k = size * ease_out_back(u / 0.18) if u < 0.18 else size
            h.location = p0 + Vector(v) * (t - t0) + Vector((0, 0, 0)); h.scale = (k, k, k)
            h.rotation_quaternion = Euler((0, 0, D(-15) + 0.25 * math.sin((t - t0) * 6))).to_quaternion()
            key_obj(h, f, clamp((1 - u) * 3))
        else:
            h.scale = (0, 0, 0); key_obj(h, f, 0.0)
    for P in (tip_smoke, exhale, poof): P.key(t, f)

# emit puffs (positions depend on the cigarette tip, so the specs are filled in a first pass over the timeline)
def tip_world(t):
    sc.frame_set(int(t * FPS)); bpy.context.view_layer.update()
    return A.bone_world('jnt_gun') @ Vector((CIG1 + 0.1, 0, 0))

def mantle_world(t):
    sc.frame_set(int(t * FPS)); bpy.context.view_layer.update()
    return A.bone_world('jnt_gun') @ Vector((0.7, 0, -0.2))

for f in range(F): scene_at(f)          # first pass: body + bone keys (puffs not yet placed)
i = 0; t = 6.35
while i < len(tip_smoke.objs) and t < DUR:
    tip_smoke.emit(i, t, tip_world(t) + Vector((0, 0, 0.1)), (rnd.uniform(-0.25, 0.1), rnd.uniform(0.0, 0.3), 1.5), 0.1, 0.45, 1.5, 0.5)
    i += 1; t += 0.1 + (0.06 if 6.8 < t < 7.1 else 0)
for i in range(len(exhale.objs)):
    t0 = 7.25 + i * 0.05; p = mantle_world(t0)
    exhale.emit(i, t0, p, (rnd.uniform(0.6, 1.6), rnd.uniform(0.2, 1.0), rnd.uniform(1.6, 2.6)), 0.2, 0.75, 1.4, 0.55)
for i in range(len(poof.objs)):
    ang = 2 * math.pi * i / len(poof.objs); p = A.bone_world('jnt_gun') @ Vector((3.0 + rnd.uniform(-1.4, 1.4), 0, 0))
    poof.emit(i, POOF_T + rnd.uniform(0, 0.05), p, (rnd.uniform(-1, 1), math.cos(ang) * 2.0, math.sin(ang) * 2.0 + 0.5), 0.3, 0.95, 0.4, 0.9)
for f in range(F):
    t = f / FPS; sc.frame_set(f)
    for P in (tip_smoke, exhale, poof): P.key(t, f)
    c, d, o = cam_at(t); aim(cam, c, o, d); cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)

os.makedirs(OUT, exist_ok=True)
sc.render.filepath = os.path.join(OUT, 'f_')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'scene.blend'))
if len(argv) > 2:      # render only a frame list "a,b,c"
    for f in map(int, argv[2].split(',')):
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f'f_{f:04d}'); bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
print('DONE', OUT)
