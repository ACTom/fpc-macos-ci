# FPC macOS native TLS test carrier

Current payload: a minimal peer-hook + pure Pascal Network.framework patch against
FPC official main 2ec3f7a440e3c7b80cba4f7d2a7814c7bb36947b. Historical
records below concern the preserved full prototype and are not evidence for this
new interface. CI orchestration remains separate from the FPC patch.
It does not mirror FPC history or publish an upstream PR. Production code is
pure Pascal; no C bridge or CI workflow is included in the FPC source patch.

Only workflow_dispatch is enabled. Standard macos-15-intel and macos-15 runners
have a 30-minute job bound. The owner approved at most 20 cumulative workflow
executions, counting each matrix once and each rerun attempt separately.
Diagnose each failure before another dispatch, check exact remote/local SHA,
and supply expected_commit. Pushes use the owner's existing SSH key and do
not trigger CI. Source origin, accounts and key configuration are unchanged.

Official FPC3.2.2 provisioning is opt-in: the approved DMG is read-only mounted,
extracted by pkgutil into RUNNER_TEMP and unmounted without executing installer
scripts. No global installation or trust-store change occurs. The native
bootstrap hello is followed by the pinned branch compiler cycle/RTL, three
Blocks ABI programs, native provider compilation/construction, Mach-O audit,
complete package build, portable HTTP contract and real peer/TLS acceptance.
Existing Python ssl/OpenSSL are only fixture servers/certificate tools; native
Pascal clients assert no third-party TLS binding is loaded.

## Minimal peer run

[Run8](https://github.com/ACTom/fpc-macos-ci/actions/runs/37601884389), carrier
279df05e25650befd685d1ee3e6d5910819a6675, compiled the new interface and all
packages on both architectures, with Blocks/import/deployment/socket/ownership
checks passed. Intel passed all72 result rows (68 acceptance +4 EOF observations).
ARM passed71/72; only TLS1.3 reset failed at Connect with POSIX54 because the
server reset immediately after its handshake, before the client had published
ready. No production backend change is needed for that valid early-reset error.
The next payload keeps the assertion that Read must report reset as an error and
synchronizes the fixture on a flushed client-native-ready marker. Only two test
files change; no result or expectation is weakened. The original run8 results
remain retained. Usage is8/20 before any next dispatch.

Run9, carrier d89e3de88be2f996cbd0f188d5a9f03c6a71b46c, preserves all assertions.
Intel passed72/72. ARM passed69/72: every local/reset/public-peer case passed;
example.com True/False and wrong.host.badssl True hit POSIX60 Connect timeout.
These are failed acceptance rows, not certificate-validation evidence. Run8
had passed the same public controls with identical production code. The next
fixture adds DNS and existing system curl IPv4/IPv6 diagnostics only after a
native public failure; it does not retry or reclassify that native result.
Usage is9/20 before any next dispatch.

## Recorded runs

| Workflow | Both-architecture outcome |
| --- | --- |
| [37319310587](https://github.com/ACTom/fpc-macos-ci/actions/runs/37319310587) | Historical C exploration: API/Blocks/C object passed; C harness warning failed. No Pascal or TLS evidence. |
| [37332944563](https://github.com/ACTom/fpc-macos-ci/actions/runs/37332944563) | Download/image validation/extraction passed; lipo argument order failed. |
| [37336482398](https://github.com/ACTom/fpc-macos-ci/actions/runs/37336482398) | Bootstrap hello, branch compiler/RTL and Blocks passed; Assigned(cblock) native compile failed. |
| [37338838447](https://github.com/ACTom/fpc-macos-ci/actions/runs/37338838447) | Native compile/construction/context drain/import audit and all packages passed; standalone BSD include path failed. |
| [37340068774](https://github.com/ACTom/fpc-macos-ci/actions/runs/37340068774) | All build/model/race stages passed; 39 of 48 real TLS cases passed on each architecture. Seven assertion failures were corrected. Two bare FIN failures remain genuine. |
| [37341698834](https://github.com/ACTom/fpc-macos-ci/actions/runs/37341698834) | All build/model/race stages passed; 50 of 52 TLS cases passed per architecture. Send/handshake deadlines and corrected assertions pass; two bare FIN failures remain. |
| [37345498651](https://github.com/ACTom/fpc-macos-ci/actions/runs/37345498651) | All build/model/race stages passed; 56 of 58 TLS cases passed per architecture. Six HTTP framing cases pass. Two strict FIN failures remain; four separate diagnostics show matching clean-close/FIN signals. |

Both architectures ran macOS15.7.9, Xcode16.4/SDK15.5. Native Mach-O minimums
remain 10.8 (x86_64) and 11.0 (arm64), with no strong Network/Security or
third-party TLS dependency. This does not test old macOS runtime compatibility.

Round5 independently established actual HTTPS, TLS1.2/1.3, False/default/
after-create, True rejection, HTTP reuse, fragmented 1 MiB echo, read deadline,
Close/CanRead cancellation, proper EOF, RST and eventual context release.
Public expired.badssl True returned TLS -9814; False succeeded. Wrong-host,
self-signed and untrusted-root True returned the specific certificate code
-9808, omitted by the first harness. Callback vetoes also returned the correct
production error, but the harness expected different text. Neither fix changes
TLS verification or converts generic network failures into certificate passes.

Network.framework reports a bare TCP FIN without close_notify as error-free EOF
on this OS. That strict test remains failed. The source backend stays opt-in;
no default-enable claim is made while this limitation is unresolved. The seventh
run observes matching terminal fields for proper TLS close and bare FIN, even
after a 500ms delayed Read, under both TLS versions on both architectures.
Content-Length/chunked truncation now rejects explicitly. Close-delimited HTTP
and the raw stream's closure assurance require the owner's compatibility or
architecture decision. The public API/SDK inspection found no reliable closure
alert query in the interfaces used here. Full results.json and stage logs are
retained; diagnostic success does not satisfy strict truncation acceptance.

Seven workflows have run, each run_attempt=1, for cumulative usage 7/20. Current
payload documentation may include later evidence-only edits; round7 tested
carrier aeab39ed6134f5078a2f02e2c05bc474e4ca7198 and patch SHA256
2368ca71688b9c30363ab2d6589f7ebe3bc9a1471e3011760a4cfe930f0a2412.

Windows evidence remains separate: earlier complete offline suite passed with
87 real local TLS cases and loader/binding/SSPI/HTTP/stream models. The latest
HTTP framing package build and all 46 HTTP models pass. Its complete runner
passes all TLS cases but exits1 at a TemporaryDirectory cleanup permission
error after 17 loader checks passed; a targeted retained-directory loader run
exits0 with all17 and50 competing initializers. That does not erase the full
runner cleanup failure.
Public Windows expired.badssl early truncation remains a failure. Real GnuTLS,
OpenSSL1.1.1 and other Windows architectures/versions are untested.

See BOOTSTRAP-PLAN.md and the source patch's fcl-tls documentation for contracts
and reproducible tests. There are no push/PR/schedule triggers or automatic retries.
