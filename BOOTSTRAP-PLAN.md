# Proposed official Darwin bootstrap and one bounded run

The owner approved this exact temporary bootstrap and one additional manual
run. Before dispatch, no bootstrap binary has been downloaded/executed locally.

Approved scope: download/extract/run the official FPC 3.2.2 bootstrap only
inside the ephemeral runner's RUNNER_TEMP, then one manual workflow dispatch on
the existing macos-15-intel and macos-15 standard runners, at most 30 minutes
per job. There are no automatic reruns. This first stage covers compiler/RTL,
Blocks, pure Pascal native compilation/linking/imports/construction and, if
those pass, package integration and portable models. It starts no native TCP
connection and does not establish TLS/trust/hostname/lifetime acceptance.

## Fixed inputs

- FPC baseline and patch SHA256 are in payload/manifest.json. The existing
  workflow downloads exactly that GitLab source archive, verifies the patch
  hash and checks/applies payload/native-tls.patch. No FPC history is mirrored.
- [FPC's official download page](https://www.freepascal.org/down/i386/macosx.html)
  links to the [official SourceForge release directory](https://sourceforge.net/projects/freepascal/files/Mac%20OS%20X/3.2.2/).
  Use fpc-3.2.2.intelarm64-macosx.dmg, listed as 274.2 MB for Intel and ARM64.
- The 2021 release notes qualify macOS only through 11.x. Compatibility with
  the current macOS15 runners and Xcode SDK is unproven and must pass a bootstrap
  hello program before the source build. The source requires 3.2.2 or 3.2.0;
  do not override its version check.
- No independently verified published SHA256 is available from this inspection.
  Record the final download URL/headers and actual SHA256; that hash provides
  reproducibility, not an independent authenticity/signature claim.

## Temporary extraction, after authorization

Use the runner's existing curl, hdiutil and pkgutil. Download over HTTPS with
bounded connection/total deadlines and HTTPS-only redirects. Inspect the image
format and run hdiutil verify, then attach read-only, with no Finder auto-open.
Register an EXIT detach trap. Inventory the package layout before selecting a
single flat product pkg. pkgutil --expand-full extracts payloads; execute no
installer/Distribution/Scripts content. The actual image was inventoried in run37332944563: its mpkg wrapper contains
one nested flat pkg. That component can be extracted directly; no installer
or Distribution scripts are executed. Stop on ambiguous/unsupported layouts.

Illustrative commands (actual paths come from the inventory):

```sh
curl --fail --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 30 --max-time 300 \
  'https://sourceforge.net/projects/freepascal/files/Mac%20OS%20X/3.2.2/fpc-3.2.2.intelarm64-macosx.dmg/download' \
  --output "$RUNNER_TEMP/fpc-bootstrap.dmg"
shasum -a 256 "$RUNNER_TEMP/fpc-bootstrap.dmg"
hdiutil verify "$RUNNER_TEMP/fpc-bootstrap.dmg"
hdiutil attach -readonly -nobrowse -noautoopen \
  -mountpoint "$RUNNER_TEMP/fpc-mount" "$RUNNER_TEMP/fpc-bootstrap.dmg"
pkgutil --expand-full '<inventoried-flat-pkg>' "$RUNNER_TEMP/fpc-expanded"
```

Select the unique native ppcx64 (x86_64) or ppca64 (arm64), inspect file/lipo and
imports, and verify version/target. Locate its extracted units/<cpu>-darwin/rtl,
including system.ppu. Compile/run a hello program using -n, that explicit -Fu,
the existing xcrun macOS SDK via -XR, and existing linker/binutils via -FD.
Preserve the branch defaults: -WM10.8 for x86_64, -WM11.0 for arm64. Stop on
loader, extraction, linker or hello failures; do not provision Rosetta or bypass
OS policy. The package has not yet been inventoried, so those paths are not
claimed to be known.

Export FPC_BOOTSTRAP_COMPILER and FPC_BOOTSTRAP_UNITS for ci/preflight.sh. The
current script already accepts these inputs. The explicitly gated ci/bootstrap.sh now implements temporary extraction and
a native hello test; absent bootstrap still returns NOT RUN/exit77. No installer
is executed. The workflow also records the branch's own global/method Blocks tests.

## Build and evidence

ci/preflight.sh builds the branch compiler cycle, which builds matching RTL.
It then first compiles/runs testnetworknative.pp without the Windows-only
FPC_NETWORKFRAMEWORK_MODEL define, checks dynamic imports and Mach-O minimum
deployment commands, and only then builds packages and runs the stream/handler/
HTTP models plus concurrent native selector. FPC_NETWORK_FRAMEWORK_NATIVE is
explicitly enabled for this prototype. Do not link a C bridge object.

Inspect actual SDK Network/Security/dispatch headers alongside Pascal bool,
enum, pointer widths and cblocks. Record _NSConcreteStackBlock/GlobalBlock and
Block copy/release imports and the source compiler's existing Blocks tests.
A successful link on macOS15 does not establish runtime support on old macOS.
Fail if the linker silently raises the configured deployment minimum or adds
strong Network/Security/third-party TLS dependencies.

Keep per-architecture stage logs: runner/SDK, observed DMG hash, bootstrap hello,
compiler/RTL, native compile/link/import/construction, package build and models.
Report each as PASS, FAIL or NOT RUN. Bootstrap/compiler failures stop dependent
tests; exit77 never counts as PASS. Do not restart failed jobs automatically.

No sudo/installer/Homebrew, new SDK, Windows software, system trust/keychain,
global FPC configuration, account settings, Gatekeeper/SIP changes or paid
runner is part of this proposal. The repository's own Darwin build may use its
existing local binary signing/compare machinery; no keychain identity is needed.

Real TLS acceptance follows separately: trusted/invalid DNS/IP certificates,
Verify=False behavior, fragmented large data, HTTP connection counts/keep-alive,
timeouts and FIN without close_notify. Native lifetime tests must keep processes
alive and observe context destruction after late state/send/receive completion;
the current short close wait alone cannot prove eventual release or no leaks.

## Official bootstrap preflight outcome

[Run 37332944563](https://github.com/ACTom/fpc-macos-ci/actions/runs/37332944563)
tested carrier a870a1e2793b886660557e9572489478ef6b6ec5, patch digest
fbb3f5b5cac2fe3ced1938474a2d7a759ef610d4d4478031a7e8171a6b62e17a.
Both standard runners finished with failure on macOS15.7.9 / Xcode16.4.
Fixed-base patch application, official DMG download, hdiutil image verification
and pkgutil extraction passed. Both observed the same DMG SHA256:
05d4510c8c887e3c68de20272abf62171aa5b2ef1eba6bce25e4c0bc41ba8b7d.
This is the observed digest, not independent publisher-signature evidence.
The image contains an mpkg wrapper with one nested flat pkg; that payload was
extracted without installer scripts. Native compiler and matching RTL paths
were found on both architectures. No compiler was installed globally.

The bootstrap script incorrectly passed `lipo -verify_arch <arch> <file>`;
lipo treated the trailing filename as another architecture and exited 1.
The correction is `lipo <file> -verify_arch <arch>`, following the actual tool's
usage. It is prepared and shell syntax checked, not revalidated on macOS.
Version/target queries, bootstrap hello, compiler cycle/RTL, branch Blocks,
native compile/link/construction/imports and package/models were NOT RUN.
No native TLS connection occurred. Only the single newly authorized dispatch
was made; no automatic or manual retry followed this failure. Text evidence
was retained for each architecture. Existing Windows evidence remains unchanged.
