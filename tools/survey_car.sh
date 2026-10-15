#!/usr/bin/env bash
# Run tools/machine_survey.sh on every car computer, from a laptop, and save each one's
# output in ~/aav-audit/. Read-only on the car (machine_survey.sh says how).
#
# usage: pixi run survey ~/aav-audit/hosts.txt
#
# hosts.txt: one machine per line, "<label> <user>@<ip>". Lines starting with # are skipped.
#   JETSON   aavjetson@192.168.1.20
#   RTK-PI   pi@192.168.1.31
# Keep hosts.txt and the outputs out of git. Logins come from the team; ssh asks for each
# password (or uses your key). Never put a password in hosts.txt.
#
# Portable: bash 3.2 (a Mac), no GNU-only flags.
set -u
hosts=${1:?usage: survey_car.sh <hosts.txt>}
here=$(cd "$(dirname "$0")" && pwd)
out=${SURVEY_OUT:-$HOME/aav-audit}
mkdir -p "$out"
chmod 700 "$out"

while read -r label target _; do
  case "$label" in ''|'#'*) continue;; esac
  file="$out/$label.txt"
  printf '%-12s %-28s ' "$label" "$target"
  # ssh's input is the script, so it can't swallow the rest of hosts.txt.
  ssh -o ConnectTimeout=8 "$target" 'bash -s' < "$here/machine_survey.sh" > "$file" 2>&1
  lines=$(wc -l < "$file" | tr -d ' ')
  if grep -q '==== done' "$file"; then
    echo "OK    $lines lines -> $file"
  else
    echo "PART  $lines lines -> $file (stopped early: read its end)"
  fi
done < "$hosts"

echo
echo "Next: read each file before sharing it (secrets are cut, but check)."
echo "Copy anything that exists only on the car (weights, unpushed code): FRIDAY-TODO.md, part 4."
