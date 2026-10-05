# FPC macOS native TLS test carrier

This repository carries a reviewed patch against FPC commit
56900cd3a58b32cf3c0f8a3b48443a139bab8e0d and manual CI orchestration.
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
complete package build, portable models, selector race and real TLS acceptance.
Existing Python ssl/OpenSSL are only fixture servers/certificate tools; native
Pascal clients assert no third-party TLS binding is loaded.

## Recorded runs

| Workflow | Both-architecture outcome |
| --- | --- |
| [37319310587](https://github.com/ACTom/fpc-macos-ci/actions/runs/37319310587) | Historical C exploration: API/Blocks/C object passed; C harness warning failed. No Pascal or TLS evidence. |
| [37332944563](https://github.com/ACTom/fpc-macos-ci/actions/runs/37332944563) | Download/image validation/extraction passed; lipo argument order failed. |
| [37336482398](https://github.com/ACTom/fpc-macos-ci/actions/runs/37336482398) | Bootstrap hello, branch compiler/RTL and Blocks passed; Assigned(cblock) native compile failed. |
| [37338838447](https://github.com/ACTom/fpc-macos-ci/actions/runs/37338838447) | Native compile/construction/context drain/import audit and all packages passed; standalone BSD include path failed. |
| [37340068774](https://github.com/ACTom/fpc-macos-ci/actions/runs/37340068774) | All build/model/race stages passed; 39 of 48 real TLS cases passed on each architecture. Seven assertion failures are corrected. Two bare FIN failures remain genuine. |

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
no default-enable claim is made while this limitation is unresolved. The next
round checks corrected assertions, send/handshake deadlines and installed SDK
public declarations. Full per-case results.json and stage logs are retained.

Windows evidence remains separate: full packages and offline suite passed,
including 87 real local TLS cases and loader/binding/SSPI/HTTP/stream models.
Public Windows expired.badssl early truncation remains a failure. Real GnuTLS,
OpenSSL1.1.1 and other Windows architectures/versions are untested.

See BOOTSTRAP-PLAN.md and the source patch's fcl-tls documentation for contracts
and reproducible tests. There are no push/PR/schedule triggers or automatic retries.
