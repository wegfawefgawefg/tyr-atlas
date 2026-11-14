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
