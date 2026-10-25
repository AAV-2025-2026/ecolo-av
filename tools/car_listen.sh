#!/usr/bin/env bash
# The read-only first step on a car computer: what devices are here, and could each of our
# drivers open its own? Starts no driver, opens no device, changes nothing.
#
# usage: ~/aav-jazzy/aav.sh tools/car_listen.sh     (after tools/car_install.sh)
#        bash tools/car_listen.sh                    (anywhere: the device part only)
#
# Why it never opens a port: opening a USB serial port can pulse its DTR line, and that
# resets an Arduino or an ESP32. So it only reads permissions, sysfs and /proc.
#
# ROS_DOMAIN_ID=42: a domain is a separate ROS network on the same wires (its own UDP
# ports, 7400 + 250 x the number). The 2025-26 Humble software uses 0 or 10, so on 42 our
# nodes and theirs never find each other. docs/car-install.md says more.
#
# Portable: bash 3.2, no GNU-only flags. Written for Linux; on a Mac it lists less.

AAV_DOMAIN=42
PREFIX="${AAV_PREFIX:-$HOME/aav-jazzy}"

# Inside our environment? If not, and the kit is installed, run again inside it.
if [[ "${ROS_DISTRO:-}" != "jazzy" && -z "${AAV_KIT_SHELL:-}" && -x "$PREFIX/aav.sh" ]]; then
  exec "$PREFIX/aav.sh" bash "$(cd "$(dirname "$0")" && pwd)/car_listen.sh" "$@"
fi
export ROS_DOMAIN_ID=$AAV_DOMAIN
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST   # the ROS check below stays on this computer
unset ROS_STATIC_PEERS

me=$(id -un)
my_groups=" $(id -nG) "

say() { printf '%s\n' "$*"; }
header() { printf '\n== %s\n' "$*"; }

in_group() { [[ "$my_groups" == *" $1 "* ]]; }

# The group that owns a file (ls works the same on Linux and macOS).
group_of() { ls -lLd "$1" 2>/dev/null | awk '{print $4}'; }

# USB vendor:product and interface number of a tty or video device, from sysfs ("" if none).
usb_ids() {
  local dir iface=""
  dir=$(cd "/sys/class/$1/$2/device" 2>/dev/null && pwd -P) || return 0
  local i=0
  while [[ -n "$dir" && "$dir" != "/" && $i -lt 6 ]]; do
    [[ -z "$iface" && -f "$dir/bInterfaceNumber" ]] && iface=$(cat "$dir/bInterfaceNumber")
    if [[ -f "$dir/idVendor" ]]; then
      printf '%s:%s %s\n' "$(cat "$dir/idVendor")" "$(cat "$dir/idProduct")" "${iface:-??}"
      return 0
    fi
    dir=$(dirname "$dir")
    i=$((i + 1))
  done
}

# The processes (of this user; others need sudo) holding a device open: "name(pid) ...".
holders() {
  local target fd pid out=""
  [[ -d /proc ]] || { echo "?"; return; }
  target=$(readlink -f "$1" 2>/dev/null || echo "$1")
  for fd in /proc/[0-9]*/fd/*; do
    [[ "$(readlink "$fd" 2>/dev/null)" == "$target" ]] || continue
    pid=${fd#/proc/}; pid=${pid%%/*}
    [[ "$out" == *"($pid)"* ]] || out="$out $(cat "/proc/$pid/comm" 2>/dev/null)($pid)"
  done
  echo "${out# }"
}

# Can this user open the device for reading and writing? Says why not.
access() {
  local dev=$1 grp
  if [[ -r "$dev" && -w "$dev" ]]; then echo "yes"; return; fi
  grp=$(group_of "$dev")
  if in_group "$grp"; then
    echo "no: in group $grp, but log out and in again"
  else
    echo "no: needs group $grp"
  fi
}

header "Who and where"
say "user: $me    groups:$my_groups"
say "computer: $(uname -n), $(uname -s) $(uname -m)"
[[ -f /etc/os-release ]] && say "os: $(. /etc/os-release && echo "$PRETTY_NAME")"
say "ROS_DOMAIN_ID=$ROS_DOMAIN_ID (ours; the 2025-26 software uses 0 or 10)"

header "Devices present"
found=0
for dev in /dev/ttyACM* /dev/ttyUSB* /dev/ttyAMA* /dev/ttyTHS* /dev/serial0 /dev/serial1 \
           /dev/video* /dev/aav/* /dev/cu.usb*; do
  [[ -e "$dev" ]] || continue
  found=1
  name=$(basename "$dev")
  ids=""
  case "$name" in
    tty*) ids=$(usb_ids tty "$name") ;;
    video*) ids=$(usb_ids video4linux "$name") ;;
  esac
  printf '  %-22s %-12s group %-8s %s\n' "$dev" "${ids%% *}" "$(group_of "$dev")" \
    "$( [[ -L "$dev" ]] && echo "-> $(readlink "$dev")")"
done
[[ $found == 1 ]] || say "  (no serial or video devices)"
if [[ -d /dev/serial/by-id ]]; then
  say "  by id:"
  ls -l /dev/serial/by-id | awk 'NR > 1 {print "    " $9 " -> " $11}'
fi
cans=""
[[ -d /sys/class/net ]] && for n in /sys/class/net/*; do
  [[ "$(cat "$n/type" 2>/dev/null)" == "280" ]] && cans="$cans $(basename "$n")($(cat "$n/operstate"))"
done
say "  CAN interfaces:${cans:- none}"

# Our drivers, what each wants, and the device it would get. The vendor:product IDs come
# from tools/udev/99-aav.rules, which isn't installed on the car yet (that needs sudo), so
# /dev/aav/* won't exist: the "Found" column then shows the raw device that matches.
# part | wants | usb id (vendor:product[:interface]) or "" | group it usually needs
PARTS="imu (aav_imu_yahboom)|/dev/aav/imu|1a86:7523|dialout
gps (ublox_gps)|/dev/aav/gps|1546:|dialout
radar commands (ti_ros2_driver)|/dev/aav/radar_cmd|10c4:ea70:00|dialout
radar data (ti_ros2_driver)|/dev/aav/radar_data|10c4:ea70:01|dialout
battery (battery_monitor)|/dev/aav/battery|0403:6015|dialout
ESP32 UART (legacy_uart_bridge)|/dev/ttyAMA0||dialout
front camera (usb_cam)|/dev/aav/camera_left|video|video"

# The first tty or video device whose USB IDs match ("" if none).
match() {
  local want=$1 dev name ids vp iface
  for dev in /dev/ttyUSB* /dev/ttyACM* /dev/video*; do
    [[ -e "$dev" ]] || continue
    name=$(basename "$dev")
    if [[ "$want" == "video" ]]; then
      [[ "$name" == video* ]] && { echo "$dev"; return; }
      continue
    fi
    [[ "$name" == tty* ]] || continue
    ids=$(usb_ids tty "$name"); vp=${ids%% *}; iface=${ids##* }
    case "$want" in
      *:*:*) [[ "$vp" == "${want%:*}" && "$iface" == "${want##*:}" ]] && { echo "$dev"; return; } ;;
      *:)    [[ "$vp" == "$want"* ]] && { echo "$dev"; return; } ;;
      *)     [[ "$vp" == "$want" ]] && { echo "$dev"; return; } ;;
    esac
  done
}

header "Could each of our drivers open its device? (nothing is opened)"
printf '  %-32s %-22s %-28s %-36s %s\n' "Part" "Wants" "Found" "Can open?" "In use by"
printf '  %-32s %-22s %-28s %-36s %s\n' "----" "-----" "-----" "---------" "---------"
while IFS='|' read -r part wants usb grp; do
  dev="" found_txt="-" can="-" busy=""
  if [[ -e "$wants" ]]; then
    dev=$wants; found_txt=$(readlink -f "$wants" 2>/dev/null || echo "$wants")
  elif [[ -n "$usb" ]]; then
    dev=$(match "$usb")
    [[ -n "$dev" ]] && found_txt="$dev (no udev name)"
  fi
  if [[ -n "$dev" ]]; then
    can=$(access "$dev")
    busy=$(holders "$dev")
  elif ! in_group "$grp"; then
    can="not here (you're not in $grp)"
  else
    can="not here"
  fi
  printf '  %-32s %-22s %-28s %-36s %s\n' "$part" "$wants" "$found_txt" "$can" "${busy:--}"
done <<EOF
$PARTS
EOF
spine="-" can="not here"
if [[ -e /sys/class/net/can0 ]]; then
  spine="can0 is $(cat /sys/class/net/can0/operstate)"
  can="needs can0 up (sudo ip link)"
  [[ "$spine" == *up ]] && can="yes"
fi
printf '  %-32s %-22s %-28s %-36s %s\n' "spine (ros2_socketcan)" "can0" "$spine" "$can" "-"
udp="unknown (no ss)"
if command -v ss >/dev/null; then
  udp=$(ss -Huanp 2>/dev/null | awk '$4 ~ /:10111$/ {print $NF}' | head -1)
  [[ -n "$udp" ]] || udp="free"
fi
printf '  %-32s %-22s %-28s %-36s %s\n' "wheel encoder (encoder_udp)" "UDP port 10111" \
  "$udp" "$( [[ "$udp" == free ]] && echo yes || echo "only once the port is free")" "-"
say ""
say "  'In use by' sees only $me's programs; another user's need sudo (not on Friday)."
say "  A driver whose device is in use must wait until the 2025-26 software is stopped."
say "  'needs group X': an admin runs 'sudo usermod -aG X $me' (later, not on Friday)."

header "ROS"
for d in /opt/ros/*; do [[ -d "$d" ]] && say "  installed, left alone: $d"; done
n=$(ps -eo comm= 2>/dev/null | grep -c -E '^(ros2|_ros2_daemon|python3|component_conta)') || true
say "  processes named ros2, python3 or component_container now: $n (the 2025-26 software, maybe)"
if [[ "${ROS_DISTRO:-}" == "jazzy" ]] && command -v ros2 >/dev/null; then
  say "  ours: ROS 2 $ROS_DISTRO from $CONDA_PREFIX"
  if pkg=$(ros2 pkg prefix aav_bringup 2>/dev/null); then
    say "  our packages are built: $pkg"
  else
    say "  our packages aren't built yet: run tools/car_install.sh again"
  fi
else
  say "  ours: not installed here (tools/car_install.sh), so no ROS check"
fi
