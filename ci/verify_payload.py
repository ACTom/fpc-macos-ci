from pathlib import Path
import hashlib, json, re
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'payload/manifest.json').read_text())
assert manifest['base_repository']=='https://gitlab.com/freepascal.org/fpc/source'
assert re.fullmatch('[0-9a-f]{40}',manifest['base_commit'])
patch=(root/'payload/native-tls.patch').read_bytes()
assert hashlib.sha256(patch).hexdigest()==manifest['patch_sha256'], 'Patch digest mismatch'
for name in ['networkframeworkapi.pp','networkframeworknative.pp','networkframeworksslsockets.pp']:
    assert ('diff --git a/packages/fcl-net/src/'+name).encode() in patch
for name in ['networkframeworkbridge.c','networkframeworkbridge.h','networkframework-api.c','testnetworkbridge.c']:
    assert ('diff --git a/packages/fcl-net/src/macos/'+name).encode() not in patch
    assert ('diff --git a/packages/fcl-tls/tests/macos/'+name).encode() not in patch
for path in ['packages/fcl-tls/ci/','packages/fcl-tls/tests/macos/preflight.sh','.github/workflows/']:
    assert ('diff --git a/'+path).encode() not in patch, 'CI orchestration leaked into FPC patch'
print('PASS fixed pure Pascal payload',manifest['base_commit'],manifest['patch_sha256'])

allowed_existing={'packages/fcl-net/fpmake.pp','packages/fcl-net/namespaces.lst',
                  'packages/fcl-net/src/sslsockets.pp','packages/fcl-web/src/base/fphttpclient.pp'}
for section in patch.decode().split('diff --git ')[1:]:
    name=section.splitlines()[0].split(' b/',1)[1]
    if 'new file mode' not in section.split('@@',1)[0]:
        assert name in allowed_existing, 'Unrelated original file changed: '+name
for marker in ['smartsslsockets','tlsbackendpolicy','RequireAuthenticatedTLSClosure',
               'CreateClientConnection','SupportsAuthenticatedEOF']:
    assert marker.encode() not in patch, 'Prototype scope leaked: '+marker
print('PASS four-original-file minimal scope; no smart/strict EOF/legacy backend edits')
