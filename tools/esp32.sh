#!/usr/bin/env bash
# The Rust firmware for today's ESP32 control board: firmware/spine/boards/esp32-umod.
#
# usage: tools/esp32.sh tools          install Espressif's Rust and espflash (once)
#        tools/esp32.sh build [args]   build it (args go to cargo: --no-default-features --features can)
#        tools/esp32.sh flash [args]   build, flash it on the USB cable, show its log (args go to espflash)
#        tools/esp32.sh check          build both links, with clippy; "skipped" without the toolchain
#
# The ESP32 has Xtensa cores, which the stock Rust (and Pixi's) can't build for. `tools`
# installs, for this user only (no admin rights):
#   - espup and espflash, at fixed versions, into vendor/cargo-tools/bin (git ignores it);
#   - with espup: the Xtensa Rust toolchain "esp" into ~/.rustup/toolchains/esp, and the
#     Xtensa GCC linker beside it;
#   - vendor/esp/export-esp.sh: the two environment variables the build needs.
# It needs rustup (https://rustup.rs): espup adds the "esp" toolchain to it.
# docs/rust-firmware.md has the details.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

ESPUP_VERSION=0.18.0
ESPFLASH_VERSION=4.3.0          # 4.4 and later need rustc 1.95
XTENSA_RUST_VERSION=1.97.0.0
XTENSA_GCC_VERSION=16.2.0_20260914

TOOLS=$ROOT/vendor/cargo-tools/bin
EXPORT_FILE=$ROOT/vendor/esp/export-esp.sh
BOARD=$ROOT/firmware/spine/boards/esp32-umod
ELF=$BOARD/target/xtensa-esp32-none-elf/release/spine-esp32-umod

have_toolchain() {
  [[ -f $EXPORT_FILE ]] && command -v rustup >/dev/null &&
    rustup toolchain list | grep -qE '^esp( |$)'
}

need_toolchain() {
  if ! have_toolchain; then
    echo "No Xtensa Rust here: run 'pixi run esp-tools' first (docs/rust-firmware.md)." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  . "$EXPORT_FILE"
  # The esp toolchain's own cargo and rustc first: under `pixi run`, Pixi's stock Rust
  # comes first on PATH, and cargo would build with its rustc.
  PATH="$(dirname "$(rustup which --toolchain esp rustc)"):$PATH"
  export PATH
}

build() {
  need_toolchain
  (cd "$BOARD" && cargo build --release --locked "$@")
}

case "${1:-}" in
  tools)
    command -v rustup >/dev/null || {
      echo "espup needs rustup: install it from https://rustup.rs, then run this again." >&2
      exit 1
    }
    cargo install --locked --root "$ROOT/vendor/cargo-tools" \
      "espup@$ESPUP_VERSION" "espflash@$ESPFLASH_VERSION"
    mkdir -p "$(dirname "$EXPORT_FILE")"
    "$TOOLS/espup" install --targets esp32 \
      --toolchain-version "$XTENSA_RUST_VERSION" \
      --crosstool-toolchain-version "$XTENSA_GCC_VERSION" \
      --export-file "$EXPORT_FILE"
    echo "Installed: espup and espflash in vendor/cargo-tools/bin; Xtensa Rust" \
         "$XTENSA_RUST_VERSION in ~/.rustup/toolchains/esp; $EXPORT_FILE."
    ;;
  build)
    shift
    build "$@"
    ;;
  flash)
    shift
    build
    "$TOOLS/espflash" flash --chip esp32 --monitor "$ELF" "$@"
    ;;
  check)
    if ! have_toolchain; then
      echo "skipped: no Xtensa Rust here (pixi run esp-tools)"
      exit 0
    fi
    need_toolchain
    cd "$BOARD"
    cargo fmt --check
    cargo clippy -q --release --locked -- -D warnings
    cargo clippy -q --release --locked --no-default-features \
      --features can,estop-input --target-dir target/can -- -D warnings
    cargo clippy -q --release --locked --features qemu --target-dir target/qemu -- -D warnings
    cargo build -q --release --locked
    echo "builds: the Motor-Pi UART link (default), CAN, and the QEMU build"
    ;;
  *)
    sed -n '2,8p' "$0" >&2
    exit 2
    ;;
esac
