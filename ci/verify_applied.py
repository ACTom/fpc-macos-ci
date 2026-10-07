from pathlib import Path
import hashlib,json,sys
carrier=Path(__file__).resolve().parent.parent
manifest=json.loads((carrier/'payload/manifest.json').read_text())
source=Path(sys.argv[1]).resolve()
for entry in manifest['canonical_files']:
    data=(source/entry['path']).read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(data).hexdigest()==entry['sha256'], 'Applied source mismatch: '+entry['path']
print('PASS all',len(manifest['canonical_files']),'applied source files match the reviewed tree')
