// Armor export: skeletal armor meshes (positions, UVs, triangles, dominant bone, sections, bones)
// and the raw BGRA armor/module textures listed in each vehicle's DT_ArmorTextureData.
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.Texture;
using Newtonsoft.Json;

static class ArmorExport
{
    public static void Run(DefaultFileProvider provider, string outDir)
    {
        Directory.CreateDirectory(outDir);
        foreach (var path in provider.Files.Keys.Where(p => System.Text.RegularExpressions.Regex.IsMatch(p,
                     @"^Tyr/Plugins/GameFeatures/Vehicles/[^/]+/Content/(Meshes/SK_[A-Za-z]+_Base_Armor_\d+|Textures/T_[A-Za-z]+_Base_Armor_\d+_(Armor|Module)(_Color_Id)?)\.uasset$")).OrderBy(p => p))
        {
            var objPath = path[..^".uasset".Length];
            var veh = path.Split('/')[4];
            try
            {
                var exports = provider.LoadPackage(path).GetExports().ToList();
                foreach (var ex in exports)
                {
                    if (ex is USkeletalMesh sk) DumpMesh(sk, Path.Combine(outDir, $"{veh}__{sk.Name}.json"));
                    else if (ex is UTexture2D tex) DumpTexture(tex, Path.Combine(outDir, $"{veh}__{tex.Name}"));
                }
            }
            catch (Exception e) { Console.Error.WriteLine($"FAIL {path}: {e.Message}"); }
        }
    }

    static void DumpMesh(USkeletalMesh sk, string file)
    {
        var lod = sk.LODModels![0];
        var vb = lod.VertexBufferGPUSkin;
        var n = vb.GetVertexCount();
        var pos = new float[n * 3]; var nrm = new float[n * 3]; var uv0 = new float[n * 2]; var uv1 = new float[n * 2]; var bone = new int[n];
        var secOf = new int[n];
        for (var s = 0; s < lod.Sections.Length; s++)
        {
            var sec = lod.Sections[s];
            for (var i = 0; i < sec.NumVertices; i++) secOf[sec.BaseVertexIndex + i] = s;
        }
        for (var i = 0; i < n; i++)
        {
            FSkelMeshVertexBase v; float u0, v0, u1 = 0, v1 = 0;
            if (vb.bUseFullPrecisionUVs) { var f = vb.VertsFloat[i]; v = f; u0 = f.UV[0].U; v0 = f.UV[0].V; if (f.UV.Length > 1) { u1 = f.UV[1].U; v1 = f.UV[1].V; } }
            else { var h = vb.VertsHalf[i]; v = h; u0 = (float)h.UV[0].U; v0 = (float)h.UV[0].V; if (h.UV.Length > 1) { u1 = (float)h.UV[1].U; v1 = (float)h.UV[1].V; } }
            if (v.Normal is { Length: 3 } && v.Normal[2] is not null) { nrm[i * 3] = v.Normal[2].X; nrm[i * 3 + 1] = v.Normal[2].Y; nrm[i * 3 + 2] = v.Normal[2].Z; }
            pos[i * 3] = (float)v.Pos.X; pos[i * 3 + 1] = (float)v.Pos.Y; pos[i * 3 + 2] = (float)v.Pos.Z;
            uv0[i * 2] = u0; uv0[i * 2 + 1] = v0; uv1[i * 2] = u1; uv1[i * 2 + 1] = v1;
            var b = 0;
            if (v.Infs != null)
            {
                var best = -1;
                for (var k = 0; k < v.Infs.BoneIndex.Length; k++) if (v.Infs.BoneWeight[k] > best) { best = v.Infs.BoneWeight[k]; b = v.Infs.BoneIndex[k]; }
                var map = lod.Sections[secOf[i]].BoneMap;
                if (map.Length > 0 && b < map.Length) b = map[b];
            }
            bone[i] = b;
        }
        var bones = sk.ReferenceSkeleton.FinalRefBoneInfo.Select((bi, i) => new
        {
            name = bi.Name.Text, parent = bi.ParentIndex,
            t = new[] { sk.ReferenceSkeleton.FinalRefBonePose[i].Translation.X, sk.ReferenceSkeleton.FinalRefBonePose[i].Translation.Y, sk.ReferenceSkeleton.FinalRefBonePose[i].Translation.Z },
            q = new[] { sk.ReferenceSkeleton.FinalRefBonePose[i].Rotation.X, sk.ReferenceSkeleton.FinalRefBonePose[i].Rotation.Y, sk.ReferenceSkeleton.FinalRefBonePose[i].Rotation.Z, sk.ReferenceSkeleton.FinalRefBonePose[i].Rotation.W },
        }).ToArray();
        var o = new
        {
            name = sk.Name, numTexCoords = vb.NumTexCoords, pos, nrm, uv0, uv1, bone, idx = lod.Indices!.Buffer,
            sections = lod.Sections.Select(s => new { mat = s.MaterialIndex, baseIndex = s.BaseIndex, numTris = s.NumTriangles, baseVertex = s.BaseVertexIndex, numVerts = s.NumVertices }),
            materials = sk.SkeletalMaterials.Select(m => new { slot = m.MaterialSlotName.Text, mat = m.Material?.Name }),
            bones,
        };
        File.WriteAllText(file, JsonConvert.SerializeObject(o));
        Console.WriteLine($"mesh {file}: {n} verts, {lod.Indices.Buffer!.Length / 3} tris, {bones.Length} bones, uvsets {vb.NumTexCoords}");
    }

    static void DumpTexture(UTexture2D tex, string file)
    {
        var mip = tex.PlatformData.Mips[0];
        var data = mip.BulkData?.Data;
        if (data == null) { Console.Error.WriteLine($"no data {tex.Name}"); return; }
        File.WriteAllBytes(file + $".{tex.Format}.{mip.SizeX}x{mip.SizeY}.raw", data);
        Console.WriteLine($"tex {tex.Name} {tex.Format} {mip.SizeX}x{mip.SizeY} {data.Length} bytes");
    }
}
