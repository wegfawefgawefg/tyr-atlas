# Map callouts

Each map is cut into regions (`extract/maps/<Map>/regions.json`, drawn in
`extract/maps/png/<map>_regions.png`). `extract/maps/<Map>/callouts.json` gives
every region one short name to say in voice chat, plus a one-line reason.

## How names are picked

- A name is something you can see from the spot: a landmark, a terrain shape,
  or the zone that is there. One or two words, 12 characters at most.
- Names are unique within a map and chosen not to sound alike
  (no "Ridge" next to "Bridge", no "Rock" next to "Block").
- A is the team that spawns at the south or west end, B the north or east end
  (same rule the region tool uses for its `side` field).
- A/B prefixes are only for zones and the ground right next to them.
  Mirrored spots further out get different landmark names (Ship vs Spires).
- Zones that belong to neither team get a compass prefix (West Ammo, East Energy).

## Shared words

| Word | Meaning on every map |
|---|---|
| A Cap / B Cap | capture zone on that team's side |
| A Heal / B Heal | heal zone on that team's side |
| A Ammo / B Ammo, West/East/North Ammo | ammo zone, sided or neutral |
| Energy | energy zone (West/East Energy when there are two) |
| Mid | the central region (on Scorch it also holds the energy zone) |
| A Yard / B Yard | open ground right beside a cap |
| A Wall / B Wall, A Bridge / B Bridge, A Gully / B Gully | identical mirrored approach to each cap |
| Thicket | the densest bush cluster on the map |
| Ruins | broken walls or towers |
| Corner, Shelf, Basin, Dip | edge regions with no landmark, named by shape |

## Notes

- On Divide, Ravine and WindValley the capture zone is inside the spawn dome,
  so "A Cap" is also where A spawns.
- Core's centre is a sunken crater: "Core" is its north-east quarter around the
  cross-shaped structure, West Ammo and Energy share the rest of the crater floor.
- After re-segmentation, tools/callout_names.py carries names over by overlap
  (callouts_v1.json + regions_v1.npy); regions it can't match are named by hand
  (source "hand" in callouts.json).
