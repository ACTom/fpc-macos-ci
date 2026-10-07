"""macOS native TLS acceptance, using existing Python ssl/OpenSSL only as servers.

The Pascal clients load system Network/Security, never the fixture's TLS library.
All certificates are disposable; this script does not change any trust store.
Public negative controls isolate hostname/expiry; private fixtures test untrusted
chains and Verify=False, and cannot isolate a hostname/expiry trust failure.
Each case is run once and its full result retained, including early TCP failures.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import struct
import subprocess
import threading
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('native', type=Path)
    parser.add_argument('http', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--peer', type=Path, required=True)
    args = parser.parse_args()
    args.native, args.http = args.native.resolve(), args.http.resolve()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    openssl_path = shutil.which('openssl')
    if not openssl_path:
        raise SystemExit('Existing OpenSSL CLI is required only to generate disposable server fixtures')
    results = []

    def save():
        (root / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

    def openssl(*parts):
        completed = subprocess.run([openssl_path, *map(str, parts)], capture_output=True,
                                   text=True, timeout=30)
        if completed.returncode:
            raise RuntimeError(f'Fixture command {parts[0]} failed: {completed.stderr}')
        return completed.stdout

    print('SERVER_ONLY Python', ssl.OPENSSL_VERSION, 'CLI', openssl('version').strip(), flush=True)
    config = root / 'root.conf'
    config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n'
                      '[dn]\nCN=FPC disposable native TLS root\n[ca]\n'
                      'basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
    openssl('req', '-new', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '3',
            '-config', config, '-keyout', root / 'root.key', '-out', root / 'root.pem')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', root / 'server.key', '-out', root / 'server.csr')
    for index, (name, san) in enumerate((('valid', 'DNS:localhost,IP:127.0.0.1'),
                                        ('wrong-dns', 'DNS:another.invalid')), 1):
        ext = root / f'{name}.ext'
        ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
                       'extendedKeyUsage=serverAuth\nsubjectAltName=' + san + '\n')
        openssl('x509', '-req', '-in', root / 'server.csr', '-CA', root / 'root.pem',
                '-CAkey', root / 'root.key', '-set_serial', index, '-days', '2',
                '-extfile', ext, '-out', root / f'{name}.pem')
    (root / 'chain.pem').write_bytes((root / 'valid.pem').read_bytes() + (root / 'root.pem').read_bytes())
    (root / 'index.txt').write_text('')
    (root / 'serial').write_text('1000\n')
    config.write_text(f'[ca]\ndefault_ca=test\n[test]\ndir="{root.as_posix()}"\n'
                      'database=$dir/index.txt\nserial=$dir/serial\nnew_certs_dir=$dir\n'
                      'certificate=$dir/root.pem\nprivate_key=$dir/root.key\ndefault_md=sha256\n'
                      'policy=policy\nunique_subject=no\n[policy]\ncommonName=supplied\n')
    now = datetime.now(timezone.utc)
    openssl('ca', '-batch', '-notext', '-config', config, '-in', root / 'server.csr',
            '-extfile', root / 'valid.ext', '-startdate', (now-timedelta(days=2)).strftime('%Y%m%d%H%M%SZ'),
            '-enddate', (now-timedelta(days=1)).strftime('%Y%m%d%H%M%SZ'), '-out', root / 'expired.pem')

    def execute(name, command, observed=None, ready=None):
        row = {'case': name, 'diagnostic_only': 'observation' in name, **(observed or {})}
        try:
            if ready is None:
                run = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=25)
            else:
                process = subprocess.Popen(list(map(str, command)), stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True)
                output, errors = [], []
                def collect(stream, target):
                    for line in stream:
                        target.append(line)
                        if stream is process.stdout and line.strip() == 'FIXTURE_READY_RESET':
                            ready.set()
                readers = [threading.Thread(target=collect, args=(process.stdout, output)),
                           threading.Thread(target=collect, args=(process.stderr, errors))]
                for reader in readers:
                    reader.start()
                try:
                    process.wait(timeout=25)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    for reader in readers:
                        reader.join(2)
                run = SimpleNamespace(returncode=process.returncode,
                                      stdout=''.join(output), stderr=''.join(errors))
            row.update(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
        except subprocess.TimeoutExpired as exc:
            row.update(returncode=-1, error=str(exc))
        results.append(row)
        save()
        label = ('DIAGNOSTIC' if row['diagnostic_only'] else 'PASS') if row['returncode'] == 0 else 'FAIL'
        print(label, name,
              row.get('stdout', '').strip().replace('\n', ' | '), row.get('stderr', '').strip(), flush=True)
        return row

    def local(name, mode='http', certificate='valid', verify='false', callback='true',
              after='false', expected='pass', calls=1, requests=1, tls='tls12', framing=None, body_mode=None, peer=False):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(15)
        port = listener.getsockname()[1]
        stop = threading.Event()
        ready = threading.Event() if mode == 'reset' else None
        observed = {'tls': tls, 'certificate': certificate, 'accepted': 0, 'requests': 0,
                    'framing': framing, 'methods': [],
                    'category': 'EOF_compatibility' if framing else 'tls_behavior'}
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        version = ssl.TLSVersion.TLSv1_2 if tls == 'tls12' else ssl.TLSVersion.TLSv1_3
        context.minimum_version = context.maximum_version = version
        context.load_cert_chain(root / f'{certificate}.pem', root / 'server.key')

        def serve():
            try:
                connection, _ = listener.accept()
                observed['accepted'] += 1
                connection.settimeout(12)
                if mode == 'connecttimeout':
                    stop.wait(12)
                    connection.close()
                    return
                with context.wrap_socket(connection, server_side=True) as secure:
                    observed['handshake'] = secure.version()
                    if mode == 'http':
                        data = b''
                        for _ in range(requests):
                            while b'\r\n\r\n' not in data:
                                chunk = secure.recv(4096)
                                if not chunk:
                                    return
                                data += chunk
                            header, data = data.split(b'\r\n\r\n', 1)
                            observed['requests'] += 1
                            observed['methods'].append(header.split(b' ', 1)[0].decode('ascii'))
                            body = b'native tls fixture\n'
                            if framing in ('close-clean', 'close-fin'):
                                response = b'HTTP/1.1 200 OK\r\nConnection: close\r\n\r\n'+body
                            else:
                                response = b'HTTP/1.1 200 OK\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: keep-alive\r\n\r\n'+body
                            for offset in range(0, len(response), 7):
                                secure.sendall(response[offset:offset+7])
                            if framing == 'close-fin':
                                fd = secure.detach()
                                with socket.socket(fileno=fd) as raw:
                                    raw.shutdown(socket.SHUT_WR)
                                observed['bare_fin_after_http'] = True
                                return
                            if framing == 'close-clean':
                                observed['close_notify_attempted'] = True
                                secure.unwrap().close()
                                return
                    elif mode == 'echo':
                        while not stop.is_set():
                            data = secure.recv(4096)
                            if not data:
                                break
                            for offset in range(0, len(data), 113):
                                secure.sendall(data[offset:offset+113])
                    elif mode in ('eof', 'reset', 'finobserve', 'eofobserve'):
                        if mode in ('eof', 'eofobserve'):
                            secure.sendall(b'abc')
                            secure.unwrap().close()
                        else:
                            fd = secure.detach()
                            with socket.socket(fileno=fd) as raw:
                                if mode == 'reset':
                                    if not ready.wait(5):
                                        observed['fixture_error'] = 'Client ready marker missing before reset'
                                        return
                                    observed['client_ready_before_reset'] = True
                                    raw.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                                else:
                                    raw.shutdown(socket.SHUT_WR)
                    elif mode == 'timeout':
                        if not stop.wait(0.15):
                            observed['late_send_attempt'] = True
                            secure.sendall(b'late-data')
                    else:
                        stop.wait(12)
            except (ssl.SSLError, OSError) as exc:
                observed['server_error'] = str(exc)
            finally:
                listener.close()

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        if mode == 'http':
            command = [args.http, f'https://localhost:{port}/', verify, callback, after,
                       expected, calls, body_mode or 'local', requests]
        else:
            command = [args.peer if peer else args.native, 'localhost', port, '0', mode]
        row = execute(name, command, ready=ready)
        stop.set()
        worker.join(2)
        listener.close()
        row.update(observed)
        if worker.is_alive() or observed['accepted'] != 1:
            row['fixture_error'] = 'server thread did not stop or connection missing'
            row['returncode'] = -1
        if expected == 'pass' and mode == 'http' and observed['requests'] != requests:
            row['fixture_error'] = 'unexpected number of HTTP requests'
            row['returncode'] = -1
        if expected in ('certificate', 'veto') and observed['requests']:
            row['fixture_error'] = 'application bytes sent after rejection'
            row['returncode'] = -1
        if mode == 'http' and observed['requests'] and observed['methods'] != ['HEAD' if body_mode == 'head' else 'GET'] * observed['requests']:
            row['fixture_error'] = 'unexpected HTTP request method'
            row['returncode'] = -1
        save()

    for tls in ('tls12', 'tls13'):
        if tls == 'tls13' and not ssl.HAS_TLSv1_3:
            results.append({'case': 'tls13-support', 'returncode': -1, 'error': 'fixture lacks TLS 1.3'})
            continue
        local(tls+'-http-default', verify='default', tls=tls)
        for cert in ('valid', 'wrong-dns', 'expired', 'chain'):
            local(tls+'-'+cert+'-false', certificate=cert, tls=tls)
            local(tls+'-'+cert+'-true-reject', certificate=cert, verify='true', expected='certificate', calls=0, tls=tls)
        local(tls+'-after-create-false', verify='true', after='true', tls=tls)
        local(tls+'-callback-veto', callback='false', expected='veto', tls=tls)
        local(tls+'-http-keepalive', requests=2, tls=tls)
        local(tls+'-fin-observation', mode='finobserve', tls=tls)
        local(tls+'-eof-observation', mode='eofobserve', tls=tls)
        for framing in ('close-clean', 'close-fin'):
            local(tls+'-'+framing+'-compatibility', framing=framing, tls=tls)
        for mode in ('echo', 'timeout', 'writetimeout', 'connecttimeout', 'close', 'canclose', 'eof', 'reset'):
            local(tls+'-'+mode, mode=mode, tls=tls)
        for mode in ('echo', 'timeout', 'close', 'canclose', 'destroy', 'callbackclose', 'callbackreenter'):
            local(tls+'-peer-'+mode, mode=mode, peer=True, tls=tls)
    # Public controls use the runner's system trust unchanged. Both settings run
    # even if one fails, so a connection failure cannot be mislabeled validation.
    for host in ('example.com', 'wrong.host.badssl.com', 'expired.badssl.com', 'self-signed.badssl.com', 'untrusted-root.badssl.com'):
        for verify in ('true', 'false'):
            expected = 'pass' if host == 'example.com' or verify == 'false' else 'certificate'
            row = execute('public-'+host+'-'+verify, [args.http, f'https://{host}/', verify, 'true', 'false', expected,
                                                     1 if expected == 'pass' else 0, 'public', 1])
            if row['returncode'] != 0:
                # A reference probe diagnoses a failing runner; it never changes
                # native acceptance, retries that client, or counts validation.
                controls = {}
                try:
                    controls['addresses'] = sorted({item[4][0] for item in
                        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
                except OSError as exc:
                    controls['dns_error'] = str(exc)
                curl = Path('/usr/bin/curl')
                if curl.is_file():
                    for flag in ('-4', '-6'):
                        try:
                            control = subprocess.run([str(curl), flag, '--head', '--silent',
                                '--show-error', '--noproxy', '*', '--connect-timeout', '5',
                                '--max-time', '8', f'https://{host}/'], capture_output=True,
                                text=True, timeout=10)
                            controls[flag] = {'exit': control.returncode,
                                             'stdout': control.stdout, 'stderr': control.stderr}
                        except subprocess.TimeoutExpired as exc:
                            controls[flag] = {'timeout': str(exc)}
                row['public_network_diagnostics'] = controls
                print('PUBLIC FAILURE DIAGNOSTIC', row['case'], json.dumps(controls), flush=True)
                save()
    save()
    failures = [row['case'] for row in results if row.get('returncode') != 0]
    acceptance = [row for row in results if not row.get('diagnostic_only')]
    diagnostic = [row for row in results if row.get('diagnostic_only')]
    print('RESULT', len(acceptance), 'supported-feature acceptance cases;', sum(row['returncode'] != 0 for row in acceptance),
          'failed;', len(diagnostic), 'EOF compatibility observations;',
          len(failures), 'unexpected failures:', ', '.join(failures), flush=True)
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
