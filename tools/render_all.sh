#!/bin/sh
# Export every tank's visual mesh + materials, then render hero (35 deg) and profile (90 deg) shots headless.
set -u
cd "$(dirname "$0")/.."
nice -n 19 dotnet tools/extract/bin/Release/net8.0/extract.dll art extract/art 2>&1 | grep -E '^Tyr|FAIL'
mkdir -p extract/renders
for d in extract/art/TyrVehicle*; do
  v=$(basename "$d" | sed 's/TyrVehicle//')
  for a in 35 90; do
    timeout 1800 nice -n 19 blender -b -t 4 -P tools/render_tank.py -- "$d" "extract/renders/${v}_${a}.png" "$a" 1000 2>&1 | grep -E 'rendered|Error|Traceback' | head -2
  done
done
echo ALL DONE
