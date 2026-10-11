#!/usr/bin/env python3
"""Prepare owner-authenticated native-updater inputs. Never publishes or signs.

Run only in an isolated, disposable release source tree after applying patches.
Windows activation is intentionally blocked pending vendor code-signing integration.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from release_manifest import bounded_read

def validate_host(host):
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', host):
        raise ValueError('Update host must be a plain public DNS hostname (HTTPS is enforced)')
    if host.endswith(('.mozilla.org', '.example.com', '.invalid', '.localhost', '.test', '.example')) or host in ('example.com', 'localhost', 'mozilla.org'):
        raise ValueError('Supply an owner-controlled update host')
    return host

def certificate(path):
    raw = bounded_read(path)
    proc = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-checkend', '2592000'], input=raw, capture_output=True, timeout=30)
    if proc.returncode:
        raise ValueError('MAR certificate must be valid DER and remain valid for at least 30 days')
    pub = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-pubkey', '-noout'], input=raw, capture_output=True, timeout=30, check=True)
    rsa = subprocess.run(['openssl', 'rsa', '-pubin', '-text', '-noout'], input=pub.stdout, capture_output=True, timeout=30)
    if rsa.returncode or not re.search(rb'\((?:2048|3072|4096) bit\)', rsa.stdout):
        raise ValueError('MAR certificates require a 2048/3072/4096-bit RSA key')
    return raw

def certificate_spki(raw):
    """Compare canonical public keys, independent of certificate serial/signature."""
    pub = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-pubkey', '-noout'],
                         input=raw, capture_output=True, timeout=30)
    if pub.returncode:
        raise ValueError('Cannot inspect MAR certificate trust key')
    der = subprocess.run(['openssl', 'pkey', '-pubin', '-outform', 'DER'],
                         input=pub.stdout, capture_output=True, timeout=30)
    if der.returncode or not der.stdout:
        raise ValueError('Cannot canonicalize MAR certificate trust key')
    return hashlib.sha256(der.stdout).hexdigest()


def prepare(args):
    if args.platform == 'windows':
        raise ValueError('Windows updater awaits owner code-signing integration')
    mac_options = []
    if args.platform == 'macos':
        team = getattr(args, 'mac_team_id', None) or ''
        identity = getattr(args, 'mac_signing_identity', None) or ''
        if not re.fullmatch(r'[A-Z0-9]{10}', team) or team == '43AQ936H96':
            raise ValueError('macOS requires an owner Apple Team ID; Mozilla trust is forbidden')
        if not re.fullmatch(r'Developer ID Application: [^\r\n]+ \(' + team + r'\)', identity):
            raise ValueError('macOS requires a Developer ID Application signing identity matching the owner Team ID')
        mac_options = ['export CLOAKFOX_MAC_TEAM_ID=' + team]
        configure = args.source / 'build/moz.configure/update-programs.configure'
        if 'CLOAKFOX_MAC_TEAM_ID' not in configure.read_text():
            raise ValueError('Apply the Cloakfox owner Team ID patch before configuring macOS releases')
    host = validate_host(args.host)
    certs = [certificate(args.primary), certificate(args.secondary)]
    trust_keys = [certificate_spki(raw) for raw in certs]
    if trust_keys[0] == trust_keys[1]:
        raise ValueError('Use distinct primary and rotation public keys')
    keyfile = args.provider_key.resolve()
    key = bounded_read(keyfile).strip()
    if keyfile.stat().st_mode & 0o077 or not re.fullmatch(rb'[A-Za-z0-9_-]{20,200}', key) or key.startswith(b'no-'):
        raise ValueError('Provider key file must be private (0600), non-placeholder and valid')
    source = args.source.resolve()
    config = source / 'mozconfig'
    original = config.read_text()
    if any(x in original for x in ['--enable-unverified-updates', '--enable-mac-elevated-updates-with-generic-certs']):
        raise ValueError('Unsafe updater configuration is forbidden')
    ini = source / 'build/application.ini.in'
    ini_text = ini.read_text()
    if 'https://@MOZ_APPUPDATE_HOST@/update/' not in ini_text:
        raise ValueError('Unexpected upstream update URL template')
    certdir = source / 'toolkit/mozapps/update/updater'
    for name in ['release_primary.der', 'release_secondary.der']:
        if not (certdir / name).is_file():
            raise ValueError('Missing native updater certificate input')
    bundled_keys = {certificate_spki(bounded_read(p)) for p in certdir.glob('*.der')}
    if any(key in bundled_keys for key in trust_keys):
        raise ValueError('Owner MAR certificates must not reuse bundled upstream or test trust roots')
    # All validation precedes mutation; only an explicitly supplied release tree is changed.
    for name, raw in zip(['release_primary.der', 'release_secondary.der'], certs):
        (certdir / name).write_bytes(raw)
    ini.write_text(ini_text.replace('https://@MOZ_APPUPDATE_HOST@/update/', f'https://{host}/update/'))
    config.write_text(original.replace('ac_add_options --disable-updater', '') + '\n' + '\n'.join([
        'ac_add_options --enable-updater', 'ac_add_options --disable-unverified-updates',
        'ac_add_options --enable-update-channel=release',
        'export MAR_CHANNEL_ID=cloakfox-release', 'export ACCEPTED_MAR_CHANNEL_IDS=cloakfox-release',
        'ac_add_options ' + shlex.quote('--with-google-safebrowsing-api-keyfile=' + str(keyfile)), *mac_options, '']))
    receipt = dict(schema=1, platform=args.platform, host=host, channel='cloakfox-release',
                   certificates_sha256=[hashlib.sha256(c).hexdigest() for c in certs],
                   provider_key_supplied=True, production_ready=False,
                   mac_team_id=getattr(args, 'mac_team_id', None),
                   mac_signing_identity=getattr(args, 'mac_signing_identity', None),
                   remaining=['Build and verify MOZ_VERIFY_MAR_SIGNATURE', 'Sign MARs with owner NSS key',
                              'Verify updater tamper, wrong-key and rollback probes',
                              'Publish HTTPS update.xml and signed MARs', 'Verify real provider list downloads'])
    (source / 'cloakfox-release-inputs.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Release inputs installed. Activation still requires built-updater and hosting validation.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--platform', choices=['linux','macos','windows'], required=True)
    p.add_argument('--host', required=True)
    p.add_argument('--mac-team-id')
    p.add_argument('--mac-signing-identity')
    p.add_argument('--primary', type=Path, required=True)
    p.add_argument('--secondary', type=Path, required=True)
    p.add_argument('--provider-key', type=Path, required=True)
    try:
        prepare(p.parse_args())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        p.exit(1, f'Release configuration blocked: {error}\n')
if __name__ == '__main__':
    main()
