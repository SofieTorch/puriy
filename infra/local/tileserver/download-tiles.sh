#!/bin/bash
# Loads an MBTiles file into the tileserver Docker volume.
# Run this once before starting the tileserver service.
#
# Usage:
#   cd infra/local && ./tileserver/download-tiles.sh <path-to-file.mbtiles>
#
# To get tiles for Bolivia / South America:
#   1. Visit https://data.maptiler.com/downloads/planet/ (free account required)
#   2. Download the South America regional extract as MBTiles
#   3. Run this script with the downloaded file
#
# After loading, start the service: docker compose up -d tileserver
# Style URL for MapLibre: http://localhost:8003/styles/basic-preview/style.json

set -euo pipefail

VOLUME_NAME="cbba_mobility_tileserver_data"
TILES_FILE="tiles.mbtiles"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <path-to-file.mbtiles>"
  echo ""
  echo "Download a regional MBTiles extract from:"
  echo "  https://data.maptiler.com/downloads/planet/"
  exit 1
fi

INPUT_FILE="$1"
if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: file not found: $INPUT_FILE"
  exit 1
fi

docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1 || \
  docker volume create "$VOLUME_NAME"

ABS_DIR="$(cd "$(dirname "$INPUT_FILE")" && pwd)"
BASENAME="$(basename "$INPUT_FILE")"

echo "Copying $INPUT_FILE into Docker volume '$VOLUME_NAME'..."
docker run --rm \
  -v "$VOLUME_NAME:/data" \
  -v "$ABS_DIR:/src:ro" \
  alpine cp "/src/$BASENAME" "/data/$TILES_FILE"

echo "Done. Start the tileserver with: docker compose up -d tileserver"
