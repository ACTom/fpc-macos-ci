from pathlib import Path
import hashlib, json, re
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'payload/manifest.json').read_text())
assert manifest['base_repository']=='https://gitlab.com/ACTom/source'
assert re.fullmatch('[0-9a-f]{40}',manifest['base_commit'])
patch=(root/'payload/native-tls.patch').read_bytes()
assert hashlib.sha256(patch).hexdigest()==manifest['patch_sha256'], 'Patch digest mismatch'
for name in ['networkframeworkapi.pp','networkframeworknative.pp','networkframeworksslsockets.pp']:
    assert ('diff --git a/packages/fcl-tls/src/'+name).encode() in patch
for name in ['networkframeworkbridge.c','networkframeworkbridge.h','networkframework-api.c','testnetworkbridge.c']:
    assert ('diff --git a/packages/fcl-tls/src/macos/'+name).encode() not in patch
    assert ('diff --git a/packages/fcl-tls/tests/macos/'+name).encode() not in patch
for path in ['packages/fcl-tls/ci/','packages/fcl-tls/tests/macos/preflight.sh','.github/workflows/']:
    assert ('diff --git a/'+path).encode() not in patch, 'CI orchestration leaked into FPC patch'
print('PASS fixed pure Pascal payload',manifest['base_commit'],manifest['patch_sha256'])
