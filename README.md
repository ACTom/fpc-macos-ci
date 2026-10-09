# fpc-macos-ci

Runs the macOS TLS tests of a branch of https://gitlab.com/ACTom/source on GitHub's
macOS runners (x86_64 and arm64), because the work is done without a Mac.

Run:

    gh workflow run macos-tls.yml -R ACTom/fpc-macos-ci -f branch=feature/networkframework-peer-minimal

The job bootstraps FPC 3.2.2 (`ci/bootstrap.sh`), builds the compiler of the branch and
runs whichever of these tests exist in `packages/fcl-net/tests`: `thandlesconnect`,
`tsslselect all` and `testnetworkframework`.
