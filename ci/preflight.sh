#!/bin/bash
set -euo pipefail
source_dir="${1:?Pass the patched FPC source directory}"
output_dir="${2:?Pass a dedicated build output directory}"
expected_arch="${3:?Pass x86_64 or arm64}"
probe_source="$source_dir/packages/fcl-tls/tests/macos/networkframework-api.c"
test -f "$probe_source"
test "$(uname -s)" = Darwin
test "$(uname -m)" = "$expected_arch"
mkdir -p "$output_dir"
sw_vers
xcrun --sdk macosx --show-sdk-path
xcrun clang --version
if command -v fpc >/dev/null 2>&1; then
  fpc -iV
  fpc -iTP
  fpc -iTO
else
  echo 'NOT RUN FPC compilation: no existing bootstrap compiler on PATH; nothing installed'
fi
if test "$expected_arch" = arm64; then deployment_target=11.0; else deployment_target=10.14; fi
xcrun --sdk macosx clang -std=c11 -fblocks -Wall -Wextra -Werror \
  "-mmacosx-version-min=$deployment_target" "$probe_source" \
  -framework Network -framework Security -o "$output_dir/networkframework-api"
"$output_dir/networkframework-api"

# Production bridge API/lifetime construction only; no native TLS connection.
bridge_source="$source_dir/packages/fcl-tls/src/macos/networkframeworkbridge.c"
native_harness="$source_dir/packages/fcl-tls/tests/macos/testnetworkbridge.c"
xcrun --sdk macosx clang -std=c11 -fblocks -Wall -Wextra -Werror \
  "-mmacosx-version-min=$deployment_target" -c "$bridge_source" \
  -o "$output_dir/networkframeworkbridge.o"
xcrun --sdk macosx clang -std=c11 -Wall -Wextra -Werror \
  "-mmacosx-version-min=$deployment_target" "$native_harness" \
  "$output_dir/networkframeworkbridge.o" -o "$output_dir/testnetworkbridge"
"$output_dir/testnetworkbridge"
