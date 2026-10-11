#!/usr/bin/env python3
"""Sign a complete MAR with owner NSS key, independently verify, and emit update.xml.

Only writes new output files. Requires Mozilla signmar and NSS certutil. No upload.
The input MAR must be produced by Firefox's make_full_update.sh (not a DMG/tarball).
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
from release_config import certificate, validate_host
from release_manifest import regular_file


def update_xml(version, build_id, url, size, digest):
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version) or not re.fullmatch(r'\d{14}', build_id):
        raise ValueError('Invalid release version or build ID')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment or parsed.port:
        raise ValueError('MAR URL must use HTTPS without credentials, port or fragment')
    validate_host(parsed.hostname or '')
    if not parsed.path.endswith('.mar') or size <= 0 or not re.fullmatch(r'[0-9a-f]{128}', digest):
        raise ValueError('Invalid complete MAR metadata')
    root = ET.Element('updates')
    update = ET.SubElement(root, 'update', type='minor', displayVersion=version, appVersion=version, buildID=build_id)
    ET.SubElement(update, 'patch', type='complete', URL=url, hashFunction='sha512', hashValue=digest, size=str(size))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def run(args):
    raw_cert = certificate(args.certificate)
    if args.output.exists() or args.xml.exists():
        raise ValueError('Output already exists')
    # Validate all public metadata before invoking signing.
    update_xml(args.version, args.build_id, args.url, 1, '0' * 128)
    with tempfile.TemporaryDirectory(prefix='cloakfox-mar-') as directory:
        root = Path(directory)
        source, signed = root / 'input.mar', root / 'signed.mar'
        with regular_file(args.input) as stream, source.open('wb') as target:
            while chunk := stream.read(1024 * 1024):
                target.write(chunk)
        subprocess.run([str(args.signmar), '-d', str(args.nss_db), '-n', args.nickname, '-s', str(source), str(signed)], check=True, timeout=120)
        cert = root / 'owner.der'
        cert.write_bytes(raw_cert)
        if args.verifier_backend == 'nss':
            db = root / 'verify-db'
            db.mkdir()
            subprocess.run([args.certutil, '-N', '-d', 'sql:' + str(db), '--empty-password'], check=True, capture_output=True, timeout=30)
            subprocess.run([args.certutil, '-A', '-d', 'sql:' + str(db), '-n', 'owner', '-t', ',,', '-i', str(cert)], check=True, capture_output=True, timeout=30)
            verify_args = ['-d', 'sql:' + str(db), '-n', 'owner']
        else:
            verify_args = ['-D', str(cert)]
        subprocess.run([str(args.signmar), *verify_args, '-v', str(signed)], check=True, timeout=120)
        info = subprocess.run([str(args.signmar), '-T', str(signed)], check=True, capture_output=True, text=True, timeout=30).stdout
        for label, value in [('MAR channel name', 'cloakfox-release'), ('Product version', args.version)]:
            if not re.search(r'^\s*- ' + label + ': ' + re.escape(value) + r'\s*$', info, re.M):
                raise ValueError('Signed MAR channel or product version mismatch')
        digest = hashlib.sha512()
        size = 0
        with signed.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        xml = update_xml(args.version, args.build_id, args.url, size, digest.hexdigest())
        with args.output.open('xb') as target, signed.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                target.write(chunk)
        with args.xml.open('xb') as target:
            target.write(xml)
    print('Owner-signed MAR verified and update.xml created. No files published.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('input', 'output', 'xml', 'signmar', 'nss-db', 'certificate'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('nickname', 'version', 'build-id', 'url'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--verifier-backend', choices=['nss', 'system'], required=True)
    p.add_argument('--certutil', default='certutil')
    try:
        run(p.parse_args())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        p.exit(1, f'Signed update blocked: {error}\n')
if __name__ == '__main__':
    main()
