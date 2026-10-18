#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ffmpeg -hide_banner -loglevel error -f lavfi -i 'testsrc2=size=640x360:rate=12' \
  -vf "drawtext=text='SENTINELA AI - VIDEO SINTETICO':fontsize=22:fontcolor=white:box=1:boxcolor=black@0.8:x=(w-tw)/2:y=20" \
  -t 12 -an -c:v libx264 -pix_fmt yuv420p -preset fast -crf 30 -movflags +faststart -y sentinela/media/demo.mp4
