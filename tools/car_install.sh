#!/usr/bin/env bash
# Install our Jazzy stack on a car computer from the USB kit (tools/car_kit.sh), offline.
#
# usage: bash /media/<you>/<stick>/car-kit/car_install.sh [--dry-run] [--all] [--no-verify]
#
#   --dry-run    only the checks: says what it would do, changes nothing
#   --all        also build the HUD (aav_hud_raylib) and bench mode's spine_sim
#   --no-verify  skip the checksums of the kit's files (they take a minute from a stick)
#
# Run it as your normal user, on the car computer itself (an Orin or a Pi, 64-bit).
# Everything goes in one folder, ~/aav-jazzy. To undo it all: rm -rf ~/aav-jazzy
#
# It never uses sudo, and never touches /opt/ros (the 2025-26 Humble), ~/.bashrc, ~/.cargo,
# or a system service. Run it again at any time: it skips what is already done, and a new
# kit updates the code, and the environment only if that changed.
#
# Portable: bash 3.2, no GNU-only flags (it also runs its checks on a Mac, and refuses).
set -euo pipefail

KIT=$(cd "$(dirname "$0")" && pwd)
PREFIX="$HOME/aav-jazzy"
PACK=aav-jazzy-linux-aarch64.tar
NEED_GB=13          # the environment unpacked (9.1 GiB, measured) + the build + room
NEED_GB_AGAIN=3     # when the environment is already unpacked
# Built only with --all: the HUD's screen is DASH-UI's, and spine_sim is bench mode's.
SKIP_PACKAGES="aav_hud_raylib aav_spine_sim"

dry=0 all=0 verify=1
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry=1 ;;
    --all) all=1 ;;
    --no-verify) verify=0 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

problems=0
ok()   { printf '  OK    %-14s %s\n' "$1" "$2"; }
bad()  { printf '  STOP  %-14s %s\n' "$1" "$2"; problems=$((problems + 1)); }
note() { printf '  NOTE  %-14s %s\n' "$1" "$2"; }
step() { printf '\n== %s\n' "$*"; }

sha256() {   # sha256 of a file, on Linux or a Mac
  if command -v sha256sum >/dev/null; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# The pack's checksum, as the kit recorded it: it tells a new environment from the old one.
pack_id() { awk -v f="$PACK" '$2 == f {print $1}' "$KIT/SHA256SUMS" 2>/dev/null; }

step "Checks (nothing changes yet)"

os=$(uname -s) arch=$(uname -m)
if [[ "$os" == Linux ]]; then ok "system" "Linux"; else bad "system" "$os: this is for the car's Linux computers"; fi
if [[ "$arch" == aarch64 ]]; then
  ok "processor" "aarch64"
else
  bad "processor" "$arch: the kit is for aarch64 (64-bit ARM). A Pi on a 32-bit OS says armv7l"
fi
if [[ "$(id -u)" == 0 ]]; then bad "user" "root: run it as your normal user, without sudo"; else ok "user" "$(id -un)"; fi

if [[ "$os" == Linux ]]; then
  glibc=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
  major=${glibc%%.*} minor=${glibc#*.}; minor=${minor%%.*}
  if [[ -n "$glibc" ]] && (( major > 2 || (major == 2 && minor >= 28) )); then
    ok "glibc" "$glibc (needs 2.28 or newer)"
  else
    bad "glibc" "${glibc:-unknown}: needs 2.28 or newer (Ubuntu 20.04 and later have it)"
  fi
fi

missing=""
for f in "$PACK" aav.bundle aav-src.tar.gz rust-crates.tar.gz bin/pixi bin/pixi-unpack SHA256SUMS; do
  [[ -f "$KIT/$f" ]] || missing="$missing $f"
done
if [[ -z "$missing" ]]; then ok "kit" "$KIT"; else bad "kit" "missing from $KIT:$missing"; fi

if [[ $verify == 1 && -z "$missing" ]]; then
  bad_sums=""
  while read -r sum file; do
    [[ -f "$KIT/$file" ]] || continue
    [[ "$(sha256 "$KIT/$file")" == "$sum" ]] || bad_sums="$bad_sums $file"
  done < "$KIT/SHA256SUMS"
  if [[ -z "$bad_sums" ]]; then ok "checksums" "every file copied whole"; else bad "checksums" "damaged:$bad_sums (copy them again)"; fi
fi

# Already unpacked from this same kit? Then little disk is needed.
env_done=0
if [[ -f "$PREFIX/env/.aav-kit" && "$(cat "$PREFIX/env/.aav-kit")" == "$(pack_id)" ]]; then env_done=1; fi
need=$NEED_GB
if [[ $env_done == 1 ]]; then need=$NEED_GB_AGAIN; fi
where=$PREFIX
if [[ ! -d "$where" ]]; then where=$HOME; fi
free_kb=$(df -Pk "$where" | awk 'NR == 2 {print $4}')
free_gb=$((free_kb / 1024 / 1024))
if (( free_gb >= need )); then ok "disk" "$free_gb GB free in $where (needs $need)"; else bad "disk" "$free_gb GB free in $where, needs $need"; fi

if command -v git >/dev/null; then ok "git" "$(git --version)"; else note "git" "none: the code comes from aav-src.tar.gz instead"; fi

workers=4 mem_gb=0
if [[ -r /proc/meminfo ]]; then
  mem_gb=$(awk '/^MemTotal/ {print int($2 / 1024 / 1024 + 0.5)}' /proc/meminfo)
  cpus=$(getconf _NPROCESSORS_ONLN)
  workers=$cpus
  if (( mem_gb < 6 )); then workers=1; fi   # Rust's linker needs 1-2 GB each: a 4 GB Pi builds one at a time
  ok "memory" "$mem_gb GB, $cpus cores: builds $workers package(s) at a time"
fi

for d in /opt/ros/*; do
  if [[ -d "$d" ]]; then note "left alone" "$d"; fi
done

if (( problems > 0 )); then
  printf '\n%d check(s) failed: nothing was changed.\n' "$problems"
  exit 1
fi
if [[ $dry == 1 ]]; then
  printf '\nDry run: every check passed. Without --dry-run it would fill %s:\n' "$PREFIX"
  printf '  env/ (Jazzy, %s), aav/ (the code, built), cargo/ (Rust crates), bin/, aav.sh\n' \
    "$( [[ $env_done == 1 ]] && echo "already there" || echo "unpacked")"
  exit 0
fi

T0=$(date +%s)
mkdir -p "$PREFIX/bin" "$PREFIX/tmp"
cp "$KIT/bin/pixi" "$KIT/bin/pixi-unpack" "$PREFIX/bin/"
chmod +x "$PREFIX/bin/pixi" "$PREFIX/bin/pixi-unpack"

step "1. ROS 2 Jazzy into $PREFIX/env"
if [[ $env_done == 1 ]]; then
  echo "already unpacked from this kit"
else
  # The prefix is written into the files as they unpack, so it unpacks in place. TMPDIR on
  # the same disk: pixi-unpack extracts there first, and can then hard-link, not copy.
  rm -rf "$PREFIX/env"
  t=$(date +%s)
  TMPDIR="$PREFIX/tmp" "$PREFIX/bin/pixi-unpack" -o "$PREFIX" -e env "$KIT/$PACK"
  pack_id > "$PREFIX/env/.aav-kit"
  echo "took $(( $(date +%s) - t )) s; $(du -sh "$PREFIX/env" | awk '{print $1}') on disk"
fi
rm -rf "$PREFIX/tmp"

step "2. The code into $PREFIX/aav"
if [[ -d "$PREFIX/aav/.git" ]] && command -v git >/dev/null; then
  git -C "$PREFIX/aav" fetch -q "$KIT/aav.bundle" HEAD
  if git -C "$PREFIX/aav" merge -q --ff-only FETCH_HEAD; then
    echo "updated to $(git -C "$PREFIX/aav" log --oneline -1)"
  else
    echo "WARNING: $PREFIX/aav has its own changes; left as it is" >&2
  fi
elif [[ -d "$PREFIX/aav" ]]; then
  echo "already there (no git here, so it isn't updated: delete $PREFIX/aav to replace it)"
elif command -v git >/dev/null; then
  git clone -q "$KIT/aav.bundle" "$PREFIX/aav"
  # The stick won't be there later: point origin at GitHub, for when there is internet.
  git -C "$PREFIX/aav" remote set-url origin git@github.com:zander1976/aav.git
  echo "cloned $(git -C "$PREFIX/aav" log --oneline -1)"
else
  mkdir -p "$PREFIX/aav"
  tar -xzf "$KIT/aav-src.tar.gz" -C "$PREFIX/aav"
  echo "unpacked from aav-src.tar.gz (no git here)"
fi
# Pixi uses the unpacked environment as this project's own: pixi run --as-is works offline.
mkdir -p "$PREFIX/aav/.pixi/envs"
ln -sfn "$PREFIX/env" "$PREFIX/aav/.pixi/envs/default"
if [[ -d "$KIT/models" ]]; then
  mkdir -p "$PREFIX/aav/models"
  for m in "$KIT"/models/*; do
    if [[ -e "$m" && ! -e "$PREFIX/aav/models/$(basename "$m")" ]]; then
      cp -R "$m" "$PREFIX/aav/models/"
    fi
  done
fi

step "3. Rust crates into $PREFIX/cargo (so cargo needs no internet)"
crates_id=$(awk '$2 == "rust-crates.tar.gz" {print $1}' "$KIT/SHA256SUMS")
if [[ -f "$PREFIX/cargo/.aav-kit" && "$(cat "$PREFIX/cargo/.aav-kit")" == "$crates_id" ]]; then
  echo "already there"
else
  rm -rf "$PREFIX/cargo"
  mkdir -p "$PREFIX/cargo"
  tar -xzf "$KIT/rust-crates.tar.gz" -C "$PREFIX/cargo"
  cat > "$PREFIX/cargo/config.toml" <<EOF
# Written by car_install.sh: crates come from the kit, never from crates.io.
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "$PREFIX/cargo/vendor"

[net]
offline = true
EOF
  echo "$crates_id" > "$PREFIX/cargo/.aav-kit"
  echo "$(ls "$PREFIX/cargo/vendor" | wc -l | tr -d ' ') crates"
fi

step "4. $PREFIX/aav.sh: runs a command inside our Jazzy"
cat > "$PREFIX/aav.sh" <<EOF
#!/usr/bin/env bash
# Written by car_install.sh. Runs a pixi task or a command inside our Jazzy, apart from the
# car's Humble:  $PREFIX/aav.sh car orin    or    $PREFIX/aav.sh ros2 topic list
# Delete $PREFIX to undo everything.
P="$PREFIX"
# A Humble terminal (its setup.bash, sourced in ~/.bashrc) would leak into ours: clear it.
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH \\
  ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION ROS_PACKAGE_PATH ROS_ETC_DIR ROS_ROOT \\
  ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL \\
  VIRTUAL_ENV PIXI_PROJECT_ROOT PIXI_ENVIRONMENT_NAME
# Our own ROS network: the 2025-26 software uses domain 0 or 10, so on 42 they never meet.
# A Mac that wants to see this computer sets the same: export ROS_DOMAIN_ID=42
export ROS_DOMAIN_ID=42
# Pixi and cargo keep their files in \$P, and never go online.
export PIXI_HOME="\$P/pixi-home" PIXI_CACHE_DIR="\$P/pixi-cache" PIXI_FROZEN=true
export CARGO_HOME="\$P/cargo" CARGO_NET_OFFLINE=true
export AAV_KIT_SHELL=1
cd "\$P/aav"
exec "\$P/bin/pixi" run --as-is "\$@"
EOF
chmod +x "$PREFIX/aav.sh"
echo "done"

step "5. Build our packages (colcon, offline)"
skip=""
if [[ $all == 0 ]]; then skip="--packages-skip $SKIP_PACKAGES"; fi
t=$(date +%s)
build_ok=1
# shellcheck disable=SC2086  # $skip is a list of words on purpose
CARGO_BUILD_JOBS=$(( workers > 2 ? workers : 2 )) \
  "$PREFIX/aav.sh" colcon build --symlink-install --parallel-workers "$workers" $skip \
  2>&1 | tee "$PREFIX/build.log" || build_ok=0   # pipefail: colcon's status
echo "the build took $(( $(date +%s) - t )) s (log: $PREFIX/build.log)"

step "Finished in $(( $(date +%s) - T0 )) s; $(du -sh "$PREFIX" | awk '{print $1}') in $PREFIX"
if [[ $build_ok == 0 ]]; then
  echo "WARNING: some packages didn't build: see $PREFIX/build.log. The rest still run."
fi
cat <<EOF

Next (docs/car-install.md):
  $PREFIX/aav.sh tools/car_listen.sh      read-only: the devices, and who can open them
  $PREFIX/aav.sh ros2 topic list          our domain (42): empty until we start something
  $PREFIX/aav.sh car motor_pi             our stack (or: car orin). Only once the
                                          2025-26 software is stopped, and the team agrees
Undo everything:  rm -rf $PREFIX
EOF
