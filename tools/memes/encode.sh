#!/bin/sh
# Frames -> MP4 (720p, for posting) + GIF (smaller, for chats).
#   tools/memes/encode.sh <frame dir> <out basename> [gif width]
set -eu
DIR=$1; OUT=$2; W=${3:-480}
FPS=24
nice -n 19 ffmpeg -y -loglevel error -framerate $FPS -i "$DIR/f_%04d.png" -c:v libx264 -pix_fmt yuv420p -crf 24 -preset slow -movflags +faststart "$OUT.mp4"
nice -n 19 ffmpeg -y -loglevel error -framerate $FPS -i "$DIR/f_%04d.png" \
  -vf "fps=20,scale=$W:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
  -loop 0 "$OUT.gif"
ls -la "$OUT.mp4" "$OUT.gif"
