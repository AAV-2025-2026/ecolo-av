#!/usr/bin/env bash
# Run a command with Mesa's software OpenGL (llvmpipe) as EGL's only driver, so Gazebo's
# cameras and lidar render on a Linux computer with no GPU: GitHub's runners, oirp-spss.
#
#   tools/software_gl.sh pixi run sim-check --obstacle
#   tools/software_gl.sh pixi run sim gui:=false
#
# Why: our environment's EGL (libglvnd) has no driver of its own; it uses the computer's.
# With none (no Mesa, no NVIDIA), Ogre can't start, and Gazebo crashes as the world loads
# ("Unable to load Ogre Plugin[.../RenderSystem_GL3Plus]", then a segfault): the car never
# appears. Found 23 Oct, the nightly sim job's first run, and again on oirp-spss.
#
# Mesa comes from conda-forge through `pixi exec`, into pixi's cache, not into pixi.lock:
# Mesa in the default environment would also replace a Linux laptop's own GPU driver.
# Macs render with Metal, and a Linux computer with a GPU has its own driver: there the
# command just runs.
set -euo pipefail
MESA="mesa-llvmpipe==26.2.5"   # Mesa's software renderer, and EGL for it (mesa-libgallium)

if [[ "$(uname -s)" != Linux ]]; then
  exec "$@"
fi
prefix=$(pixi exec --spec "$MESA" -- sh -c 'echo "$CONDA_PREFIX"')
if [[ ! -f "$prefix/lib/libEGL_mesa.so.0" ]]; then
  echo "software_gl.sh: no libEGL_mesa.so.0 in $prefix ($MESA)" >&2
  exit 1
fi
# EGL's driver list, by full path: Mesa's own file names the library without a folder.
vendor=$(mktemp -d "${TMPDIR:-/tmp}/aav-software-gl.XXXXXX")
cat > "$vendor/50_mesa.json" <<EOF
{"file_format_version": "1.0.0", "ICD": {"library_path": "$prefix/lib/libEGL_mesa.so.0"}}
EOF
export __EGL_VENDOR_LIBRARY_FILENAMES="$vendor/50_mesa.json"
echo "software_gl.sh: EGL renders with Mesa llvmpipe ($prefix)" >&2
exec "$@"
