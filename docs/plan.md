# Tyr analysis

Goal: stats site (and later a video) for Tyr (Stoke Games, UE5 tank shooter, Steam 2445260).

1. Builds: Pareto fronts per tank and across tanks, plus notable/wacky builds found by interaction analysis.
2. Armor by facing, effective HP, 1v1 matchups, peeking duels.
3. Map scans: hidden spots, sightlines, holdable positions (replays in the Proton prefix can help).
4. CS-style callout names for map zones.

## Data pipeline

- `tools/find_aes3.py` finds the pak AES key in the exe (stack-built key).
- `tools/reflect_scan.py` + `tools/make_usmap.py` rebuild a .usmap from UHT reflection tables in the
  shipping exe (no game run needed). Output `extract/Tyr.usmap`.
- `tools/extract` (C#, CUE4Parse net8 snapshot in third_party) dumps assets to `extract/json`.
- Talent tree layout is not in the client: it comes from
  `https://cdn.snapser.com/1d4c-c573-d9pt9gg0/talent-data/talent-trees.json` (same file the client fetches).
  Saved as `extract/cdn/talent-trees-<date>.json`.
- `tools/build_dataset.py` -> `data/tyr.json` (tanks, trees, talents, components, ammo, effect summaries).

After a game patch: rerun find_aes3 (key may change), reflect_scan, make_usmap, extractor, refetch trees, build_dataset.

## Mechanics notes

- Talent values are cumulative per level (TalentPointValues[k-1] at k points), applied via GEs with TyrTalentMagCalculation.
- GAS aggregation: ((Base + sum Add) * (1 + sum(Mult-1)) / (1 + sum(Div-1))) * prod(MultiplyCompound). Multiplicitive mods add their bonuses.
- Trees: 7 tiers, 5 points spent to unlock each next tier, prerequisites per node, 2 keystones in tier 6.
- Loadout: 3 component slots (from logs), 4 ammo slots.

## Open

- Total talent point budget per tank (server-side inventory item Gameplay.Item.Talent.Point). Ask owner / treat as parameter.
- Whether only one keystone can be taken.
- Event-triggered effects need uptime assumptions; mark them conditional.

## Tree rules (from VM_TechTree / VM_TechTree_Node bytecode, tools/kismet_pp.py)

- Tier t unlocks when points in tiers < t >= 5*t (MinPointsToUnlock = RequiredMinTierPoints * tier).
- Prerequisite nodes must be maxed (AreRequiredNodesActivated -> HasMaxPoints).
- No keystone exclusivity in the client UI.
- Owner thinks the budget is 20 points. At 20, tier 4 needs all 20 spent above it, so builds live in tiers 0-3
  and keystones (tier 6, need 30 spent) are unreachable. Valid exact-20 talent builds: 51k (Valor) to 7.5M (Kestrel),
  37M total (tools/count_builds.py).

## Website

- `site/index.html` + `site/data.js` (built by `tools/site_data.py`). Plain HTML/SVG, no build step.
- Serve locally with `./serve.sh` -> http://127.0.0.1:8740/. Not published anywhere (owner: no artifact, local hosting).
- Sections: per-stat strips (base / 31-point core mode), any-vs-any scatter with Pareto frontier staircase,
  PCA tank map with loadings, similarity heatmap + nearest neighbours, talent uplift dumbbells, sortable table.

## Findings so far

- Core stats (DPS, alpha, HP, speed) are free at 31 points on every tank but Fuse; real choices are keystone,
  components, ammo, leftover points. Helio has no speed or reload talents, so its core needs only 10 points.
- Designer ratings in DT_TankData: Durability ~ HP (rank corr +0.96), Scouting ~ camo (+0.91),
  Firepower vs DPS is -0.62 (rating follows per-shot damage +0.51; Alecto has top DPS but rating 5).
- PCA: PC1 (29%) light/fast/camo vs heavy/HP/detection; PC2 (14%) turreted vs turretless hover tanks.

## Armor (tools/armor.py)

- Armor lives on `SK_<Veh>_Base_Armor_01` (armor-only skeletal mesh) + `T_<Veh>_Base_Armor_01_Armor` (BGRA, one pixel
  per triangle: B = thickness mm, A = plate id; a few stray pixels on wheel triangles of Seeker/Recall/Vtol/Blink are dropped).
  `_Module` texture: A = 0 none, 1-2 treads (track you, no HP damage), 3+ crit modules. `_Color_Id` 1024 DXT5 maps are the viewer art.
- Penetration rule from TyrArmorRuntimeSettings (constructor 0x145fa9ea0 + DefaultGame.ini): auto-bounce over 80 deg,
  overmatch at pen >= 4x thickness, eff = t/cos(angle), fifty-fifty band 1.25 (direction of the band assumed: pen < eff <= 1.25 pen).
  Effective-armor formula confirmed against an in-game viewer readout (21 mm @ 62.98 deg = 46.2 mm).
- Ray casting: orthographic z-buffer per direction, 6 cm rays, 72 azimuths x 8 elevations; hits assumed uniform over silhouette.
- Site: armor roses, hemisphere map, x-ray views, frontal TTK duel matrix (front / 30 deg angled); armor + size stats feed
  the strips, scatter, correlations and PCA (front armor now loads -0.94 on PC1 next to HP).

## Combat (tools/combat.py)

- Soft armor normals: BP_BaseTank sets bUseSoftArmorNormals = true, so impact angles use barycentric-interpolated
  vertex normals (exported TangentZ). Armor meshes are hard-edged, so this differs from face normals by ~0.3 deg median, ~4 deg p90.
- Shots to kill on core builds; expected shots = hits / damage chance (even spread over the silhouette, or aimed).
- Aimed model is unit-free: best aim point on the Gaussian-blurred damage map for spread sigma 0.1-2 m (dispersion units
  in the native ShellFiringComponent are not recovered yet, so no distance mapping).
- Breakpoint levers: Duplicator +5, Shell Stabilizer +10, Shell Charger +25.5 (3 stacks), Momentum Imparter +30 (>40 kph),
  Hot Chamber x1.12, ammo x1.1/1.2/1.3; defender levers Bulkheads x1.085, Mobility Surger +100.
- Hull-down: front view above (gun height - 25 cm). Ammo modifiers from DT_AmmunitionUIData (AP x1.35 pen is hidden/non-selectable).
- Turret yaw: turret-chain vertices rotated about jnt_turret, front view, face normals for rotated turrets.
- Ram: kinetic energy at top speed (collision damage formula is native TyrCollisionDamageExecution, not recovered).

## Crits (from BPC_Module*Component + GE_Module_* + module textures)

- Module texture B channel = module row: DT_ModuleData row suffix = trunc(B/255*1e5). Types: Track (no HP damage), Bonus
  (+50% damage on that hit), Fire (20/s until repaired; repair 8/4/2/0 s within a 10 s window), Engine (halves speed/accel/strafe,
  steering x0.75), Gun, Turret, Ability. All need penetration.
- Combat page: shots to kill, breakpoints, aimed weak spots + crits, hull-down, ammo, turret yaw, tread area, size vs camo, ram.

## Maps (started)

- `extract.dll map <out> <umap>`: landscape heightmaps (BGRA, h = ((R<<8)|G - 32768)/128 * zscale), every mesh placement with
  world transform (level instances followed), gameplay actors (capture/heal/ammo/energy zones, spawns, no-go, bushes), coarse LOD
  geometry. Local CUE4Parse patch: FStaticMeshRenderData keeps LODs when newer Nanite/RT fields fail to parse.
- `tools/mapdsm.py`: 1 m DTM + DSM (structures >= 1.2 m tall) + bush mask per map. Next: Rust viewshed tool, exposure /
  coverage / hull-down crest maps, zone coverage, callout naming.
- Callouts: `tools/callouts.py` (regions) -> names in `extract/maps/<Map>/callouts.json` (docs/callouts.md; carry names over
  after re-segmenting with `tools/callout_names.py`) -> `tools/callouts_web.py` writes site/maps/<map>/callouts.json +
  regions.png (borders between named regions; labels by their zone or spawn). Maps page has a Callouts toggle.

## Spotting rules (game files) and the map model

- BP_TyrGameMode: MaxCamoValue 80, MaxBushCamoValue 40, GunFireCamoAddition -15, GunFireCamoScalar -0.4, OutsideVisionRadiusFactor -15.
- BP_VisionBlocker (bush): CamoPercentageIncreaseAmount 40, CollisionBounds sphere 325 cm (vision overlap), SeeThroughBounds 1500 cm.
  Smoke cloud: +50 camo. GE_GunDetection on firing: camo AddFinal (set by caller) + BushSpottingTime 0.1.
- Web guides agree (tyrhq advanced spotting: +40 directional bush camo; spotted 7 s; LoS any part to any part; 400 m).
- tools/los: spotted if LoS to any part of a 2.5 m column and distance <= 400 * (1 - min(80, camo + 40 if a bush is on the
  line and the spotter is > 15 m from it)/100). Computed for camo 0/25/40. Result: open-ground spotting is symmetric; the edge is bushes + camo.
- Live rotation (from match travel in owner's logs): Core, Divide, Fields, Ravine, Scorch, Wind Valley. Dunes, Ruins, Glade never seen.
