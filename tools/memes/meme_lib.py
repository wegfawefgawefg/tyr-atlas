"""Shared Blender helpers for the tank meme animations (run inside `blender -b -P`).

Tanks come from extract/art (tools/render_all.sh exports them). Every bone in these rigs has the same axes:
local X = tank forward (+X world at rest), local Y = up, local Z = -Y world. So a pose-bone euler (x, y, z) is
(roll, yaw, pitch nose-up).
"""
import bpy, bmesh, glob, json, math, os
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.bvhtree import BVHTree

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
ART = os.path.join(REPO, 'extract/art')


# ---------- small maths ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def smooth(x): x = clamp(x); return x * x * (3 - 2 * x)
def ramp(t, t0, t1): return smooth((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)
def lerp(a, b, s): return a + (b - a) * s
def ease_out_back(x, k=1.70158):
    x = clamp(x) - 1; return 1 + (k + 1) * x ** 3 + k * x ** 2

def mat_from(loc, yaw=0.0, pitch=0.0, roll=0.0):
    """World matrix for a tank body: yaw about Z, then pitch nose-up, then roll about forward (radians)."""
    r = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(-pitch, 4, 'Y') @ Matrix.Rotation(roll, 4, 'X')
    return Matrix.Translation(Vector(loc)) @ r

def blend(m1, m2, s):
    l1, q1, _ = m1.decompose(); l2, q2, _ = m2.decompose()
    return Matrix.Translation(l1.lerp(l2, s)) @ q1.slerp(q2, s).to_matrix().to_4x4()

def put(obj, m):
    obj.rotation_mode = 'QUATERNION'
    l, q, s = m.decompose(); obj.location = l; obj.rotation_quaternion = q


# ---------- scene ----------
def reset(fps=24, frames=200, w=640, h=360, samples=32, scale=200):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = fps; sc.frame_start = 0; sc.frame_end = frames - 1
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = samples; sc.cycles.use_denoising = False
    sc.render.resolution_x = w; sc.render.resolution_y = h; sc.render.resolution_percentage = scale
    sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    vt = [v.identifier for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items]
    sc.view_settings.view_transform = 'AgX' if 'AgX' in vt else 'Filmic'
    sc.cycles.max_bounces = 4; sc.cycles.transparent_max_bounces = 16
    return sc


def stage(ctr=(0, 0, 2), rad=8.0):
    sc = bpy.context.scene; ctr = Vector(ctr)
    def light(name, loc, energy, colour, size_):
        L = bpy.data.lights.new(name, 'AREA'); L.energy = energy; L.color = colour; L.size = size_
        o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
        o.rotation_euler = (ctr - o.location).to_track_quat('-Z', 'Y').to_euler()
    light('key', ctr + Vector((rad * 1.2, -rad * 2.2, rad * 2.0)), 550 * rad * rad, (1.0, 0.97, 0.93), rad * 2)
    light('rim_m', ctr + Vector((-rad * 2.4, rad * 1.6, rad * 0.8)), 260 * rad * rad, (1.0, 0.15, 0.85), rad * 0.8)
    light('rim_c', ctr + Vector((rad * 2.4, rad * 1.6, rad * 0.6)), 420 * rad * rad, (0.1, 0.85, 1.0), rad * 0.8)
    light('top', ctr + Vector((0, 0, rad * 3.0)), 160 * rad * rad, (0.85, 0.9, 1.0), rad * 3)
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.012, 0.008, 0.03, 1); bg.inputs['Strength'].default_value = 1.0
    # floor: dark glossy with a faint neon grid, like the site
    bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 0, 0)); fl = bpy.context.active_object; fl.name = 'floor'
    m = bpy.data.materials.new('floor'); m.use_nodes = True; nt = m.node_tree; N = nt.nodes; Lk = nt.links
    b = N['Principled BSDF']; b.inputs['Base Color'].default_value = (0.03, 0.025, 0.05, 1); b.inputs['Roughness'].default_value = 0.55; b.inputs['Specular IOR Level'].default_value = 0.15
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); Lk.new(tc.outputs['Object'], sep.inputs[0])
    lines = []
    for ax in ('X', 'Y'):
        a = N.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; a.inputs[1].default_value = 0.25; Lk.new(sep.outputs[ax], a.inputs[0])
        f = N.new('ShaderNodeMath'); f.operation = 'FRACT'; Lk.new(a.outputs[0], f.inputs[0])
        s = N.new('ShaderNodeMath'); s.operation = 'SUBTRACT'; s.inputs[1].default_value = 0.5; Lk.new(f.outputs[0], s.inputs[0])
        ab = N.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; Lk.new(s.outputs[0], ab.inputs[0])
        g = N.new('ShaderNodeMath'); g.operation = 'GREATER_THAN'; g.inputs[1].default_value = 0.485; Lk.new(ab.outputs[0], g.inputs[0])
        lines.append(g)
    mx = N.new('ShaderNodeMath'); mx.operation = 'MAXIMUM'; Lk.new(lines[0].outputs[0], mx.inputs[0]); Lk.new(lines[1].outputs[0], mx.inputs[1])
    st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; st.inputs[1].default_value = 0.7; Lk.new(mx.outputs[0], st.inputs[0])
    b.inputs['Emission Color'].default_value = (0.75, 0.2, 1.0, 1); Lk.new(st.outputs[0], b.inputs['Emission Strength'])
    fl.data.materials.append(m)


def camera(lens=50):
    sc = bpy.context.scene
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.lens = lens; cam.data.clip_end = 1000
    return cam

def aim(cam, target, offset_dir, dist):
    d = Vector(offset_dir).normalized(); cam.location = Vector(target) + d * dist
    cam.rotation_mode = 'XYZ'; cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()


# ---------- tanks ----------
def _tex_path(art_top, ue_path):
    p = ue_path.split('.')[0]
    cand = os.path.join(art_top, 'Tyr/Content', p[len('/Game/'):] + '.png') if p.startswith('/Game/') else os.path.join(art_top, p.strip('/') + '.png')
    return cand if os.path.exists(cand) else None

def _image(path, colour):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'; return img

def _materials(mats, root, art_top):
    """Same material rebuild as tools/render_tank.py (colour, DX normal, emissive, metal/rough)."""
    for mat in mats:
        js = glob.glob(os.path.join(root, 'Materials', mat.name.split('.')[0] + '.json'))
        if not js: continue
        J = json.load(open(js[0])); T = J.get('Textures', {}); P = J.get('Parameters', {})
        S = P.get('Scalars', {}); C = P.get('Colors', {})
        mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
        out_n = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        nt.links.new(bsdf.outputs['BSDF'], out_n.inputs['Surface'])
        bsdf.inputs['Metallic'].default_value = S.get('Metallic', 0.5); bsdf.inputs['Roughness'].default_value = S.get('Roughness', 0.4)
        col = next((T[k] for k in ('Tank_ Color Map', 'PM_Diffuse', 'Diffuse', 'BaseColor') if k in T), None)
        generic = col and 'T_Tank_Base_C' in col
        if col and _tex_path(art_top, col) and not (generic and 'Color' in C):
            n = nt.nodes.new('ShaderNodeTexImage'); n.image = _image(_tex_path(art_top, col), True)
            nt.links.new(n.outputs['Color'], bsdf.inputs['Base Color'])
        elif 'Color' in C:
            c = C['Color']; bsdf.inputs['Base Color'].default_value = (c['R'], c['G'], c['B'], 1)
        nrm = next((T[k] for k in ('Tank_ NRM Map', 'Normals', 'Normal') if k in T), None)
        if nrm and _tex_path(art_top, nrm):
            n = nt.nodes.new('ShaderNodeTexImage'); n.image = _image(_tex_path(art_top, nrm), False)
            sep = nt.nodes.new('ShaderNodeSeparateColor'); comb = nt.nodes.new('ShaderNodeCombineColor'); inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
            nt.links.new(n.outputs['Color'], sep.inputs['Color'])
            nt.links.new(sep.outputs['Red'], comb.inputs['Red']); nt.links.new(sep.outputs['Green'], inv.inputs[1])
            nt.links.new(inv.outputs['Value'], comb.inputs['Green']); comb.inputs['Blue'].default_value = 1.0
            nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(comb.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        em = next((T[k] for k in ('Tank_ Emissive Map', 'PM_Emissive') if k in T), None); ec = C.get('Emissive Color')
        if em and _tex_path(art_top, em) and ec:
            n = nt.nodes.new('ShaderNodeTexImage'); n.image = _image(_tex_path(art_top, em), False)
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
            nt.links.new(n.outputs['Color'], mix.inputs[6]); mix.inputs[7].default_value = (ec['R'], ec['G'], ec['B'], 1)
            nt.links.new(mix.outputs[2], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 3.0 * S.get('Emissive Multiplier', 1.0)
        elif 'Glow' in mat.name and ec:
            bsdf.inputs['Emission Color'].default_value = (ec['R'], ec['G'], ec['B'], 1); bsdf.inputs['Emission Strength'].default_value = 6.0


class Tank:
    """One imported tank: .arm (armature object, move it for the whole body), .mesh, .pb(name) pose bones."""
    def __init__(self, vehicle, label):
        sc = bpy.context.scene
        glb = sorted(glob.glob(os.path.join(ART, f'TyrVehicle{vehicle}', '**', 'SK_*Visual*.glb'), recursive=True))[0]
        before_o, before_m = set(sc.objects), set(bpy.data.materials)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in sc.objects if o not in before_o]
        for o in new:
            if o.type == 'MESH' and o.name.startswith('Icosphere'): bpy.data.objects.remove(o, do_unlink=True)
        new = [o for o in sc.objects if o not in before_o]
        root = os.path.dirname(os.path.dirname(glb)); _materials([m for m in bpy.data.materials if m not in before_m], root, os.path.dirname(root))
        self.arm = next(o for o in new if o.type == 'ARMATURE'); self.arm.name = label
        self.mesh = next(o for o in new if o.type == 'MESH')
        for p in self.arm.pose.bones: p.rotation_mode = 'XYZ'
        self.verts = [v.co.copy() for v in self.mesh.data.vertices]   # rest pose, armature space
        self.keyed = set()

    def pb(self, name): return self.arm.pose.bones[name]

    def bone_world(self, name):
        """World matrix of a posed bone, with the rest orientation (X forward, Y up) - not Blender's bone-Y convention."""
        p = self.pb(name); return self.arm.matrix_world @ p.matrix

    def rest_bone(self, name): return self.arm.data.bones[name].matrix_local

    def pose(self, name, rot=None, loc=None, scale=None):
        p = self.pb(name)
        if rot is not None: p.rotation_euler = rot; self.keyed.add((name, 'rotation_euler'))
        if loc is not None: p.location = loc; self.keyed.add((name, 'location'))
        if scale is not None: p.scale = scale; self.keyed.add((name, 'scale'))

    def rot(self, name, yaw=0.0, pitch=0.0, roll=0.0):
        """Pose-bone euler for a rotation given in the tank's own frame (yaw about up, pitch nose-up, roll about forward).
        Bones differ in their rest axes (Valor's gun bones are Z-up, most others Y-up), so convert per bone."""
        L = self.arm.data.bones[name].matrix_local.to_3x3().inverted()
        R = (Matrix.Rotation(yaw, 3, L @ Vector((0, 0, 1))) @ Matrix.Rotation(pitch, 3, L @ Vector((0, -1, 0)))
             @ Matrix.Rotation(roll, 3, L @ Vector((1, 0, 0))))
        return R.to_euler('XYZ')

    def key(self, f):
        self.arm.keyframe_insert('location', frame=f); self.arm.keyframe_insert('rotation_quaternion', frame=f)
        for name, prop in self.keyed: self.pb(name).keyframe_insert(prop, frame=f)

    def tip(self, axis=0, sign=1, band=0.3):
        """Average rest-pose vertex in the extreme `band` metres along an axis: the nose (0,+1), tail (0,-1), ..."""
        ext = max(sign * v[axis] for v in self.verts)
        pts = [v for v in self.verts if sign * v[axis] > ext - band]
        return sum(pts, Vector()) / len(pts)

    def ray(self, origin, direction):
        """Ray against the rest-pose mesh in armature space; returns (hit, normal) or (None, None)."""
        if not hasattr(self, '_bvh'):
            me = self.mesh.data; self._bvh = BVHTree.FromPolygons(self.verts, [tuple(p.vertices) for p in me.polygons])
        h, n, _, _ = self._bvh.ray_cast(Vector(origin), Vector(direction).normalized())
        return h, n


# ---------- props ----------
def material(name, colour, rough=0.5, emit=0.0, emit_col=None, alpha_from_object=False, metallic=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; N = m.node_tree.nodes; b = N['Principled BSDF']
    b.inputs['Base Color'].default_value = (*colour, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metallic
    if emit: b.inputs['Emission Color'].default_value = (*(emit_col or colour), 1); b.inputs['Emission Strength'].default_value = emit
    if alpha_from_object:
        oi = N.new('ShaderNodeObjectInfo'); m.node_tree.links.new(oi.outputs['Alpha'], b.inputs['Alpha'])
    return m

def obj_from_bm(name, bm, mat=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(o)
    if mat: me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    return o

def cylinder_x(name, r, x0, x1, mat, segs=24):
    """Cylinder along +X from x0 to x1 (local)."""
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=x1 - x0)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    bmesh.ops.translate(bm, verts=bm.verts, vec=((x0 + x1) / 2, 0, 0))
    o = obj_from_bm(name, bm, mat)
    for p in o.data.polygons: p.use_smooth = abs(p.normal.x) < 0.5
    return o

def sphere(name, r, mat, segs=16):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r)
    return obj_from_bm(name, bm, mat)

def heart(name, size, depth, mat):
    """Extruded heart in the XZ plane (faces -Y), about `size` metres tall."""
    bm = bmesh.new(); n = 48; pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3; z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append(bm.verts.new((x * size / 32, 0, (z + 2) * size / 32)))
    f = bm.faces.new(pts)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f]); vs = [e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=vs, vec=(0, depth, 0)); bmesh.ops.translate(bm, verts=bm.verts, vec=(0, -depth / 2, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = obj_from_bm(name, bm, mat)
    for p in o.data.polygons: p.use_smooth = False
    return o

def key_obj(o, f, alpha=None):
    o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_quaternion', frame=f); o.keyframe_insert('scale', frame=f)
    if alpha is not None: o.color[3] = alpha; o.keyframe_insert('color', frame=f)


class Puffs:
    """Cartoon smoke/poof: a pool of soft white spheres, each with a spawn time, start point, drift, life."""
    def __init__(self, name, count, mat):
        self.objs = [sphere(f'{name}{i}', 1.0, mat, 12) for i in range(count)]; self.specs = [None] * count
        for o in self.objs: o.rotation_mode = 'QUATERNION'

    def emit(self, i, t0, pos, vel, r0, r1, life, alpha=0.85):
        self.specs[i] = (t0, Vector(pos), Vector(vel), r0, r1, life, alpha)

    def key(self, t, f):
        for o, sp in zip(self.objs, self.specs):
            if sp is None: o.scale = (0, 0, 0); key_obj(o, f, 0.0); continue
            t0, p, v, r0, r1, life, a = sp; u = (t - t0) / life
            if u < 0 or u > 1: o.scale = (0, 0, 0); o.location = p; key_obj(o, f, 0.0); continue
            r = lerp(r0, r1, 1 - (1 - u) ** 2); o.location = p + v * (t - t0); o.scale = (r, r, r)
            key_obj(o, f, a * (1 - u) ** 1.5 * min(1, u * 8))
