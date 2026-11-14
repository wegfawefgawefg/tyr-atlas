"""Blender (headless) render of one tank from its exported glTF + material JSON.

usage: blender -b -t 4 -P tools/render_tank.py -- <art dir for the vehicle> <out.png> [angle_deg] [size]
Materials are rebuilt from CUE4Parse's material JSON: colour map, normal map (DirectX -> OpenGL: green flipped),
emissive map x emissive colour, metallic/roughness scalars. Transparent background so the site can composite it.
"""
import bpy, sys, os, json, glob, math
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
art, out = argv[0], argv[1]
angle = float(argv[2]) if len(argv) > 2 else 35.0
size = int(argv[3]) if len(argv) > 3 else 1400

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
glb = sorted(glob.glob(os.path.join(art, '**', 'SK_*Visual*.glb'), recursive=True))[0]
bpy.ops.import_scene.gltf(filepath=glb)
root = os.path.dirname(os.path.dirname(glb))          # <veh>/<veh>
art_top = os.path.dirname(root)

def tex_path(ue_path):
    """'/TyrVehicleRam/Textures/T_X.T_X' or '/Game/Vehicles/...' -> exported png"""
    p = ue_path.split('.')[0]
    if p.startswith('/Game/'): cand = os.path.join(art_top, 'Tyr/Content', p[len('/Game/'):] + '.png')
    else: cand = os.path.join(art_top, p.strip('/') + '.png')
    return cand if os.path.exists(cand) else None

def image(path, colour):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    return img

for mat in bpy.data.materials:
    js = glob.glob(os.path.join(root, 'Materials', mat.name + '.json'))
    if not js: continue
    J = json.load(open(js[0])); T = J.get('Textures', {}); P = J.get('Parameters', {})
    S = P.get('Scalars', {}); C = P.get('Colors', {})
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    out_n = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out_n.inputs['Surface'])
    bsdf.inputs['Metallic'].default_value = S.get('Metallic', 0.5)
    bsdf.inputs['Roughness'].default_value = S.get('Roughness', 0.4)
    col = next((T[k] for k in ('Tank_ Color Map', 'PM_Diffuse', 'Diffuse', 'BaseColor') if k in T), None)
    generic = col and 'T_Tank_Base_C' in col          # placeholder texture: the material's Color tint carries the paint
    if col and tex_path(col) and not (generic and 'Color' in C):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = image(tex_path(col), True)
        nt.links.new(n.outputs['Color'], bsdf.inputs['Base Color'])
    elif 'Color' in C:
        c = C['Color']; bsdf.inputs['Base Color'].default_value = (c['R'], c['G'], c['B'], 1)
    nrm = next((T[k] for k in ('Tank_ NRM Map', 'Normals', 'Normal') if k in T), None)
    if nrm and tex_path(nrm):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = image(tex_path(nrm), False)
        sep = nt.nodes.new('ShaderNodeSeparateColor'); comb = nt.nodes.new('ShaderNodeCombineColor'); inv = nt.nodes.new('ShaderNodeMath')
        inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        nt.links.new(n.outputs['Color'], sep.inputs['Color'])
        nt.links.new(sep.outputs['Red'], comb.inputs['Red']); nt.links.new(sep.outputs['Green'], inv.inputs[1])
        nt.links.new(inv.outputs['Value'], comb.inputs['Green']); comb.inputs['Blue'].default_value = 1.0
        nm = nt.nodes.new('ShaderNodeNormalMap'); nt.links.new(comb.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    em = next((T[k] for k in ('Tank_ Emissive Map', 'PM_Emissive') if k in T), None)
    ec = C.get('Emissive Color')
    if em and tex_path(em) and ec:
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = image(tex_path(em), False)
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'; mix.inputs['Factor'].default_value = 1.0
        nt.links.new(n.outputs['Color'], mix.inputs[6]); mix.inputs[7].default_value = (ec['R'], ec['G'], ec['B'], 1)
        nt.links.new(mix.outputs[2], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = 3.0 * S.get('Emissive Multiplier', 1.0)
    elif 'Glow' in mat.name and ec:
        bsdf.inputs['Emission Color'].default_value = (ec['R'], ec['G'], ec['B'], 1); bsdf.inputs['Emission Strength'].default_value = 6.0

# frame the tank
objs = [o for o in sc.objects if o.type == 'MESH']
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (mn + mx) / 2; rad = (mx - mn).length / 2
# camera: low three-quarter view, hard angle; distance solved so the bounding-box corners fill the frame
a = math.radians(angle)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 70; cam.data.sensor_fit = 'HORIZONTAL'
aspect = 0.62
th, tv = 18 / 70, 18 * aspect / 70                 # tan of half fov
fwd = -Vector((math.cos(a), math.sin(a), 0.32)).normalized()
right = fwd.cross(Vector((0, 0, 1))).normalized(); up = right.cross(fwd).normalized()
margin = 0.88
need = 0.0
for p in pts:
    d = p - ctr
    px, py, pz = abs(d.dot(right)), abs(d.dot(up)), d.dot(fwd)
    need = max(need, px / (th * margin) - pz, py / (tv * margin) - pz)
cam.location = ctr - fwd * need
cam.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
# lights: key, magenta rim, cyan rim, soft top
def light(name, kind, loc, energy, colour, size_=None):
    L = bpy.data.lights.new(name, kind); L.energy = energy; L.color = colour
    if size_ and kind == 'AREA': L.size = size_
    o = bpy.data.objects.new(name, L); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (ctr - o.location).to_track_quat('-Z', 'Y').to_euler(); return o
light('key', 'AREA', ctr + Vector((rad * 2.2, rad * 1.2, rad * 2.0)), 550 * rad * rad, (1.0, 0.97, 0.93), rad * 2)
light('rim_m', 'AREA', ctr + Vector((-rad * 2.4, rad * 1.6, rad * 0.8)), 260 * rad * rad, (1.0, 0.15, 0.85), rad * 0.8)
light('rim_c', 'AREA', ctr + Vector((-rad * 1.6, -rad * 2.4, rad * 0.6)), 420 * rad * rad, (0.1, 0.85, 1.0), rad * 0.8)
light('top', 'AREA', ctr + Vector((0, 0, rad * 3.0)), 160 * rad * rad, (0.85, 0.9, 1.0), rad * 3)
# world: dark gradient for reflections only (background stays transparent)
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.02, 0.02, 0.035, 1); bg.inputs['Strength'].default_value = 0.6
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 64; sc.cycles.use_denoising = False   # this Blender build has no OIDN; render at 2x and downscale instead
sc.render.film_transparent = True
sc.render.resolution_x = size * 2; sc.render.resolution_y = int(size * 0.62) * 2
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
sc.view_settings.view_transform = 'AgX' if 'AgX' in [v.identifier for v in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
print('rendered', out)
