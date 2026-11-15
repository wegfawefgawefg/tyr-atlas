# Tyr Tank Atlas

Unofficial data site for the tank game Tyr (Stoke Games, UE5, Steam app 2445260), built from the game's own files.
Live at https://tyr-atlas.pages.dev (Cloudflare Pages project `tyr-atlas`).

Data is from game build 26309825 (2026-11-10). Status, findings and open questions are in `docs/plan.md`;
how map callouts were made is in `docs/callouts.md`.

## Layout

- `site/` the static site (plain HTML/JS, no build step). `./serve.sh` serves it at http://127.0.0.1:8740/.
  `site/armor_data.js` is generated and not committed (7 MB): run `tools/armor.py` before serving or deploying.
- `site_hidden/maps/` spotting layers for Dunes, Ruins and Glade, which ship in the files but were not in rotation.
- `data/` processed datasets (stats, loadouts, armor, combat) that the site data is built from.
  `data/callouts/<Map>/` holds the callout regions and their hand-picked names (see `docs/callouts.md`).
- `tools/` the extractor (`tools/extract`, C#), dataset builders (Python), line-of-sight sweep (`tools/los`, Rust),
  Blender renders, and the update and deploy scripts.
- `extract/` (not committed) raw asset dumps, map geometry, renders. Rebuilt by the steps below.
- `third_party/` (not committed) CUE4Parse and Oodle. Rebuilt by the steps below.

## Rebuilding from scratch

Needs: Tyr installed through Steam (set `TYR_GAME` to its `steamapps/common/Tyr` folder; the default is
`~/.local/share/Steam/steamapps/common/Tyr`), .NET 8 SDK, Python 3 with
numpy, scipy, Pillow and cryptography, Rust (cargo), Blender 4.0 for the renders, and objdump for the reflection scan.

1. CUE4Parse: `git clone https://github.com/FabianFG/CUE4Parse third_party/CUE4Parse-net8`, then
   `git -C third_party/CUE4Parse-net8 checkout 75983dc51608e0285e5d9ea5f28133e6a4951ccf` and
   `git -C third_party/CUE4Parse-net8 apply ../../tools/extract/cue4parse-net8.patch`
   (the patch keeps static mesh LODs when the newer Nanite/RT fields fail to parse).
2. Oodle: put `liboodle-data-shared.so` in `third_party/oodle/lib/` (from the `gcc.zip` release of
   WorkingRobot/OodleUE on GitHub).
3. Build the extractor: `dotnet build -c Release tools/extract`, and the sweep: `cargo build --release --manifest-path tools/los/Cargo.toml`.
4. `tools/update_all.sh` rebuilds the usmap, dumps, datasets, armor, combat and site data.
   `MAPS=1` also re-exports the maps and reruns spotting (slow). `ART=1` also re-renders the tanks in Blender (slow).

The game's paks are encrypted. `tools/find_aes.py` finds the AES key in your installed game exe, and `update_all.sh`
runs it first and writes the key to `extract/aes.key` (not committed), so a patch that changes the key is picked up
automatically. To run the extractor by hand, set `TYR_AES_KEY` or run that step first.

## Deploying

`tools/deploy.sh` uploads `site/` to the Cloudflare Pages project (needs `npx wrangler login`). It is a classic Pages
project: do not use `wrangler deploy`, which makes a Worker on the account's workers.dev subdomain instead.
