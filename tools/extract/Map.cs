// Map export: landscape heightmaps + components, mesh placements (world transforms), gameplay actors, coarse mesh geometry.
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Component;
using CUE4Parse.UE4.Assets.Exports.Component.Landscape;
using CUE4Parse.UE4.Assets.Exports.Component.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.UObject;
using Newtonsoft.Json;

static class MapExport
{
    static object T(FTransform t) => new { t = new[] { t.Translation.X, t.Translation.Y, t.Translation.Z }, q = new[] { t.Rotation.X, t.Rotation.Y, t.Rotation.Z, t.Rotation.W }, s = new[] { t.Scale3D.X, t.Scale3D.Y, t.Scale3D.Z } };
    static readonly string[] GameplayHints = { "BlockingVolume", "CaptureZone", "HealZone", "AmmunitionZone", "AbilityResourceZone", "NoGoZone", "Spawn", "PlayerStart", "Bush", "ZoneSelector", "PowerUp" };

    public static void Run(DefaultFileProvider provider, string outDir, string mapPath)
    {
        PropertyUtil.SearchPropertyInTemplate = true;
        Directory.CreateDirectory(outDir);
        var meshDir = Path.Combine(outDir, "meshes"); Directory.CreateDirectory(meshDir);
        var placements = new List<object>(); var land = new List<object>(); var actors = new List<object>(); var levelInstances = new List<object>();
        var meshes = new HashSet<string>(); var heightmaps = new Dictionary<string, object>();
        void Package(string path, FTransform? outer)
        {
            var exports = provider.LoadPackage(path).GetExports().ToList();
            foreach (var ex in exports)
            {
                try
                {
                    if (ex is ULandscapeComponent lc)
                    {
                        var hm = lc.GetHeightmap();
                        var tr = lc.GetAbsoluteTransform(); if (outer.HasValue) tr = tr * outer.Value;
                        if (hm != null && !heightmaps.ContainsKey(hm.Name))
                        {
                            var mip = hm.GetFirstMip()!; var data = mip.BulkData?.Data;
                            if (data != null) File.WriteAllBytes(Path.Combine(outDir, $"hm_{hm.Name}.{hm.Format}.{mip.SizeX}x{mip.SizeY}.raw"), data);
                            heightmaps[hm.Name] = new { w = mip.SizeX, h = mip.SizeY, fmt = hm.Format.ToString() };
                        }
                        land.Add(new { name = lc.Name, xf = T(tr), sbx = lc.SectionBaseX, sby = lc.SectionBaseY, size = lc.ComponentSizeQuads, sub = lc.SubsectionSizeQuads, nsub = lc.NumSubsections,
                            hsb = new[] { lc.HeightmapScaleBias.X, lc.HeightmapScaleBias.Y, lc.HeightmapScaleBias.Z, lc.HeightmapScaleBias.W }, hm = hm?.Name });
                    }
                    else if (ex is UStaticMeshComponent smc)
                    {
                        var mi = smc.GetOrDefault<FPackageIndex>("StaticMesh");
                        var mesh = mi?.ResolvedObject?.GetPathName();
                        if (mesh == null) continue;
                        var tr = smc.GetAbsoluteTransform(); if (outer.HasValue) tr = tr * outer.Value;
                        var collide = smc.GetOrDefault("bCanEverAffectNavigation", true);
                        var owner = smc.Outer?.Name ?? "";
                        if (smc is UInstancedStaticMeshComponent ism && ism.PerInstanceSMData != null)
                        {
                            var list = ism.PerInstanceSMData.Select(i => T(i.TransformData * tr)).ToList();
                            placements.Add(new { mesh, owner, type = ex.ExportType, inst = list });
                        }
                        else placements.Add(new { mesh, owner, type = ex.ExportType, xf = T(tr) });
                        meshes.Add(mesh);
                    }
                    else if (ex is USceneComponent sc && GameplayHints.Any(h => (sc.Outer?.Name ?? "").Contains(h) || sc.ExportType.Contains(h)))
                    {
                        var tr = sc.GetAbsoluteTransform(); if (outer.HasValue) tr = tr * outer.Value;
                        float[]? brush = null;
                        if (sc.ExportType == "BrushComponent")
                        {
                            var model = sc.GetOrDefault<FPackageIndex>("Brush")?.Load<CUE4Parse.UE4.Objects.Engine.UModel>();
                            if (model?.Points != null) brush = model.Points.SelectMany(p => new[] { (float)p.X, (float)p.Y, (float)p.Z }).ToArray();
                        }
                        actors.Add(new { owner = sc.Outer?.Name, cls = sc.Outer is UObject o ? o.ExportType : "", comp = sc.Name, type = sc.ExportType, xf = T(tr), brush,
                            box = sc.GetOrDefault<FVector?>("BoxExtent", null), sphere = sc.GetOrDefault<float?>("SphereRadius", null),
                            capsule = new[] { sc.GetOrDefault<float>("CapsuleRadius", 0), sc.GetOrDefault<float>("CapsuleHalfHeight", 0) } });
                    }
                    if (ex is USceneComponent lic && ex.ExportType == "LevelInstanceComponent")
                    {
                        var owner = lic.Outer as UObject;
                        var world = owner?.GetOrDefault<FSoftObjectPath?>("WorldAsset", null);
                        var tr = lic.GetAbsoluteTransform(); if (outer.HasValue) tr = tr * outer.Value;
                        levelInstances.Add(new { owner = owner?.Name, world = world?.AssetPathName.Text, xf = T(tr) });
                        var wp = world?.AssetPathName.Text;
                        if (!string.IsNullOrEmpty(wp))
                        {
                            var pkg = wp.Split('.')[0];
                            var file = provider.Files.Keys.FirstOrDefault(k => k.EndsWith(pkg.Replace("/Game/", "Tyr/Content/").TrimStart('/') + ".umap", StringComparison.OrdinalIgnoreCase)
                                                                             || k.EndsWith(pkg.TrimStart('/').Split('/', 2).Last() + ".umap", StringComparison.OrdinalIgnoreCase));
                            if (file != null) Package(file, tr);
                        }
                    }
                }
                catch (Exception e) { Console.Error.WriteLine($"skip {ex.Name}: {e.Message}"); }
            }
        }
        Package(mapPath, null);
        // gameplay layer next to the map, if any
        var gp = mapPath.Replace(".umap", "_Gameplay.umap");
        if (provider.Files.ContainsKey(gp) && gp != mapPath) Package(gp, null);
        // coarse mesh geometry
        var meshInfo = new Dictionary<string, object>();
        foreach (var m in Environment.GetEnvironmentVariable("TYR_MAP_ACTORS_ONLY") == "1" ? new HashSet<string>() : meshes)
        {
            try
            {
                var sm = provider.LoadPackageObject<UStaticMesh>(m);
                var lods = sm.RenderData?.LODs;
                if (lods == null || lods.Length == 0) { Console.Error.WriteLine($"mesh {m}: no LODs (render data {(sm.RenderData == null ? "null" : "present")}, cooked {sm.bCooked}, filterEditorOnly {sm.Owner?.Summary.PackageFlags})"); continue; }
                var li = Math.Min(2, lods.Length - 1); var lod = lods[li];
                var pv = lod.PositionVertexBuffer!.Verts; var idx = lod.IndexBuffer!.Buffer!;
                var pos = new float[pv.Length * 3];
                for (var i = 0; i < pv.Length; i++) { pos[i * 3] = (float)pv[i].X; pos[i * 3 + 1] = (float)pv[i].Y; pos[i * 3 + 2] = (float)pv[i].Z; }
                var file = Path.Combine(meshDir, Convert.ToHexString(System.Security.Cryptography.SHA1.HashData(System.Text.Encoding.UTF8.GetBytes(m)))[..16] + ".json");
                File.WriteAllText(file, JsonConvert.SerializeObject(new { lod = li, pos, idx }));
                meshInfo[m] = new { lod = li, verts = pv.Length, tris = idx.Length / 3, file = Path.GetFileName(file) };
            }
            catch (Exception e) { Console.Error.WriteLine($"mesh {m}: {e.Message}"); }
        }
        var mapJson = Path.Combine(outDir, Environment.GetEnvironmentVariable("TYR_MAP_ACTORS_ONLY") == "1" ? "map_actors.json" : "map.json");
        File.WriteAllText(mapJson, JsonConvert.SerializeObject(new { map = mapPath, land, heightmaps, placements, actors, levelInstances, meshes = meshInfo }));
        Console.WriteLine($"{mapPath}: land {land.Count}, placements {placements.Count}, actors {actors.Count}, level instances {levelInstances.Count}, meshes {meshInfo.Count}");
    }
}
