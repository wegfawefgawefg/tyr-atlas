#!/bin/sh
# Rebuild everything after a game patch: key check, usmap, asset dumps, datasets, armor, combat, site data, maps, art.
#   tools/update_all.sh            data + armor + site data (fast path, most patches)
#   MAPS=1 tools/update_all.sh     also re-export maps and rerun spotting (slow; see note on callouts below)
#   ART=1 tools/update_all.sh      also re-export tank models and re-render them in Blender (slow)
# Stops at the first failing step. Everything runs at nice 19.
set -eu
cd "$(dirname "$0")/.."
export TYR_GAME="${TYR_GAME:-$HOME/.local/share/Steam/steamapps/common/Tyr}"
GAME=$TYR_GAME
EXE=$GAME/Tyr/Binaries/Win64/TyrClient-Win64-Shipping.exe
X="nice -n 19 dotnet tools/extract/bin/Release/net8.0/extract.dll"
P="nice -n 19 python3 -I"
step() { echo "== $*"; }

step "game build"
grep -E '"buildid"|"LastUpdated"' "$GAME/../../appmanifest_2445260.acf"

step "AES key (TYR_AES_KEY or extract/aes.key; a game patch can change it, and the dumps below then fail)"
[ -n "${TYR_AES_KEY:-}" ] || [ -s extract/aes.key ] || { echo "no AES key: set TYR_AES_KEY or write it to extract/aes.key"; exit 1; }

step "usmap from exe reflection"
$P tools/reflect_scan.py extract/reflect_stage1.pkl
$P tools/make_usmap.py extract/reflect_stage1.pkl extract/Tyr.usmap

step "asset dumps"
$X json extract/json Tyr/Content/DataTables Tyr/Content/DataRegistries Tyr/Content/DataAssets Tyr/Content/Blueprints \
  Tyr/Content/UI/Menus Tyr/Content/UI/ViewModels Tyr/Plugins/GameFeatures/Vehicles 're:/Maps/[^/]+/Content/DT_MapInfo' 2>&1 | tail -1

step "talent trees from the CDN"
curl -fsS https://cdn.snapser.com/1d4c-c573-d9pt9gg0/talent-data/talent-trees.json -o "extract/cdn/talent-trees-$(date +%F).json"

step "datasets"
$P tools/build_dataset.py
$P tools/loadouts.py
$X armor extract/armor 2>&1 | grep -v '^tex' | tail -2
$P tools/armor.py
$P tools/combat.py
$P tools/site_data.py

if [ -n "${MAPS:-}" ]; then
  step "maps (actors, geometry, spotting)"
  for m in Fields:TyrMapFields/Content/Maps/Map_Fields Divide:TyrMapDivide/Content/Maps/Map_Divide Dunes:TyrMapDunes/Content/Maps/Map_Dunes_Rework \
           Ravine:TyrMapRavine/Content/Maps/Map_Ravine Scorch:TyrMapScorch/Content/Maps/Map_Scorch WindValley:TyrMapWindValley/Content/Maps/Map_WindValley \
           Ruins:TyrMapRuins/Content/Maps/Map_Ruins Glade:TyrMapGlade/Content/Map_Glade Core:TyrMapCore/Content/Maps/Map_Core_V2; do
    n=${m%%:*}; p=${m#*:}
    timeout 1500 $X map extract/maps/$n Tyr/Plugins/GameFeatures/Maps/$p.umap 2>&1 | grep -E 'umap:' || true
  done
  $P tools/mapdsm.py
  # Dunes, Ruins and Glade are not in rotation, so they stay off the site (old layers kept in site_hidden/maps)
  $P tools/maplos.py Fields Divide Ravine Scorch WindValley Core
  # Callout regions and their hand-picked names live in data/callouts/<Map>/ and are NOT rebuilt here (re-segmenting
  # changes region ids). If a map changed: copy its regions.npy/callouts.json to extract/maps/<Map>/regions_v1.npy and
  # callouts_v1.json, run tools/callouts.py <Map>; tools/callout_names.py <Map> (carries names over; name leftovers by
  # hand), then copy regions.npy, regions.json and callouts.json back into data/callouts/<Map>/.
  for m in Fields Divide Ravine Scorch WindValley Core; do cp data/callouts/$m/* extract/maps/$m/; done
  $P tools/callouts_web.py Fields Divide Ravine Scorch WindValley Core
fi

if [ -n "${ART:-}" ]; then
  step "tank art"
  ./tools/render_all.sh
  $P tools/site_art.py
fi
echo "UPDATE DONE"
