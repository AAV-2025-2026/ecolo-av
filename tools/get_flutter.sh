#!/usr/bin/env bash
# Download one pinned stable Flutter SDK into vendor/flutter/, for the HUD app
# (hud/flutter_pi). Like the rest of vendor/, it's other people's code, and not in git.
#
# usage: tools/get_flutter.sh      (or: pixi run get-flutter)
#
# Flutter 3.35.7 (Dart 3.9.2), the last 3.35 release. The app's pubspec.lock was made
# with Flutter 3.35: it needs Flutter 3.35 or newer, and Flutter pins some packages
# exactly (meta 1.16.0, test_api 0.7.6), so 3.38 and newer would rewrite the lock.
# conda-forge has no Flutter, so it can't come from Pixi.
#
# The archive is checked by the SHA-256 that Flutter publishes in its releases JSON
# (storage.googleapis.com/flutter_infra_release/releases/releases_macos.json and
# releases_linux.json), and the SDK by its git commit. Flutter publishes archives for
# macOS (arm64 and x64) and Linux x64 only: none for Linux arm64 (the Pis, the Orin).
#
# Afterwards it fetches what the app's tests need, so `pixi run hud-test` runs offline:
# the engine's files for this computer, into vendor/flutter/bin/cache, and the app's
# packages from pub.dev, into vendor/flutter/.pub-cache. HTTPS checks those, and pub
# checks each package against the SHA-256 in pubspec.lock.
set -euo pipefail
cd "$(dirname "$0")/.."

version=3.35.7
commit=adc901062556672b4138e18a4dc62a4be8f4b3c2   # the release's commit, from the JSON
base=https://storage.googleapis.com/flutter_infra_release/releases
dest=vendor/flutter

case "$(uname -s)/$(uname -m)" in
  Darwin/*)
    # An Apple-silicon Mac says x86_64 under Rosetta: ask the hardware instead.
    if [[ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" == 1 ]]; then
      archive=stable/macos/flutter_macos_arm64_$version-stable.zip
      sum=4d7aaadc4893f9216d4e2ecbe0e8fb4213e9bd49d29fd5f441f34fcc05758e2b
    else
      archive=stable/macos/flutter_macos_$version-stable.zip
      sum=1d9630be94c200877a3799d88db587e3575f88dd05c98bae733756bec0a8ec97
    fi
    ;;
  Linux/x86_64)
    archive=stable/linux/flutter_linux_$version-stable.tar.xz
    sum=146df531f9ac6a11a918013c1a70faafc053d4811c8cb69a413fd70748d51c3d
    ;;
  *)
    echo "Flutter publishes no SDK archive for $(uname -s) $(uname -m)." >&2
    echo "Use a Mac or a Linux x64 computer (docs/hud.md)." >&2
    exit 1
    ;;
esac

if [[ -e $dest ]]; then
  got=$(git -C "$dest" rev-parse HEAD 2>/dev/null || echo none)
  if [[ $got != "$commit" ]]; then
    echo "$dest isn't Flutter $version: delete it (rm -rf $dest) and run this again" >&2
    exit 1
  fi
  echo "$dest: Flutter $version is already there"
else
  # A new, empty folder for the download, next to where it ends up (the same disk).
  tmp=$(mktemp -d vendor/.get-flutter.XXXXXX)
  trap 'rm -rf "$tmp"' EXIT
  file=$tmp/${archive##*/}
  echo "Downloading Flutter $version: ${archive##*/} (1.5 to 2 GB)"
  curl -fL --retry 3 -o "$file" "$base/$archive"
  if command -v sha256sum >/dev/null; then
    got=$(sha256sum "$file" | cut -d' ' -f1)
  else
    got=$(shasum -a 256 "$file" | cut -d' ' -f1)
  fi
  if [[ $got != "$sum" ]]; then
    echo "${archive##*/} isn't the file Flutter published (SHA-256 $got): not unpacked" >&2
    exit 1
  fi
  echo "Checked (SHA-256). Unpacking..."
  mkdir "$tmp/unpacked"
  case $file in
    *.zip) unzip -q "$file" -d "$tmp/unpacked" ;;
    *.tar.xz) tar -xJf "$file" -C "$tmp/unpacked" ;;
  esac
  rm "$file"
  got=$(git -C "$tmp/unpacked/flutter" rev-parse HEAD)
  if [[ $got != "$commit" ]]; then
    echo "the archive holds Flutter at $got, not $commit: not installed" >&2
    exit 1
  fi
  mv "$tmp/unpacked/flutter" "$dest"
fi

# The engine's files for this computer: enough to analyze and test the app, and to build
# it for this computer's desktop. No Android, iOS or web.
tools/flutter.sh precache --no-android --no-ios --no-web
(cd hud/flutter_pi && ../../tools/flutter.sh pub get --enforce-lockfile)
echo "$dest: Flutter $version, ok"
