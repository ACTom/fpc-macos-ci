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
python3 - "$sdk" <<'PY' | tee "$output_dir/sdk-tls-api-audit.txt"
from pathlib import Path
import re, sys
sdk=Path(sys.argv[1])/'System/Library/Frameworks'
for relative in ['Network.framework/Headers/connection.h', 'Network.framework/Headers/tls_options.h',
                 'Security.framework/Headers/SecProtocolMetadata.h', 'Security.framework/Headers/SecProtocolOptions.h']:
    path=sdk/relative
    print('SDK_HEADER',relative)
    if not path.is_file():
        print('NOT FOUND'); continue
    lines=path.read_text().splitlines()
    matches=[i for i,line in enumerate(lines) if re.search(r'close.?notify|truncat|\bEOF\b|nw_connection_receive_completion_t',line,re.I)]
    for index in matches:
        after=48 if '@typedef nw_connection_receive_completion_t' in lines[index] else 4
        print('\n'.join(f'{i+1}: {lines[i]}' for i in range(max(0,index-2),min(len(lines),index+after))))
    if not matches: print('No close-notify/truncation/EOF declaration matched')
    if 'SecProtocol' in relative:
        print('PUBLIC_NAMES', ' '.join(sorted(set(re.findall(r'sec_protocol_(?:options|metadata)_[a-z0-9_]+',path.read_text())))))
PY
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
options=(-n -gl -dFPC_NETWORKFRAMEWORK_DIAGNOSTICS "-XR$sdk" "-WM$minimum" "-FD$tools_dir" "-Fu$unit_root"
  "-Fu$source_dir/packages/fcl-net/src"
  "-Fu$source_dir/packages/fcl-web/src/base" "-Fu$source_dir/packages/fcl-base/src"
  "-Fu$source_dir/packages/rtl-objpas/src/inc" "-Fu$source_dir/packages/rtl-extra/src/unix"
  "-Fu$source_dir/packages/rtl-extra/src/darwin" "-Fu$source_dir/packages/rtl-extra/src/bsd"
  "-Fi$source_dir/packages/fcl-net/src/unix" "-Fi$source_dir/packages/fcl-net/tests" "-Fi$source_dir/packages/rtl-extra/src/inc"
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
stage native-compile "$compiler" "${options[@]}" "$source_dir/packages/fcl-net/tests/testnetworknative.pp"
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
stage packages make -C "$source_dir/packages" all -j4 "FPC=$compiler" "FPMAKEOPT=-T 4 -sap -o '-XR$sdk'" "OPT=-XR$sdk"
for unit_dir in "$source_dir"/packages/*/units/"$cpu-darwin"; do
  if test -d "$unit_dir"; then options+=("-Fu$unit_dir"); fi
done
# Keep the existing runner on one matching set of package PPUs. Earlier native
# pre-package compilation writes source-built RTL/FCL units to output_dir.
runner_dir="$output_dir/http-runner-units"
mkdir "$runner_dir"
runner_options=(-n -gl "-XR$sdk" "-WM$minimum" "-FD$tools_dir" "-Fu$unit_root"
  "-FU$runner_dir" "-FE$runner_dir")
for unit_dir in "$source_dir"/packages/*/units/"$cpu-darwin"; do
  if test -d "$unit_dir"; then runner_options+=("-Fu$unit_dir"); fi
done
# These extra source paths are declared in the existing testfpweb.lpi.
runner_options+=("-Fu$source_dir/packages/fcl-web/src/base" "-Fu$source_dir/packages/fcl-web/src/jwt"
  "-Fu$source_dir/packages/fcl-web/src/restbridge" "-Fu$source_dir/packages/fcl-openapi/src"
  "-Fu$source_dir/packages/fcl-jsonschema/src" "-Fi$source_dir/packages/fcl-net/src/unix")
# Run the new Unix-route cases against the exact previous HTTP implementation.
# Only this temporary copy is reverted; the tested final source stays unchanged.
# A test-only unit name prevents resolving to the final package's PPU or object.
before_dir="$output_dir/http-runner-before"
mkdir "$before_dir"
python3 - "$source_dir" "$before_dir" <<'PY'
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys
source, before = map(Path, sys.argv[1:])
manifest = json.loads((Path(os.environ['GITHUB_WORKSPACE'])/'payload/manifest.json').read_text())
regression = manifest['unix_route_regression']
target = before/regression['path']
target.parent.mkdir(parents=True)
shutil.copyfile(source/regression['path'], target)
subprocess.run(['git', 'apply', '--check', '-'], input=regression['reverse_patch'].encode(), cwd=before, check=True)
subprocess.run(['git', 'apply', '-'], input=regression['reverse_patch'].encode(), cwd=before, check=True)
assert hashlib.sha256(target.read_bytes()).hexdigest() == regression['prior_source_sha256']
previous = target.read_text()
assert previous.count('unit fpHTTPClient;') == 1
aliased = previous.replace('unit fpHTTPClient;', 'unit fphttpclient_before;')
assert aliased.replace('unit fphttpclient_before;', 'unit fpHTTPClient;') == previous
(before/'fphttpclient_before.pp').write_text(aliased)
for name in ['testfpweb.lpr', 'tcclientpeer.pp']:
    shutil.copyfile(source/'packages/fcl-web/tests'/name, before/name)
test_unit = before/'tcclientpeer.pp'
tests = test_unit.read_text()
assert tests.count('clientpeers, fphttpclient;') == 1
test_unit.write_text(tests.replace('clientpeers, fphttpclient;', 'clientpeers, fphttpclient_before;'))
print('PASS exact previous HTTP source', regression['prior_commit'], regression['prior_source_sha256'])
print('PASS previous HTTP unit uses a test-only name; its implementation and test assertions are unchanged')
PY
before_options=("-Fu$before_dir" "${runner_options[@]}" "-Fu$source_dir/packages/fcl-web/tests" "-FU$before_dir" "-FE$before_dir")
compile_previous_http() {
  (cd "$before_dir"; "$compiler" "${before_options[@]}" "$@")
}
stage http-unix-before-unit-compile compile_previous_http "$before_dir/fphttpclient_before.pp"
stage http-unix-before-runner-compile compile_previous_http "$before_dir/testfpweb.lpr"
echo 'STAGE http-unix-regression-before RUN'
before_status=0
"$before_dir/testfpweb" --suite=TTestClientPeers.TestUnixHTTPSWithoutTLSHandler,TTestClientPeers.TestUnixHTTPSWithoutHandlerCallbacks \
  --format=plain > "$output_dir/http-unix-regression-before.log" 2>&1 || before_status=$?
cat "$output_dir/http-unix-regression-before.log"
python3 - "$output_dir/http-unix-regression-before.log" "$before_status" <<'PY'
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
assert int(sys.argv[2]) != 0, 'Previous HTTP implementation unexpectedly passed'
assert 'Number of run tests: 2' in text
assert 'No SSL Socket support compiled in.' in text, 'Missing unregistered-backend regression'
assert 'Unix route must skip OnGetSocketHandler' in text, 'Missing callback regression'
print('PASS both regressions reproduced against the exact previous HTTP source')
PY
echo 'STAGE http-unix-regression-before PASS (expected failures verified)'
stage testfpweb-compile "$compiler" "${runner_options[@]}" "$source_dir/packages/fcl-web/tests/testfpweb.lpr"
stage http-peer-model "$runner_dir/testfpweb" --suite=TTestClientPeers --format=plain
stage http-protocol-regression "$runner_dir/testfpweb" --suite=TTestHTTPEncode --format=plain
stage testsocketpeer-compile "$compiler" "${runner_options[@]}" "$source_dir/packages/fcl-web/tests/testsocketpeer.pp"
stage real-socket-regression python3 "$GITHUB_WORKSPACE/ci/run_socket_test.py" "$runner_dir/testsocketpeer"
for program in testnetworkhttp testnetworkpeer; do
  stage "$program-compile" "$compiler" "${options[@]}" "$source_dir/packages/fcl-net/tests/$program.pp"
done
stage public-peer-construction "$output_dir/testnetworkpeer"
options+=("-Fu$source_dir/packages/fcl-tls/src" "-Fu$source_dir/packages/openssl/src" "-Fu$source_dir/packages/gnutls/src")
for program in testsmartselection testsmartnetworkhttp; do
  stage "$program-compile" "$compiler" "${options[@]}" "$source_dir/packages/fcl-tls/tests/$program.pp"
done
stage smart-selector python3 "$GITHUB_WORKSPACE/ci/testsmartmatrix.py" --source "$source_dir" \
  --program "$output_dir/testsmartselection" --compiler "$compiler" --rtl "$unit_root" \
  --output "$output_dir/selector-fixtures"
otool -L "$output_dir/testsmartnetworkhttp" > "$output_dir/smart-imports.txt"
stage smart-imports python3 "$GITHUB_WORKSPACE/ci/check_smart_imports.py" "$output_dir/smart-imports.txt"
stage smart-native-tls-acceptance python3 "$GITHUB_WORKSPACE/ci/testnetworktls.py" "$output_dir/testnetworknative" "$output_dir/testsmartnetworkhttp" "$output_dir/tls-fixtures" --peer "$output_dir/testnetworkpeer"
echo 'PASS native prerequisites, smart selection and real native TLS; see every result and counter'
