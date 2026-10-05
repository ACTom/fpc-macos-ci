from pathlib import Path
import hashlib, json, re
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'payload/manifest.json').read_text())
assert manifest['base_repository']=='https://gitlab.com/ACTom/source'
assert re.fullmatch('[0-9a-f]{40}',manifest['base_commit'])
patch=(root/'payload/native-tls.patch').read_bytes()
assert hashlib.sha256(patch).hexdigest()==manifest['patch_sha256'], 'Patch digest mismatch'
assert b'diff --git a/packages/fcl-tls/tests/macos/networkframework-api.c' in patch
assert b'diff --git a/packages/fcl-tls/ci/' not in patch, 'CI workflow leaked into FPC patch'
assert b'diff --git a/packages/fcl-tls/tests/macos/preflight.sh' not in patch, 'CI script leaked into FPC patch'
assert b'diff --git a/.github/workflows/' not in patch, 'GitHub workflow leaked into FPC patch'
print('PASS immutable payload' , manifest['base_commit'], manifest['patch_sha256'])
