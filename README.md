# FPC macOS native TLS test carrier

This public repository carries the task patch, fixed FPC baseline and manual
CI orchestration. It does not mirror FPC history or publish an upstream PR.
No workflow/CI-only script is included in the FPC patch.

The current payload is the pure Pascal Network.framework prototype plus Windows
Schannel, deterministic selector and HTTP connection factory. The C exploration
is excluded. The real Darwin conditional code has not compiled/linked/run yet.
Windows package rebuild and complete offline regression pass: HTTP 40, handler
22, stream 20, shared state model zero leaks, loader/binding/state/deadline checks
and 87 real local TLS cases. These are not macOS ABI or HTTPS evidence.

Only workflow_dispatch is enabled. There are two standard runners,
macos-15-intel (x86_64) and macos-15 (arm64), with a proposed 30-minute bound per
job and fail-fast disabled. No push/PR/schedule trigger, automatic retry, larger
runner or software installer is configured. Updating this repository does not
dispatch a run. The owner has now approved one additional manual run with official temporary
bootstrap provisioning. No automatic retry is permitted.

ci/preflight.sh consumes an existing native Darwin FPC bootstrap (PATH or
FPC_BOOTSTRAP_COMPILER, with FPC_BOOTSTRAP_UNITS for a portable extract). Missing
FPC is explicit NOT RUN and exit 77. The separate opt-in ci/bootstrap.sh uses
the approved official 3.2.2 DMG, read-only mounting/pkgutil extraction and a
native hello test in RUNNER_TEMP; it executes no installer scripts. After
building the pinned branch compiler/RTL/packages, it compiles the pure Pascal
Darwin branch with FPC_NETWORK_FRAMEWORK_NATIVE, runs portable models, native
selector concurrency and a native construction harness, then records Mach-O
imports. It starts no native TCP/TLS connection and cannot establish trust,
hostname, truncation or eventual callback release. No C bridge is built.

[BOOTSTRAP-PLAN.md](BOOTSTRAP-PLAN.md) describes the official 3.2.2 package,
temporary-only extraction, exact approval scope and stop conditions. Before dispatch, the official bootstrap download/extraction code was prepared
and shell syntax checked locally; it was not executed on Windows. Mac15 compatibility of this
2021 bootstrap is unproven. A later TLS matrix must observe native context
release, late send/receive/state completions, DNS/IP trust, EOF/FIN and HTTP
connection counts before the backend can be offered as default.

## Earlier authorized run

[37319310587](https://github.com/ACTom/fpc-macos-ci/actions/runs/37319310587),
carrier 57c74fec6a0ff35c8cc93ee1a7702b20db793b95, tested the earlier C
exploration. Patch application, Apple API/Blocks construction and C object
compilation passed on both macOS15.7.9 architectures with SDK15.5/clang17.
Overall it failed at the C harness -Wstring-plus-int under -Werror. Neither runner
had FPC. This historical first run remains failed; the owner-approved second run uses
the pure Pascal payload and will be recorded separately. This is historical evidence only;
it does not verify the new Pascal branch. The public expired.badssl Windows
truncation failure also remains recorded, not counted as certificate rejection.

Updates are pushed through the owner's configured SSH key. Source repository
origin, account settings and key configuration are not changed.
