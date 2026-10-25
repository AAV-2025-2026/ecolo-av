#!/usr/bin/env bash
# Make the car's two screens start at login: the HUD full screen on one monitor, the map
# on the other, restarted if they crash. docs/car-screens.md.
#
# usage: bash ~/aav-jazzy/aav/tools/car_screens_install.sh [install|uninstall] [--dry-run]
#        (or: car_install.sh --screens, which runs it after the build)
#
#   install     (the default) copies two systemd *user* units and an autostart entry
#               into ~/.config, writes ~/.config/aav/screens.env if there's none, and
#               enables the units. They start at the next login
#   uninstall   disables and removes them; keeps screens.env (delete it by hand)
#   --dry-run   says what it would do, changes nothing
#
# Run it on the car computer that drives the dash's screens, as the user that logs in to
# its desktop. No sudo: user units live in ~/.config/systemd/user. It needs our stack
# installed in ~/aav-jazzy (car_install.sh) with the HUD built (--all or --screens).
#
# Booting into that desktop without a password (auto-login) is a system setting, and
# needs an admin: this script doesn't touch it (docs/car-screens.md says how).
# Portable: bash 3.2, no GNU-only flags (it runs its dry run on a Mac, and refuses).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SCREENS="$HERE/screens"
PREFIX="$HOME/aav-jazzy"
UNITS="$HOME/.config/systemd/user"
AUTOSTART="$HOME/.config/autostart"
CONFIG="$HOME/.config/aav/screens.env"
NAMES="aav-hud.service aav-map.service"

action=install dry=0
for arg in "$@"; do
  case "$arg" in
    install|uninstall) action=$arg ;;
    --dry-run) dry=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

problems=0
ok()   { printf '  OK    %-12s %s\n' "$1" "$2"; }
bad()  { printf '  STOP  %-12s %s\n' "$1" "$2"; problems=$((problems + 1)); }
note() { printf '  NOTE  %-12s %s\n' "$1" "$2"; }
# Each change goes through do_it: shown in a dry run, done otherwise.
do_it() {
  if [[ $dry == 1 ]]; then printf '  would: %s\n' "$*"; else printf '  %s\n' "$*"; "$@"; fi
}

printf '== Checks (nothing changes yet)\n'
if [[ "$(uname -s)" == Linux ]]; then ok "system" "Linux"; else bad "system" "$(uname -s): this is for the car's Linux computer"; fi
if [[ "$(id -u)" == 0 ]]; then bad "user" "root: run it as the user that logs in to the desktop"; else ok "user" "$(id -un)"; fi
if command -v systemctl >/dev/null; then ok "systemd" "$(command -v systemctl)"; else bad "systemd" "no systemctl here"; fi
for f in aav-hud.service aav-map.service aav-screens.desktop screens.env; do
  [[ -f "$SCREENS/$f" ]] || bad "files" "$SCREENS/$f is missing"
done
if [[ $action == install ]]; then
  if [[ -f "$PREFIX/aav.sh" ]]; then ok "aav.sh" "$PREFIX/aav.sh"; else bad "aav.sh" "no $PREFIX/aav.sh: run car_install.sh first"; fi
  built="$PREFIX/aav/install/aav_hud_raylib/lib/aav_hud_raylib"
  if [[ -f "$built/hud" && -f "$built/map" ]]; then
    ok "built" "hud and map, in $built"
  else
    bad "built" "the HUD isn't built: car_install.sh --screens (or --all) builds it"
  fi
  if [[ -f "$CONFIG" ]]; then note "config" "$CONFIG is there: kept as it is"; else ok "config" "a new $CONFIG, from the template"; fi
  for f in "$PREFIX/aav/maps/streets/ottawa.pmtiles" "$PREFIX/aav/maps/places/ottawa.db"; do
    [[ -f "$f" ]] || note "map files" "no $f: the map shows no streets or no search (the kit copies them)"
  done
fi

if (( problems > 0 )) && [[ $dry == 0 ]]; then
  printf '\n%d check(s) failed: nothing was changed.\n' "$problems"
  exit 1
fi
label=""
if [[ $dry == 1 ]]; then label=" (dry run: what it would do)"; fi
if [[ $action == install ]]; then
  printf '\n== Install%s\n' "$label"
  do_it mkdir -p "$UNITS" "$AUTOSTART" "$(dirname "$CONFIG")"
  for unit in $NAMES; do do_it cp "$SCREENS/$unit" "$UNITS/$unit"; done
  do_it cp "$SCREENS/aav-screens.desktop" "$AUTOSTART/aav-screens.desktop"
  if [[ ! -f "$CONFIG" ]]; then
    # The template's @PREFIX@ becomes this computer's full path: no ~ or $HOME in it.
    if [[ $dry == 1 ]]; then
      printf '  would: write %s (tools/screens/screens.env, with %s)\n' "$CONFIG" "$PREFIX"
    else
      printf '  write %s\n' "$CONFIG"
      sed "s#@PREFIX@#$PREFIX#g" "$SCREENS/screens.env" > "$CONFIG"
    fi
  fi
  do_it systemctl --user daemon-reload
  # shellcheck disable=SC2086  # $NAMES is a list of words on purpose
  do_it systemctl --user enable $NAMES
else
  printf '\n== Uninstall%s\n' "$label"
  # shellcheck disable=SC2086  # $NAMES is a list of words on purpose
  do_it systemctl --user disable --now $NAMES || echo "  (they weren't enabled)"
  do_it rm -f "$UNITS/aav-hud.service" "$UNITS/aav-map.service" "$AUTOSTART/aav-screens.desktop"
  do_it systemctl --user daemon-reload
fi

if [[ $dry == 1 ]]; then
  if (( problems > 0 )); then
    printf '\nDry run: %d check(s) failed, so it would stop there. Nothing was changed.\n' "$problems"
    exit 1
  fi
  printf '\nDry run: every check passed, nothing was changed.\n'
  exit 0
fi

if [[ $action == uninstall ]]; then
  cat <<EOF

Done: the screens no longer start at login. Kept: $CONFIG (rm it to forget the monitors).
EOF
  exit 0
fi
cat <<EOF

Done: $NAMES start at the next login.
Next (docs/car-screens.md):
  1. The monitors' names:   $PREFIX/aav.sh tools/car_screen.sh --list
  2. Write them in:         $CONFIG   (AAV_HUD_MONITOR, AAV_MAP_MONITOR)
  3. Check, runs nothing:   $PREFIX/aav.sh tools/car_screen.sh hud --print
  4. Start them now:        systemctl --user restart aav-hud aav-map
  5. Their logs:            journalctl --user -u aav-hud -u aav-map -f
Undo:  bash $HERE/car_screens_install.sh uninstall
EOF
