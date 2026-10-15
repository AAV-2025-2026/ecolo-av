#!/usr/bin/env bash
# Start one of the car's two screens, full screen on its own monitor: the HUD (the
# instrument cluster) or the map window. docs/car-screens.md.
#
# usage: tools/car_screen.sh hud|map [--config FILE] [--print]
#        tools/car_screen.sh --list
#
#   hud, map       which window. Its monitor comes from the config
#   --config FILE  instead of ~/.config/aav/screens.env (tools/screens/screens.env is the
#                  template; tools/car_screens_install.sh installs it)
#   --print        check the config, print what it would run, run nothing
#   --list         the monitors raylib sees: their numbers and names, for the config
#
# At login, aav-hud.service and aav-map.service run it through aav.sh, which gives it our
# Jazzy and our built packages:  ~/aav-jazzy/aav.sh tools/car_screen.sh hud
#
# Exit 78 (EX_CONFIG) means the config is wrong or unfinished: the units don't retry
# that. Any other failure (no display yet, a crash) they retry every 5 s.
# Portable: bash 3.2, no GNU-only flags.
set -euo pipefail

CONFIG="$HOME/.config/aav/screens.env"
EX_CONFIG=78
USAGE="usage: tools/car_screen.sh hud|map [--config FILE] [--print]   or   --list"

which="" print=0
# What the config says. Read, never sourced: it runs nothing.
hud_monitor="" map_monitor="" domain="" street_map="" places=""

say() { echo "car_screen${which:+ $which}: $*" >&2; }

config_problem() {
  say "$*"
  say "the config: $CONFIG (docs/car-screens.md)"
  exit "$EX_CONFIG"
}

# KEY=value lines, only the keys below; # starts a comment line.
read_config() {
  if [[ ! -f "$CONFIG" ]]; then
    config_problem "no config file: tools/car_screens_install.sh writes one"
  fi
  local n=0 line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    n=$((n + 1))
    line=${line%$'\r'}
    case "$line" in ''|'#'*) continue ;; esac
    if [[ "$line" != *=* ]]; then config_problem "line $n isn't KEY=value: $line"; fi
    key=${line%%=*} value=${line#*=}
    # One pair of quotes around the value is fine; nothing is expanded.
    if [[ "$value" == \"*\" && ${#value} -ge 2 ]]; then value=${value:1:${#value}-2}; fi
    case "$key" in
      AAV_HUD_MONITOR) hud_monitor=$value ;;
      AAV_MAP_MONITOR) map_monitor=$value ;;
      AAV_ROS_DOMAIN_ID) domain=$value ;;
      AAV_STREET_MAP) street_map=$value ;;
      AAV_PLACES) places=$value ;;
      *) config_problem "line $n: unknown key $key" ;;
    esac
  done < "$CONFIG"
}

list=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    hud|map) which=$1 ;;
    --config) CONFIG=${2:?--config needs a file}; shift ;;
    --print) print=1 ;;
    --list) list=1 ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "car_screen: unknown option $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

if [[ $list == 1 ]]; then
  ros2 run aav_hud_raylib hud --list-monitors
elif [[ -z "$which" ]]; then
  echo "$USAGE" >&2
  exit 2
else
  # It is defined above: shellcheck 0.11's SC2218 here is a false alarm.
  # shellcheck disable=SC2218
  read_config

  if [[ $which == hud ]]; then monitor=$hud_monitor; else monitor=$map_monitor; fi
  upper=$(echo "$which" | tr '[:lower:]' '[:upper:]')
  if [[ -z "$monitor" ]]; then
    config_problem "AAV_${upper}_MONITOR is empty: set it to a name or number from: tools/car_screen.sh --list"
  fi
  if [[ -n "$hud_monitor" && "$hud_monitor" == "$map_monitor" ]]; then
    say "NOTE: the HUD and the map are both on monitor $monitor: one hides the other"
  fi
  # ROS 2 takes 0-232; 0 and 10 are the 2025-26 team's (docs/car-install.md).
  if ! [[ "$domain" =~ ^[0-9]+$ ]] || (( domain > 232 )); then
    config_problem "AAV_ROS_DOMAIN_ID must be a number from 0 to 232, not '${domain}'"
  fi
  for f in "$street_map" "$places"; do
    if [[ -n "$f" && "$f" != /* ]]; then config_problem "map files need a full path: $f"; fi
  done

  args=(fullscreen:=true "monitor:=$monitor")
  if [[ $which == map ]]; then
    # A missing file isn't fatal: the window says so on screen, and still shows the car.
    for f in "$street_map" "$places"; do
      if [[ -n "$f" && ! -f "$f" ]]; then say "NOTE: $f isn't there (docs/car-screens.md: the map's files)"; fi
    done
    if [[ -n "$street_map" ]]; then args+=("streets:=$street_map"); fi
    if [[ -n "$places" ]]; then args+=("places:=$places"); fi
  fi

  export ROS_DOMAIN_ID=$domain
  cmd=(ros2 launch aav_hud_raylib "$which.launch.py" "${args[@]}")
  if [[ $print == 1 ]]; then
    echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID"
    printf '%q ' "${cmd[@]}"
    echo
  # raylib draws through X11 (GLFW): on a Wayland desktop that is XWayland's DISPLAY.
  elif [[ -z "${DISPLAY:-}" ]]; then
    say "no DISPLAY yet: the desktop hasn't shared it with systemd (retrying)"
    exit 1
  else
    say "monitor $monitor, ROS_DOMAIN_ID $ROS_DOMAIN_ID, DISPLAY $DISPLAY"
    exec "${cmd[@]}"
  fi
fi
