using CUE4Parse_Conversion.Textures;
// Art export: each tank's visual meshes as glTF with materials and textures (for Blender renders).
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Meshes;
using CUE4Parse.UE4.Assets.Exports;

static class ArtExport
{
    public static void Run(DefaultFileProvider provider, string outDir, string? only)
    {
        TextureDecoder.UseAssetRipperTextureDecoder = true;   // managed BC decoders (no native Detex on Linux)
        var opts = new ExporterOptions { MeshFormat = EMeshFormat.Gltf2, LodFormat = ELodFormat.FirstLod, ExportMaterials = true, TextureFormat = ETextureFormat.Png };
        var pattern = new System.Text.RegularExpressions.Regex(@"^Tyr/Plugins/GameFeatures/Vehicles/([^/]+)/Content/Meshes/(SK_[A-Za-z]+_[A-Za-z_]*Visual[A-Za-z0-9_]*)\.uasset$");
        foreach (var path in provider.Files.Keys.Where(p => pattern.IsMatch(p)).OrderBy(p => p))
        {
            var veh = pattern.Match(path).Groups[1].Value;
            if (only != null && !veh.Contains(only)) continue;
            try
            {
                var obj = provider.LoadPackage(path).GetExports().FirstOrDefault(e => e is USkeletalMesh || e is UStaticMesh);
                if (obj == null) continue;
                var exporter = obj is USkeletalMesh sk ? new MeshExporter(sk, opts) : new MeshExporter((UStaticMesh)obj, opts);
                var dir = new DirectoryInfo(Path.Combine(outDir, veh)); dir.Create();
                var ok = exporter.TryWriteToDir(dir, out var label, out var saved);
                Console.WriteLine($"{veh}: {obj.Name} -> {(ok ? saved : "FAILED")} {label}");
            }
            catch (Exception e) { Console.Error.WriteLine($"FAIL {path}: {e.Message}"); }
        }
    }
}
