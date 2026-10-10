#!/usr/bin/env bash
# Download the stock YOLO model into models/. Model files stay out of git.
#
# usage: tools/get_models.sh      (or: pixi run get-models)
#
# YOLO11 nano: 5.6 MB. It knows 80 everyday things, "stop sign" among them (the COCO
# dataset). Licence: AGPL-3.0, from Ultralytics.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
file=models/yolo11n.pt
url=https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
sum=0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1
if [[ ! -f $file ]]; then
  curl -fL --retry 3 -o "$file.part" "$url"
  mv "$file.part" "$file"
fi
if command -v sha256sum >/dev/null; then
  got=$(sha256sum "$file" | cut -d' ' -f1)
else
  got=$(shasum -a 256 "$file" | cut -d' ' -f1)
fi
if [[ $got != "$sum" ]]; then
  echo "$file isn't the expected download: delete it and run this again" >&2
  exit 1
fi
echo "$file: ok"
