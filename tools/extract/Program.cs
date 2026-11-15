using Serilog;
// Tyr asset extractor. usage:
//   extract list                      -> all package paths
//   extract json <outdir> <prefix>... -> dump packages under prefixes as JSON
using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;

// TYR_GAME: the game folder (steamapps/common/Tyr). The pak AES key comes from TYR_AES_KEY or extract/aes.key (not in the repo).
var Game = Path.Combine(Environment.GetEnvironmentVariable("TYR_GAME") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".local/share/Steam/steamapps/common/Tyr"), "Tyr/Content/Paks");
var keyFile = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../extract/aes.key"));
var Key = (Environment.GetEnvironmentVariable("TYR_AES_KEY") ?? (File.Exists(keyFile) ? File.ReadAllText(keyFile) : null))?.Trim()
    ?? throw new Exception("no AES key: set TYR_AES_KEY or write it to extract/aes.key");
if (Environment.GetEnvironmentVariable("TYR_LOG") == "1") Log.Logger = new LoggerConfiguration().MinimumLevel.Warning().WriteTo.Console().CreateLogger();
var here = AppContext.BaseDirectory;
OodleHelper.Initialize(Path.GetFullPath(Path.Combine(here, "../../../../../third_party/oodle/lib/liboodle-data-shared.so")));

var ver = Enum.Parse<EGame>(Environment.GetEnvironmentVariable("TYR_UE") ?? "GAME_UE5_LATEST");
var provider = new DefaultFileProvider(Game, SearchOption.TopDirectoryOnly, new VersionContainer(ver));
provider.MappingsContainer = new CUE4Parse.MappingsProvider.FileUsmapTypeMappingsProvider(Path.GetFullPath(Path.Combine(here, "../../../../../extract/Tyr.usmap")));
provider.ReadScriptData = true;
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey(Key));
provider.PostMount();

if (args[0] == "list")
{
    foreach (var f in provider.Files.Keys.OrderBy(x => x)) Console.WriteLine(f);
    return;
}
if (args[0] == "art") { ArtExport.Run(provider, args[1], args.Length > 2 ? args[2] : null); return; }
if (args[0] == "map") { MapExport.Run(provider, args[1], args[2]); return; }
if (args[0] == "armor") { ArmorExport.Run(provider, args[1]); return; }
if (args[0] == "audio")
{
    // audio <out dir> <regex...>: every matching SoundWave, raw codec bytes as <name>.<format lowercased>
    var outDir = args[1]; int n = 0; var formats = new Dictionary<string, int>();
    foreach (var path in provider.Files.Keys.Where(p => p.EndsWith(".uasset") && args.Skip(2).Any(r => System.Text.RegularExpressions.Regex.IsMatch(p, r))).OrderBy(p => p))
    {
        try
        {
            foreach (var e in provider.LoadPackage(path).GetExports())
            {
                if (e is not CUE4Parse.UE4.Assets.Exports.Sound.USoundWave sw) continue;
                CUE4Parse_Conversion.Sounds.SoundDecoder.Decode(sw, true, out var fmt, out var data);
                if (data == null) { Console.WriteLine($"FAIL nodata {path}"); continue; }
                var o = Path.Combine(outDir, Path.ChangeExtension(path, null) + "." + fmt.ToLowerInvariant());
                Directory.CreateDirectory(Path.GetDirectoryName(o)!); File.WriteAllBytes(o, data); n++;
                formats[fmt] = formats.GetValueOrDefault(fmt) + 1;
            }
        }
        catch (Exception ex) { Console.WriteLine($"FAIL {path}: {ex.Message}"); }
    }
    Console.WriteLine($"audio {n} " + string.Join(" ", formats.Select(kv => $"{kv.Key}={kv.Value}")));
    return;
}
if (args[0] == "tex")
{
    // tex <out dir> <regex...>: every matching Texture2D as PNG (full-size mip)
    CUE4Parse_Conversion.Textures.TextureDecoder.UseAssetRipperTextureDecoder = true;
    var outDir = args[1]; int n = 0;
    foreach (var path in provider.Files.Keys.Where(p => p.EndsWith(".uasset") && args.Skip(2).Any(r => System.Text.RegularExpressions.Regex.IsMatch(p, r))).OrderBy(p => p))
    {
        try
        {
            foreach (var e in provider.LoadPackage(path).GetExports())
            {
                if (e is not CUE4Parse.UE4.Assets.Exports.Texture.UTexture2D tex) continue;
                var c = CUE4Parse_Conversion.Textures.TextureDecoder.Decode(tex);
                if (c == null) { Console.WriteLine($"FAIL nodata {path}"); continue; }
                var bytes = CUE4Parse_Conversion.Textures.TextureEncoder.Encode(c, CUE4Parse_Conversion.Textures.ETextureFormat.Png, false, out var ext);
                var o = Path.Combine(outDir, Path.ChangeExtension(path, null) + "." + ext);
                Directory.CreateDirectory(Path.GetDirectoryName(o)!); File.WriteAllBytes(o, bytes); n++;
                Console.WriteLine($"{o} {c.Width}x{c.Height}");
            }
        }
        catch (Exception ex) { Console.WriteLine($"FAIL {path}: {ex.Message}"); }
    }
    Console.WriteLine($"tex {n}");
    return;
}
if (args[0] == "raw")
{
    var outDir = args[1]; int n = 0;
    foreach (var (path, file) in provider.Files)
    {
        if (!args.Skip(2).Any(p => System.Text.RegularExpressions.Regex.IsMatch(path, p))) continue;
        var o = Path.Combine(outDir, path);
        Directory.CreateDirectory(Path.GetDirectoryName(o)!);
        File.WriteAllBytes(o, file.Read()); n++;
    }
    Console.WriteLine($"raw {n}");
    return;
}
if (args[0] == "json")
{
    var outDir = args[1];
    int ok = 0, bad = 0;
    foreach (var (path, file) in provider.Files.OrderBy(x => x.Key))
    {
        if (!args.Skip(2).Any(p => p.StartsWith("re:") ? System.Text.RegularExpressions.Regex.IsMatch(path, p[3..]) : path.StartsWith(p, StringComparison.OrdinalIgnoreCase))) continue;
        if (!path.EndsWith(".uasset") && !path.EndsWith(".umap")) continue;
        try
        {
            var pkg = provider.LoadPackage(file);
            var exports = pkg.GetExports().ToList();
            var o = Path.Combine(outDir, Path.ChangeExtension(path, ".json"));
            Directory.CreateDirectory(Path.GetDirectoryName(o)!);
            File.WriteAllText(o, JsonConvert.SerializeObject(exports, Formatting.Indented));
            ok++;
        }
        catch (Exception e) { bad++; Console.Error.WriteLine($"FAIL {path}: {e.Message}"); }
    }
    Console.WriteLine($"ok {ok} bad {bad}");
}
