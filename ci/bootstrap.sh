#!/bin/bash
set -euo pipefail
expected_arch="${1:?Pass expected native architecture}"
: "${RUNNER_TEMP:?}" "${GITHUB_ENV:?}" "${GITHUB_STEP_SUMMARY:?}"
test "$(uname -s)" = Darwin
test "$(uname -m)" = "$expected_arch"
case "$expected_arch" in
  x86_64) cpu=x86_64; compiler_name=ppcx64; minimum=10.8 ;;
  arm64) cpu=aarch64; compiler_name=ppca64; minimum=11.0 ;;
  *) exit 1 ;;
esac
work="$RUNNER_TEMP/fpc-official-bootstrap"
mkdir "$work"
mkdir "$work/logs" "$work/mount" "$work/hello"
sw_vers
xcodebuild -version
sdk="$(xcrun --sdk macosx --show-sdk-path)"
tools_dir="$(dirname "$(xcrun --sdk macosx --find ld)")"
test -d "$sdk"
test -x "$tools_dir/ld"
test -x "$tools_dir/as"
dmg="$work/fpc-3.2.2.intelarm64-macosx.dmg"
url='https://sourceforge.net/projects/freepascal/files/Mac%20OS%20X/3.2.2/fpc-3.2.2.intelarm64-macosx.dmg/download'
echo 'STAGE official-bootstrap-download RUN'
curl --fail --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 30 --max-time 300 --dump-header "$work/logs/download-headers.txt" \
  --output "$dmg" --write-out '%{url_effective}\n' "$url" \
  > "$work/logs/download-final-url.txt"
cat "$work/logs/download-final-url.txt"
shasum -a 256 "$dmg" | tee "$work/logs/observed-sha256.txt"
file "$dmg"
hdiutil verify "$dmg"
echo 'STAGE official-bootstrap-download PASS (observed hash, not independent publisher signature)'
mounted=false
detach_image() {
  if [[ "$mounted" = true ]]; then
    hdiutil detach "$work/mount" > "$work/logs/detach.txt" 2>&1 || true
  fi
}
trap detach_image EXIT
hdiutil attach -readonly -nobrowse -noautoopen -mountpoint "$work/mount" "$dmg"
mounted=true
echo 'STAGE official-bootstrap-extract RUN'
# Inventory before selecting. No installer, scripts or Distribution is executed.
python3 - "$work/mount" "$work/package-path.txt" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
all_packages=list(root.rglob('*.pkg'))
print('Package inventory:',*[str(p) for p in all_packages],sep='\n')
(Path(sys.argv[2]).parent/'logs/package-inventory.txt').write_text('\n'.join(map(str,all_packages))+'\n')
packages=[p for p in all_packages if p.is_file() and not p.is_symlink()]
assert len(packages)==1, 'Expected one flat product pkg; stop on bundle/ambiguous layout: '+repr(packages)
assert '\n' not in str(packages[0]), 'Invalid package path'
Path(sys.argv[2]).write_text(str(packages[0])+'\n')
PY
package="$(cat "$work/package-path.txt")"
pkgutil --expand-full "$package" "$work/expanded"
python3 - "$work/expanded" "$compiler_name" "$cpu" "$work/compiler-path.txt" "$work/rtl-path.txt" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
compilers=[p for p in root.rglob(sys.argv[2]) if p.is_file() and not p.is_symlink()]
units=[p for p in root.rglob('system.ppu') if str(p.parent).endswith('/units/'+sys.argv[3]+'-darwin/rtl')]
print('Native compiler inventory:',*[str(p) for p in compilers],sep='\n')
print('Native bootstrap RTL inventory:',*[str(p.parent) for p in units],sep='\n')
assert len(compilers)==1 and len(units)==1, 'Ambiguous/missing native compiler or RTL; no install fallback'
for target,value in [(sys.argv[4],compilers[0]),(sys.argv[5],units[0].parent)]:
    assert '\n' not in str(value)
    Path(target).write_text(str(value)+'\n')
PY
echo 'STAGE official-bootstrap-extract PASS'
echo 'STAGE official-bootstrap-identity RUN'
bootstrap="$(cat "$work/compiler-path.txt")"
units="$(cat "$work/rtl-path.txt")"
test -x "$bootstrap"
file "$bootstrap"
lipo "$bootstrap" -verify_arch "$expected_arch"
otool -L "$bootstrap"
test "$("$bootstrap" -n -iV)" = 3.2.2
test "$("$bootstrap" -n -iTP)" = "$cpu"
test "$("$bootstrap" -n -iTO)" = darwin
echo 'STAGE official-bootstrap-identity PASS'
echo 'STAGE official-bootstrap-hello RUN'
cat > "$work/hello/boothello.pp" <<'PASCAL'
program boothello;
begin Writeln('PASS official native bootstrap hello') end.
PASCAL
"$bootstrap" -n "-Fu$units" "-XR$sdk" "-FD$tools_dir" "-WM$minimum" \
  "-FU$work/hello" "-FE$work/hello" "$work/hello/boothello.pp"
"$work/hello/boothello"
echo 'STAGE official-bootstrap-hello PASS'
printf 'FPC_BOOTSTRAP_COMPILER=%s\nFPC_BOOTSTRAP_UNITS=%s\nFPC_BOOTSTRAP_TOOLS=%s\n' \
  "$bootstrap" "$units" "$tools_dir" >> "$GITHUB_ENV"
printf '%s\n' "Official FPC3.2.2 temporary extraction and native hello passed on $expected_arch." \
  'No installer/scripts or system configuration changes; observed DMG digest is recorded in logs.' >> "$GITHUB_STEP_SUMMARY"
