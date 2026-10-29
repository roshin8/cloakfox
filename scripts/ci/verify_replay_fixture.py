#!/usr/bin/env python3
"""Verify pinned data and safely unpack it; no replay or native execution."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

REVISION = 'a06a95168d462024d274570ab73f5b8c535ca103'
MANIFEST_SHA256 = '49f0e00f0b7da7701f9845f248074bcb0a7b387fa22ab30436529fae88f6e29d'
SDK_MANIFEST_SHA256 = '6f4b598b29e0e175721c407e092869ec29e07ef8d9837ac597a1dc57da4edef8'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def verify(repo, assets, destination):
    manifest_bytes = (assets / 'locale-source-replay-a06a951.json').read_bytes()
    assert sha(manifest_bytes) == MANIFEST_SHA256, 'Fixture manifest changed'
    manifest = json.loads(manifest_bytes)
    assert manifest['clientRevision'] == REVISION
    sdk_bytes = (assets / manifest['sdkManifestAsset']).read_bytes()
    assert sha(sdk_bytes) == SDK_MANIFEST_SHA256 == manifest['sdkManifestSha256']
    sdk = json.loads(sdk_bytes)
    assert sdk['clientRevision'] == REVISION
    locks, inputs = {}, {}
    def inherit(name):
        data = (repo / 'engines/chromium' / name).read_bytes()
        lock = json.loads(data)
        if lock.get('applyAfter'):
            inherit(lock['applyAfter'])
        digest = sha(data)
        assert digest == manifest['patchLocks'][name] == sdk['patchLocks'][name], name
        locks[name] = digest
        for item in lock['inputs']:
            inputs[item['path']] = item['afterSha256']
    inherit(manifest['terminalPatchLock'])
    assert locks == manifest['patchLocks'] and len(locks) == 11
    assert inputs == sdk['sourceFiles']
    assert inputs == {name: entry['sha256'] for name, entry in manifest['sourceFiles'].items()}
    assert len(inputs) == manifest['sourceFileCount'] == 68
    assert sha((repo / manifest['testPath']).read_bytes()) == manifest['testSha256'], 'Replay test is not pinned a06 text'
    archive = assets / manifest['archiveName']
    assert archive.stat().st_size == manifest['archiveBytes']
    assert sha(archive.read_bytes()) == manifest['archiveSha256'], 'Fixture archive changed'
    expected = {manifest['archiveRoot'] + '/' + name: name for name in inputs}
    with tarfile.open(archive, 'r:gz') as tar:
        entries = tar.getmembers()
        assert len(entries) == len(expected)
        assert {entry.name for entry in entries} == set(expected)
        data_by_name = {}
        for entry in entries:
            path = PurePosixPath(entry.name)
            assert not path.is_absolute() and '..' not in path.parts and entry.isfile()
            name = expected[entry.name]
            data = tar.extractfile(entry).read()
            assert sha(data) == inputs[name], name
            assert len(data) == manifest['sourceFiles'][name]['bytes'], name
            data_by_name[entry.name] = data
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in data_by_name.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source = destination / manifest['archiveRoot']
    assert all(sha((source / name).read_bytes()) == digest for name, digest in inputs.items())
    print(json.dumps({'verified': True, 'sourceFiles': len(inputs), 'patchLocks': len(locks), 'clientRevision': REVISION, 'CLOAKFOX_CHROMIUM_SOURCE': str(source)}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    args = p.parse_args()
    verify(args.repo, args.assets, args.destination)
