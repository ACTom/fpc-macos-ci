#!/usr/bin/env python3
"""Fault-injection libraries test selection only; they never perform TLS.

Run in fresh processes. Production clients use existing backend libraries;
these stub fixtures deliberately expose enough entry points to isolate faults.
"""
import argparse
import json
import os
import pathlib
import platform
import re
import shutil
import struct
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--program', required=True)
    ap.add_argument('--compiler', required=True)
    ap.add_argument('--rtl', required=True)
    ap.add_argument('--sdk')
    args = ap.parse_args()
    source, out = pathlib.Path(args.source).resolve(), pathlib.Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    probe = (source / 'packages/fcl-tls/src/tlslibraryprobe.pp').read_text(encoding='utf-8')
    groups = re.findall(r'RequireProcs\([^;]+?\[([^]]+)\]\);', probe, re.S)
    assert len(groups) == 3
    crypto_names, ssl_names, gnu_names = [re.findall(r"'([^']+)'", group) for group in groups]
    ssl_names += ['SSL_get1_peer_certificate']
    # All legacy binding symbols avoid optional-load warnings in the Gnu fixture.
    gnu_names = sorted(set(gnu_names + re.findall(r"GPA\('([^']+)'\)",
        (source / 'packages/gnutls/src/gnutls.pp').read_text(encoding='utf-8'))))
    win, mac = sys.platform == 'win32', sys.platform == 'darwin'
    cpu = 'aarch64' if platform.machine().lower() in ['arm64', 'aarch64'] else 'x86_64'
    if win:
        ssl_name, crypto_name, gnu_name = 'libssl-3-x64.dll', 'libcrypto-3-x64.dll', 'libgnutls-30.dll'
    elif mac:
        ssl_name, crypto_name, gnu_name = 'libssl.3.dylib', 'libcrypto.3.dylib', 'libgnutls.30.dylib'
    else:
        ssl_name, crypto_name, gnu_name = 'libssl.so.3', 'libcrypto.so.3', 'libgnutls.so.30'
    built = out / 'mock-libraries'
    built.mkdir(exist_ok=True)

    def build(kind, names, filename, variant='normal', omit=None):
        folder = built / variant
        folder.mkdir(exist_ok=True)
        names = [n for n in names if n != omit]
        if win:
            lines = ['library fixture;', '{$mode objfpc}{$H+}', 'uses ctypes;']
            if kind == 'ssl':
                lines += [f"function CryptoVersion: culong; cdecl; external '{crypto_name}' name 'OpenSSL_version_num';"]
            exports = []
            for i, name in enumerate(names):
                fn = 'F' + str(i)
                if name == 'OpenSSL_version_num':
                    value = '$10101000' if variant == 'mixed' else '$30000000'
                    lines += [f'function {fn}: culong; cdecl; begin Result:={value} end;']
                elif name == 'gnutls_check_version':
                    result = 'nil' if variant == 'oldgnu' else "'3.8.0'"
                    lines += [f'function {fn}(Minimum: PAnsiChar): PAnsiChar; cdecl; begin Result:={result} end;']
                elif name == 'TLS_method':
                    lines += [f'function {fn}: Pointer; cdecl; begin Result:=Pointer(PtrUInt(CryptoVersion())) end;']
                else:
                    lines += [f'function {fn}: PtrInt; cdecl; begin Result:=0 end;']
                exports.append(f"{fn} name '{name}'")
            lines += ['exports ' + ',\n'.join(exports) + ';', 'begin end.']
            code = folder / (kind + '.pp')
            code.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            cmd = [args.compiler, '-n', '-Fu' + args.rtl, '-FU' + str(folder),
                   '-FE' + str(folder), '-o' + filename, str(code)]
        else:
            lines = ['#include <stddef.h>', '#include <stdint.h>']
            if kind == 'ssl':
                lines += ['extern unsigned long OpenSSL_version_num(void);']
            for name in names:
                if name == 'OpenSSL_version_num':
                    value = '0x10101000UL' if variant == 'mixed' else '0x30000000UL'
                    lines += [f'unsigned long {name}(void) {{ return {value}; }}']
                elif name == 'gnutls_check_version':
                    value = 'NULL' if variant == 'oldgnu' else '"3.8.0"'
                    lines += [f'const char *{name}(const char *minimum) {{ return {value}; }}']
                elif name == 'TLS_method':
                    lines += [f'void *{name}(void) {{ return (void *)(uintptr_t)OpenSSL_version_num(); }}']
                else:
                    lines += [f'long {name}(void) {{ return 0; }}']
            code = folder / (kind + '.c')
            code.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            cmd = ['cc', '-dynamiclib' if mac else '-shared', '-fPIC', str(code), '-o', str(folder / filename)]
            if mac:
                cmd += ['-Wl,-install_name,@rpath/' + filename, '-Wl,-rpath,@loader_path']
            if kind == 'ssl':
                cmd += [str(built / 'normal' / crypto_name)]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        (folder / (kind + '-build.log')).write_text(p.stdout, encoding='utf-8')
        if p.returncode:
            raise RuntimeError('Mock fixture build failed: ' + p.stdout)
        return folder / filename

    crypto = build('crypto', crypto_names, crypto_name)
    ssl = build('ssl', ssl_names, ssl_name)
    gnu = build('gnu', gnu_names, gnu_name)
    missing_ssl = build('ssl', ssl_names, ssl_name, 'missing', 'SSL_set1_host')
    mixed_crypto = build('crypto', crypto_names, crypto_name, 'mixed')
    old_gnu = build('gnu', gnu_names, gnu_name, 'oldgnu')
    cases = []
    native = 'schannel' if win else 'networkframework' if mac else 'error'

    def case(name, files=(), expected=native, preference='auto', mode='', diagnostic='', preload=(), cwd=None, app_relative=None):
        folder = out / name
        folder.mkdir(exist_ok=True)
        app = folder / (app_relative or ('application.exe' if win else 'application'))
        app.parent.mkdir(parents=True, exist_ok=True)
        app.write_bytes(b'fixture application location only\n')
        for src, target in files:
            destination = folder / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, destination)
        cmd = [str(pathlib.Path(args.program).resolve()), str(app), expected, preference, mode, diagnostic, *map(str, preload)]
        p = subprocess.run(cmd, cwd=cwd or folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        row = {'case': name, 'fixture_only': True, 'expected': expected, 'preference': preference,
               'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
        cases.append(row)
        print(('PASS' if p.returncode == 0 else 'FAIL'), name)
        return folder

    both = [(ssl, ssl_name), (crypto, crypto_name)]
    with_gnu = both + [(gnu, gnu_name)]
    case('no-bundled-libraries')
    case('openssl-before-gnu', with_gnu, 'openssl')
    case('gnu-before-native', [(gnu, gnu_name)], 'gnutls')
    case('openssl-lib-directory', [(ssl, 'lib/' + ssl_name), (crypto, 'lib/' + crypto_name)], 'openssl')
    case('explicit-native-ignores-bundled', with_gnu, native, native)
    case('explicit-gnu-override', with_gnu, 'gnutls', 'gnutls')
    case('explicit-openssl-override', with_gnu, 'openssl', 'openssl')
    case('explicit-openssl-absent', [], 'error', 'openssl', diagnostic='absent')
    case('explicit-gnu-absent', [], 'error', 'gnutls', diagnostic='absent')
    case('partial-ssl', [(ssl, ssl_name), (gnu, gnu_name)], 'error', diagnostic='Incomplete')
    case('partial-crypto', [(crypto, crypto_name), (gnu, gnu_name)], 'error', diagnostic='Incomplete')
    case('split-pair-directories', [(ssl, ssl_name), (crypto, 'lib/' + crypto_name)], 'error', diagnostic='Incomplete')
    damaged = built / 'damaged'
    damaged.write_bytes(b'not a native library')
    case('damaged-pair', [(damaged, ssl_name), (crypto, crypto_name), (gnu, gnu_name)], 'error', diagnostic='Truncated')
    case('missing-hostname-symbol', [(missing_ssl, ssl_name), (crypto, crypto_name), (gnu, gnu_name)], 'error', diagnostic='SSL_set1_host')
    case('mixed-version-pair', [(ssl, ssl_name), (mixed_crypto, crypto_name)], 'error', diagnostic='mismatched')
    case('old-gnu-version', [(old_gnu, gnu_name)], 'error', diagnostic='3.6.0')
    case('gnu-false-true-local-adapter', [(gnu, gnu_name)], 'gnutls', mode='gnuverification')
    case('concurrent-native', mode='threads')
    case('concurrent-openssl', both, 'openssl', mode='threads')
    case('concurrent-gnu', [(gnu, gnu_name)], 'gnutls', mode='threads')
    case('preinitialized-openssl', both, 'error', mode='preopenssl', diagnostic='earlier', preload=[ssl, crypto])
    case('preinitialized-gnu', [(gnu, gnu_name)], 'error', mode='pregnu', diagnostic='earlier', preload=[gnu])
    case('destroyed-openssl-no-reload', both, 'openssl', mode='destroyed')
    case('freed-gnu-no-reload', [(gnu, gnu_name)], 'gnutls', mode='destroyed')
    wrong = built / ('wrong-' + ssl_name)
    data = bytearray(ssl.read_bytes())
    if win:
        offset = struct.unpack_from('<I', data, 60)[0]
        struct.pack_into('<H', data, offset + 4, 0x14c)
    elif mac:
        struct.pack_into('<I', data, 4, 0x0100000c if cpu == 'x86_64' else 0x01000007)
    else:
        struct.pack_into('<H', data, 18, 3)
    wrong.write_bytes(data)
    case('wrong-architecture', [(wrong, ssl_name), (crypto, crypto_name)], 'error', diagnostic='architecture')
    foreign = case('foreign-current-directory', both, 'openssl')
    case('current-directory-not-bundled', cwd=foreign)
    invalid_type = out / 'library-directory'
    (invalid_type / ssl_name).mkdir(parents=True, exist_ok=True)
    case('library-directory', [(crypto, crypto_name)], 'error', diagnostic='regular file')
    if win:
        junction = out / 'outside-junction'
        junction.mkdir(exist_ok=True)
        p = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(junction/'lib'), str(built/'normal')],
                           capture_output=True, text=True, timeout=10)
        if p.returncode:
            raise RuntimeError('Junction fixture failed: '+p.stdout+p.stderr)
        case('outside-junction', expected='error', diagnostic='outside')
        wrong_import = built / ('wrong-import-'+ssl_name)
        original = ssl.read_bytes()
        assert original.count(crypto_name.encode()) == 1
        wrong_import.write_bytes(original.replace(crypto_name.encode(), crypto_name.replace('-3-', '-9-').encode()))
        case('mixed-import-pair', [(wrong_import, ssl_name), (crypto, crypto_name)], 'error', diagnostic='import pair mismatch')
    if mac:
        app_relative = 'Fixture.app/Contents/MacOS/application'
        case('mac-app-frameworks', [(ssl, 'Fixture.app/Contents/Frameworks/'+ssl_name),
             (crypto, 'Fixture.app/Contents/Frameworks/'+crypto_name)], 'openssl', app_relative=app_relative)
        case('mac-app-lib-gnu', [(gnu, 'Fixture.app/Contents/lib/'+gnu_name)],
             'gnutls', app_relative=app_relative)
        thin = ssl.read_bytes()
        cputype, subtype = struct.unpack_from('<II', thin, 4)
        def fat_image(name, fat64=False, architecture=None, invalid_bounds=False):
            magic = 0xcafebabf if fat64 else 0xcafebabe
            # Keep slices aligned for both Intel 4 KiB and Apple Silicon 16 KiB pages.
            offset = 16384
            size = len(thin) + (16384 if invalid_bounds else 0)
            entry = struct.pack('>IIQQII', architecture or cputype, subtype, offset, size, 14, 0) if fat64 else \
                    struct.pack('>IIIII', architecture or cputype, subtype, offset, size, 14)
            header = struct.pack('>II', magic, 1) + entry
            path = built / name
            path.write_bytes(header + b'\0' * (offset-len(header)) + thin)
            return path
        for fat64 in [False, True]:
            label = 'fat64' if fat64 else 'fat32'
            fat = fat_image(label, fat64=fat64)
            case('mach-'+label, [(fat, ssl_name), (crypto, crypto_name)], 'openssl')
        no_cpu = fat_image('fat-no-cpu', architecture=0x0100000c if cpu=='x86_64' else 0x01000007)
        case('mach-fat-missing-architecture', [(no_cpu, ssl_name), (crypto, crypto_name)],
             'error', diagnostic='matching Mach-O slice')
        bounds = fat_image('fat-invalid-bounds', invalid_bounds=True)
        case('mach-fat-invalid-bounds', [(bounds, ssl_name), (crypto, crypto_name)], 'error', diagnostic='bounds')
    if not win:
        folder = out / 'outside-symlink'
        folder.mkdir(exist_ok=True)
        (folder / ssl_name).symlink_to(ssl)
        (folder / crypto_name).symlink_to(crypto)
        case('outside-symlink', expected='error', diagnostic='outside')
    (out / 'results.json').write_text(json.dumps(cases, indent=2) + '\n', encoding='utf-8')
    failures = [row['case'] for row in cases if row['returncode']]
    print('RESULT', len(cases), 'selector cases;', len(failures), 'failed:', ','.join(failures))
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
