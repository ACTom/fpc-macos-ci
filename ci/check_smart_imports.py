from pathlib import Path
import sys
data=Path(sys.argv[1]).read_text().lower()
for name in ['libssl','libcrypto','libgnutls','network.framework','security.framework']:
    assert name not in data, 'Unexpected strong TLS dependency: '+name
print('PASS smart native HTTP has no strong third-party/Network/Security TLS import')
