#!/usr/bin/env python3
"""Create unsigned release metadata or verify local artifacts using OpenSSL.

No downloads, signing keys, extraction, installation or browser updater changes.
Trust root and minimum sequence must come from a separate trusted source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time

MAX_METADATA = 64 * 1024
MAX_LIFETIME = 30 * 24 * 3600
FIELDS = {'schema', 'product', 'version', 'sequence', 'platform', 'channel',
          'issued_at', 'expires_at', 'filename', 'size', 'sha256'}


def regular_file(path):
    # Reject symlinks and special files before reading. O_NOFOLLOW also closes
    # the lstat/open race on supported systems; fstat checks the opened object.
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'{path.name}: expected regular file (no symlink)')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    stream = os.fdopen(descriptor, 'rb')
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ValueError(f'{path.name}: expected regular file')
    return stream


def bounded_read(path):
    with regular_file(path) as stream:
        data = stream.read(MAX_METADATA + 1)
    if len(data) > MAX_METADATA:
        raise ValueError(f'{path.name}: metadata too large')
    return data


def package_digest(path):
    digest = hashlib.sha256()
    size = 0
    with regular_file(path) as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate metadata field: {key}')
        result[key] = value
    return result


def validate(metadata, now):
    if not isinstance(metadata, dict) or set(metadata) != FIELDS:
        raise ValueError('unexpected manifest fields')
    if type(metadata['schema']) is not int or metadata['schema'] != 1 or metadata['product'] != 'Cloakfox':
        raise ValueError('unsupported schema or product')
    for key in ('sequence', 'size', 'issued_at', 'expires_at'):
        if type(metadata[key]) is not int or metadata[key] <= 0:
            raise ValueError(f'invalid {key}')
    for key in ('version', 'platform', 'channel'):
        if not isinstance(metadata[key], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', metadata[key]):
            raise ValueError(f'invalid {key}')
    if not isinstance(metadata['filename'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}', metadata['filename']):
        raise ValueError('invalid filename: only a plain artifact basename is allowed')
    if not isinstance(metadata['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', metadata['sha256']):
        raise ValueError('invalid sha256')
    if metadata['issued_at'] > now:
        raise ValueError('manifest issued in the future')
    if metadata['expires_at'] <= now:
        raise ValueError('manifest expired')
    if not 0 < metadata['expires_at'] - metadata['issued_at'] <= MAX_LIFETIME:
        raise ValueError('manifest lifetime must be positive and at most 30 days')


def create(args):
    size, digest = package_digest(args.package)
    metadata = dict(schema=1, product='Cloakfox', version=args.version,
                    sequence=args.sequence, platform=args.platform, channel=args.channel,
                    issued_at=int(time.time()), expires_at=args.expires_at,
                    filename=args.package.name, size=size, sha256=digest)
    validate(metadata, int(time.time()))
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(metadata, sort_keys=True, indent=2) + '\n')
    print('Created UNSIGNED release manifest; owner signature required.')


def verify(args):
    if args.minimum_sequence <= 0:
        raise ValueError('minimum sequence must be a trusted positive integer')
    try:
        key = bounded_read(args.public_key)
    except (OSError, ValueError) as error:
        raise ValueError('owner public key missing or invalid; signing configuration required') from error
    raw = bounded_read(args.manifest)
    signature = bounded_read(args.signature)
    # Snapshot key/signature bytes into private temporary files, so OpenSSL and
    # the metadata parser operate on the same bytes even if downloads change.
    with tempfile.TemporaryDirectory(prefix='cloakfox-verify-') as directory:
        key_path = Path(directory) / 'public.pem'
        sig_path = Path(directory) / 'manifest.sig'
        key_path.write_bytes(key)
        sig_path.write_bytes(signature)
        try:
            result = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(key_path),
                                     '-signature', str(sig_path)], input=raw, capture_output=True, timeout=30)
        except FileNotFoundError as error:
            raise ValueError('OpenSSL is required for signature verification') from error
        if result.returncode:
            raise ValueError('manifest signature verification failed (or invalid public key)')
    metadata = json.loads(raw, object_pairs_hook=unique_object)
    validate(metadata, int(time.time()))
    for key in ('platform', 'channel'):
        if metadata[key] != getattr(args, key):
            raise ValueError(f'{key} mismatch')
    if metadata['sequence'] < args.minimum_sequence:
        raise ValueError('release sequence is older than the trusted minimum')
    if metadata['filename'] != args.package.name:
        raise ValueError('package filename mismatch')
    size, digest = package_digest(args.package)
    if size != metadata['size'] or digest != metadata['sha256']:
        raise ValueError('package size or SHA-256 mismatch')
    print(f"Local package verified: {metadata['version']} ({metadata['platform']}, "
          f"{metadata['channel']}, sequence {metadata['sequence']}). No update installed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    creator = commands.add_parser('create', help='produce unsigned metadata; never signs')
    verifier = commands.add_parser('verify', help='authenticate metadata and local package')
    for command in (creator, verifier):
        command.add_argument('--package', type=Path, required=True)
        command.add_argument('--platform', required=True)
        command.add_argument('--channel', required=True)
    creator.add_argument('--output', type=Path, required=True)
    creator.add_argument('--version', required=True)
    creator.add_argument('--sequence', type=int, required=True)
    creator.add_argument('--expires-at', type=int, required=True, help='Unix seconds; within 30 days')
    verifier.add_argument('--manifest', type=Path, required=True)
    verifier.add_argument('--signature', type=Path, required=True)
    verifier.add_argument('--public-key', type=Path, required=True, help='independently trusted PEM public key')
    verifier.add_argument('--minimum-sequence', type=int, required=True, help='trusted release floor, not downloaded metadata')
    args = parser.parse_args()
    try:
        (create if args.command == 'create' else verify)(args)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f'Release verification error: {error}\n')


if __name__ == '__main__':
    main()
