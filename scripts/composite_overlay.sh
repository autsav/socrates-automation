#!/bin/bash
# scripts/composite_overlay.sh
# Composite MPT base.mp4 + HF overlay.mp4 → final.mp4 (IG-compatible, no alpha)
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <base.mp4> <overlay.mp4> <final.mp4>" >&2
  exit 1
fi

BASE="$1"
OVERLAY="$2"
FINAL="$3"

if [[ ! -f "$BASE" ]]; then
  echo "❌ Base video not found: $BASE" >&2
  exit 2
fi

if [[ ! -f "$OVERLAY" ]]; then
  echo "❌ Overlay video not found: $OVERLAY" >&2
  exit 2
fi

mkdir -p "$(dirname "$FINAL")"

echo "🎬 Compositing base + overlay → $FINAL"
ffmpeg -y \
  -i "$BASE" \
  -i "$OVERLAY" \
  -filter_complex "[1]format=yuva420p[ovl]; [0][ovl]overlay=0:0:format=auto,format=yuv420p" \
  -c:v libx264 -crf 23 -preset fast -movflags +faststart \
  "$FINAL"

echo "✅ Composite saved: $FINAL"