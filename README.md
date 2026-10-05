# FPC macOS native TLS test carrier

This repository carries only the task patch, exact source baseline and a bounded
manual CI workflow. All workflows and CI-only orchestration live in this
repository, outside the FPC patch. It does not mirror FPC history or publish an
upstream PR.

The owner's repository is public. First-run conditions: exactly two standard
GitHub-hosted jobs, `macos-15-intel` (x86_64) and `macos-15` (arm64), each with a
15-minute timeout. Only `workflow_dispatch` is enabled; no push, PR or schedule
trigger exists. A concurrency group prevents simultaneous duplicate runs.
The owner has authorized one first manual dispatch after a successful upload.
Further runs are not scheduled automatically. No run is requested
by committing/pushing this payload.

The patch SHA256 and FPC base commit are fixed in `payload/manifest.json`. Each
job downloads one source snapshot at that commit, checks/applies the patch, and
uses the runner's installed Xcode SDK/clang to build and execute an API/Blocks
construction probe, and compiles/constructs the production C bridge. No TCP/TLS
connection is started. No compiler, SDK or package is installed. Existing FPC, if
present, is inventoried; its absence is explicitly reported.

**This stage is not FPC native HTTPS acceptance.** The probe never starts a TCP
or TLS connection. Trust, hostname verification, stream ownership, cancellation,
late callbacks and Pascal runtime tests remain future stages. See the applied
patch's `packages/fcl-tls/docs/macos-transport.md` for the connection seam audit
and required next tests. A compatible Darwin bootstrap compiler/RTL remains a
provisioning requirement before an actual FPC build can run.

Windows validation: package build and complete offline runner exit 0; 87 real
local TLS cases passed. A bounded native online recheck retains one early TCP
truncation at expired.badssl.com as failure; it is not certificate rejection.
No real GnuTLS runtime or macOS runtime claim is made.

The standard macOS labels are documented at
https://docs.github.com/en/actions/reference/runners/github-hosted-runners
and are free for public repositories. No larger/paid runner is configured.

The standalone Pascal connection layer now passes 20 Windows ABI model cases.
This is state/ownership evidence only. The first preflight also builds the
production C object and no-argument native harness; full native TLS fixture
modes are not started by this workflow. FPC native stream linking and the HTTP
transport seam remain later stages. SSH access authenticates as ACTom; HTTPS
token push was denied, without identifying a specific missing token permission.

## First manual run

[37319310587](https://github.com/ACTom/fpc-macos-ci/actions/runs/37319310587)
failed on both architectures at the native C test harness compile: clang 17
-Wstring-plus-int rejected a string-literal offset expression under -Werror.
Payload application, direct Apple API/Blocks construction and production C
bridge object compilation passed on both architectures with the installed
macOS 15.5 SDK. The expression has been corrected using a named array; its
macOS revalidation and bridge runtime remain pending. Neither runner provided
an existing FPC bootstrap. No new software was installed, and no second run has
been requested. The first tested carrier commit is 57c74fec6a0ff35c8cc93ee1a7702b20db793b95.
The source download uses HTTPS; the native construction probes open no connection.
