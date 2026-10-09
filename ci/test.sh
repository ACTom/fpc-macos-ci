#!/bin/bash
# Build the FPC compiler of a source tree and run the macOS TLS tests.
# Usage: test.sh <fpc source> <output dir> <x86_64|arm64>
set -euo pipefail
src="$1"; out="$2"; arch="$3"
if [[ "$arch" = arm64 ]]; then cpu=aarch64; compiler_name=ppca64; minimum=11.0; else cpu=x86_64; compiler_name=ppcx64; minimum=10.8; fi
sdk="$(xcrun --sdk macosx --show-sdk-path)"
tools="$(dirname "$(xcrun --sdk macosx --find ld)")"
mkdir -p "$out"
common="-XR$sdk -WM$minimum -FD$tools"
echo "=== building the compiler of $(git -C "$src" log --oneline -1)"
make -C "$src/compiler" cycle -j4 "FPC=$FPC_BOOTSTRAP_COMPILER" \
  "OPT=-n -Fu$FPC_BOOTSTRAP_UNITS $common" "OPTNEW=$common" > "$out/cycle.log" 2>&1 \
  || { tail -30 "$out/cycle.log"; exit 1; }
fpc="$src/compiler/$compiler_name"
opts=(-n -gl $common "-Fu$src/rtl/units/$cpu-darwin" "-FU$out" "-FE$out"
  "-Fu$src/packages/fcl-net/src" "-Fi$src/packages/fcl-net/src/unix"
  "-Fu$src/packages/fcl-base/src" "-Fu$src/packages/fcl-web/src/base"
  "-Fu$src/packages/rtl-objpas/src/inc" "-Fu$src/packages/rtl-extra/src/unix"
  "-Fu$src/packages/rtl-extra/src/darwin" "-Fu$src/packages/rtl-extra/src/bsd"
  "-Fi$src/packages/rtl-extra/src/inc" "-Fi$src/packages/rtl-extra/src/bsd"
  "-Fi$src/packages/rtl-extra/src/unix" "-Fi$src/packages/rtl-extra/src/darwin"
  "-Fu$src/packages/openssl/src" "-Fu$src/packages/gnutls/src")
failed=0
run() {
  echo "=== $*"
  if "$@"; then echo "=== PASS $1"; else echo "=== FAIL $1"; failed=1; fi
}
compile() {
  "$fpc" "${opts[@]}" "$1" > "$out/$(basename "$1" .pp).build.log" 2>&1 \
    || { tail -20 "$out/$(basename "$1" .pp).build.log"; return 1; }
}
tests="$src/packages/fcl-net/tests"
for t in thandlesconnect tsslselect testnetworkframework; do
  if [[ -f "$tests/$t.pp" ]]; then
    if compile "$tests/$t.pp"; then
      if [[ "$t" = tsslselect ]]; then run "$out/$t" all; else run "$out/$t"; fi
    else
      echo "=== FAIL compile $t"; failed=1
    fi
  fi
done
exit $failed
