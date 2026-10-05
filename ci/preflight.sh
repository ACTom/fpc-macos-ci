#!/bin/bash
set -euo pipefail
source_dir="${1:?Pass patched FPC source}"
output_dir="${2:?Pass dedicated output directory}"
expected_arch="${3:?Pass x86_64 or arm64}"
test "$(uname -s)" = Darwin
test "$(uname -m)" = "$expected_arch"
mkdir -p "$output_dir"
stage() {
  local name="$1"; shift
  echo "STAGE $name RUN"
  if "$@" 2>&1 | tee "$output_dir/$name.log"; then
    echo "STAGE $name PASS"
  else
    local result="$?"
    echo "STAGE $name FAIL exit=$result"
    return "$result"
  fi
}
sw_vers
sdk="$(xcrun --sdk macosx --show-sdk-path)"
xcrun clang --version
if [[ "$expected_arch" = arm64 ]]; then cpu=aarch64; compiler_name=ppca64; minimum=11.0; else cpu=x86_64; compiler_name=ppcx64; minimum=10.8; fi
bootstrap="${FPC_BOOTSTRAP_COMPILER:-}"
if [[ -z "$bootstrap" ]] && command -v fpc >/dev/null 2>&1; then bootstrap="$(command -v fpc)"; fi
if [[ -z "$bootstrap" ]]; then
  echo 'NOT RUN Darwin Pascal compile/link/runtime: no existing bootstrap. No software downloaded or installed.'
  echo 'See BOOTSTRAP-PLAN.md. Provisioning and another manual dispatch require owner approval.'
  exit 77
fi
test "$("$bootstrap" -iTO)" = darwin
test "$("$bootstrap" -iTP)" = "$cpu"
"$bootstrap" -iV
bootstrap_opt="-XR$sdk -WM$minimum"
if [[ -n "${FPC_BOOTSTRAP_UNITS:-}" ]]; then
  test -f "$FPC_BOOTSTRAP_UNITS/system.ppu"
  bootstrap_opt="-n -Fu$FPC_BOOTSTRAP_UNITS -XR$sdk -WM$minimum"
fi
tools_dir="$(dirname "$(xcrun --sdk macosx --find ld)")"
bootstrap_opt="$bootstrap_opt -FD$tools_dir"
# Fresh temporary source tree only. The compiler cycle builds its matching RTL.
stage compiler-cycle make -C "$source_dir/compiler" cycle -j4 "FPC=$bootstrap" "OPT=$bootstrap_opt" "OPTNEW=-XR$sdk -WM$minimum -FD$tools_dir"
compiler="$source_dir/compiler/$compiler_name"
test -x "$compiler"
test "$("$compiler" -iV)" = 3.3.1
unit_root="$source_dir/rtl/units/$cpu-darwin"
test -f "$unit_root/system.ppu"
options=(-n -gl -dFPC_NETWORK_FRAMEWORK_NATIVE -dFPC_NETWORKFRAMEWORK_DIAGNOSTICS "-XR$sdk" "-WM$minimum" "-FD$tools_dir" "-Fu$unit_root"
  "-Fu$source_dir/packages/fcl-net/src" "-Fu$source_dir/packages/fcl-tls/src"
  "-Fu$source_dir/packages/fcl-web/src/base" "-Fu$source_dir/packages/fcl-base/src"
  "-Fu$source_dir/packages/rtl-objpas/src/inc" "-Fu$source_dir/packages/rtl-extra/src/unix"
  "-Fu$source_dir/packages/rtl-extra/src/darwin" "-Fu$source_dir/packages/rtl-extra/src/bsd"
  "-Fu$source_dir/packages/openssl/src" "-Fu$source_dir/packages/gnutls/src"
  "-Fi$source_dir/packages/fcl-net/src/unix" "-Fi$source_dir/packages/rtl-extra/src/inc"
  "-Fi$source_dir/packages/rtl-extra/src/bsd" "-Fi$source_dir/packages/rtl-extra/src/unix" "-Fi$source_dir/packages/rtl-extra/src/darwin"
  "-FU$output_dir" "-FE$output_dir")
# The branch's own global/object-method Blocks ABI checks.
for program in tblock1 tblock2 tblock2a; do
  mkdir "$output_dir/$program"
  stage "blocks-$program-compile" "$compiler" -n "-Fu$unit_root" "-XR$sdk" "-WM$minimum" "-FD$tools_dir" \
    "-FU$output_dir/$program" "-FE$output_dir/$program" "$source_dir/tests/test/$program.pp"
  stage "blocks-$program-run" "$output_dir/$program/$program"
done
# Establish the native compiler/Blocks/link boundary before building FCL packages.
stage native-compile "$compiler" "${options[@]}" "$source_dir/packages/fcl-tls/tests/macos/testnetworknative.pp"
stage native-construction "$output_dir/testnetworknative"
echo "STAGE native-imports RUN"
otool -L "$output_dir/testnetworknative" | tee "$output_dir/native-imports.txt"
nm -u "$output_dir/testnetworknative" | tee "$output_dir/native-symbols.txt"
otool -l "$output_dir/testnetworknative" > "$output_dir/native-load-commands.txt"
python3 - "$output_dir/native-imports.txt" "$output_dir/native-load-commands.txt" "$minimum" <<'PY'
from pathlib import Path
import re, sys
imports=Path(sys.argv[1]).read_text().lower()
for name in ['network.framework','security.framework','libssl','libcrypto','libgnutls']:
    assert name not in imports, 'Unexpected strong/native TLS dependency: '+name
commands=Path(sys.argv[2]).read_text()
versions=[]
for command in commands.split('Load command ')[1:]:
    if 'cmd LC_VERSION_MIN_MACOSX' in command:
        versions+=re.findall(r'^\s+version\s+(\d+(?:\.\d+)+)',command,re.M)
    if 'cmd LC_BUILD_VERSION' in command:
        versions+=re.findall(r'^\s+minos\s+(\d+(?:\.\d+)+)',command,re.M)
def version(value):
    parts=tuple(map(int,value.split('.')))
    return parts+(0,)*(3-len(parts))
assert versions, 'No macOS minimum deployment load command'
assert all(version(value)<=version(sys.argv[3]) for value in versions), 'Linker raised minimum deployment: '+repr(versions)
print('PASS no strong Network/Security or third-party TLS imports; minimum deployment',versions)
print('Blocks imports and old-system runtime still require review/real execution')
PY
echo "STAGE native-imports PASS"
stage packages make -C "$source_dir/packages" all -j4 "FPC=$compiler" "FPMAKEOPT=-T 4 -sap -o '-XR$sdk -dFPC_NETWORK_FRAMEWORK_NATIVE'" "OPT=-XR$sdk"
for program in testpolicy testfactory testnetworkstream testhttpconnection testnetworkhandler testsmart; do
  stage "$program-compile" "$compiler" "${options[@]}" "$source_dir/packages/fcl-tls/tests/$program.pp"
done
for program in testpolicy testfactory testnetworkstream testhttpconnection testnetworkhandler; do stage "$program-run" "$output_dir/$program"; done
stage native-selector-race "$output_dir/testsmart" race
stage native-http-compile "$compiler" "${options[@]}" "$source_dir/packages/fcl-tls/tests/macos/testnetworkhttp.pp"
stage native-tls-acceptance python3 "$source_dir/packages/fcl-tls/tests/macos/testnetworktls.py" "$output_dir/testnetworknative" "$output_dir/testnetworkhttp" "$output_dir/tls-fixtures"
echo 'PASS native build/models/TLS acceptance; see per-case results and context counters'
