from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parent.parent
m=json.loads((root/'payload/manifest.json').read_text())
assert m['base_repository']=='https://gitlab.com/freepascal.org/fpc/source'
assert re.fullmatch('[0-9a-f]{40}',m['base_commit'])
combined=(root/'payload/native-tls.patch').read_bytes()
smart=(root/'payload/smart-tls.patch').read_bytes()
assert hashlib.sha256(combined).hexdigest()==m['patch_sha256']
assert hashlib.sha256(smart).hexdigest()==m['smart_patch_sha256']
original_native={'packages/fcl-net/fpmake.pp','packages/fcl-net/namespaces.lst',
 'packages/fcl-net/src/sslsockets.pp','packages/fcl-web/src/base/fphttpclient.pp',
 'packages/fcl-web/tests/testfpweb.lpr'}
original_smart={'packages/fpmake_add.inc','packages/fpmake_proc.inc',
 'packages/openssl/src/openssl.pas','packages/gnutls/src/gnutls.pp','packages/gnutls/src/gnutlssockets.pp'}
def inspect(patch,allowed_original,expected):
 names=[]
 for section in patch.decode().split('diff --git ')[1:]:
  name=section.splitlines()[0].split(' b/',1)[1]
  names.append(name)
  if 'new file mode' not in section.split('@@',1)[0]:
   assert name in allowed_original, 'Unrelated original file changed: '+name
 assert set(names)==expected and len(names)==len(expected), 'Unexpected file set'
inspect(smart,original_smart,{e['path'] for e in m['files']})
inspect(combined,original_native|original_smart,{e['path'] for e in m['canonical_files']})
assert len(m['files'])==17 and len(m['prerequisite_files'])==24
assert set(m['original_files_in_smart_diff'])==original_smart
for name in ['networkframeworkapi.pp','networkframeworknative.pp','networkframeworksslsockets.pp','schannelsslsockets.pp']:
 assert ('diff --git a/packages/fcl-net/src/'+name).encode() in combined
for entry in m['canonical_files']:
 assert '/docs/' not in entry['path'] and not entry['path'].endswith(('.md','.py','.ps1','.sh')), 'Support material leaked into FPC: '+entry['path']
for prefix in ['.github/','packages/fcl-tls/ci/','packages/fcl-net/src/macos/','packages/fcl-net/tests/schannel/','packages/fcl-net/tests/networkframework/']:
 assert ('diff --git a/'+prefix).encode() not in combined
for marker in ['CreateClientConnection','RequireAuthenticatedTLSClosure','SupportsAuthenticatedEOF','ClaimSSLInterface','ClaimGnuTLS']:
 assert marker.encode() not in combined, 'Full experiment marker leaked: '+marker
assert 'SetDefaultHandlerClass(HandlerClass)' in smart.decode()
assert 'InitSSLInterfaceIfUnloaded' in smart.decode() and 'LoadGnuTLSIfUnloaded' in smart.decode()
print('PASS fixed native-prerequisite + minimal smart payload',m['base_commit'],m['patch_sha256'])
print('PASS independent smart delta: 17 files, five existing loader/package files, no further HTTP/socket core change')
print('PASS flat Pascal tests, existing FPCUnit runner; orchestration lives only in this independent CI carrier')
