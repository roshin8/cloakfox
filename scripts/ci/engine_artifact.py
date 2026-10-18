#!/usr/bin/env python3
"""Content-addressed, repository-owned macOS native build artifacts.

An engine artifact is a build input, never a substitute for current runtime tests.
Keys use committed Git objects; uncommitted local implementation is excluded.
"""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'engine-artifact.json'
INPUTS = {
    'chromium': ['engines/chromium/source-lock.json', 'engines/chromium/cef-lock.json',
        'engines/chromium/cef-runtime-patches.json', 'engines/chromium/*patch-lock.json',
        'engines/chromium/apply_*_patch.py', 'engines/chromium/patches',
        'engines/chromium/fetch_cef.py', 'scripts/ci/chromium_source.py',
        'scripts/ci/chromium_checkpoint.py', 'scripts/ci/chromium_host_identity.py',
        'scripts/ci/chromium_host_tools.py', 'scripts/ci/metal_toolchain.py',
        'scripts/ci/prepare_macos.py', 'scripts/ci/runner_probe.py',
        'scripts/ci/engine_artifact.py', '.github/workflows/chromium-engine.yml',
        '.github/workflows/chromium-source-segment.yml'],
    'gecko': ['Makefile', 'upstream.sh', 'patches', 'additions', 'settings', 'branding',
        'assets', 'bundle', '*mozconfig*', 'scripts', '.github/workflows/gecko-engine.yml',
        'tests/fingerprint/test_*.mjs', 'tests/release', 'tests/network/test_native_network_snapshot.py'],
}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def input_key(root, kind):
    listing = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', '-z', 'HEAD'])
    selected = []
    for entry in listing.split(b'\0'):
        if not entry:
            continue
        path = entry.split(b'\t', 1)[1].decode('utf-8')
        if any(path == pattern or path.startswith(pattern + '/') or fnmatch.fnmatchcase(path, pattern)
               for pattern in INPUTS[kind]):
            selected.append(entry)
    tree = b'\0'.join(selected)
    if not tree:
        raise ValueError('No committed build inputs')
    return hashlib.sha256(b'cloakfox-native-v1/macos-arm64/' + kind.encode() + b'\0' + tree).hexdigest()


def payload(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Artifact payload cannot contain symlinks')
        if path.is_file() and path != directory / MANIFEST:
            files[path.relative_to(directory).as_posix()] = {'sha256': digest(path), 'size': path.stat().st_size}
    if not files:
        raise ValueError('Empty artifact payload')
    return files


def seal(directory, kind, key, producer_sha, producer_run):
    record = {'schema': 1, 'platform': 'macos-arm64', 'kind': kind, 'key': key,
              'producerSha': producer_sha, 'producerRun': str(producer_run), 'files': payload(directory)}
    (directory / MANIFEST).write_text(json.dumps(record, indent=2) + '\n')
    return record


def verify(directory, kind, key, producer_sha, producer_run):
    if (directory / MANIFEST).is_symlink():
        raise ValueError('Linked manifest')
    record = json.loads((directory / MANIFEST).read_text())
    expected = {'schema': 1, 'platform': 'macos-arm64', 'kind': kind, 'key': key,
                'producerSha': producer_sha, 'producerRun': str(producer_run)}
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError('Artifact key/platform/producer mismatch')
    if record.get('files') != payload(directory):
        raise ValueError('Artifact payload file set/hash mismatch')
    return record


def trusted_run(run, repository, kind):
    paths = {'.github/workflows/build-macos.yml', f'.github/workflows/{kind}-engine.yml'}
    return (run.get('repository', {}).get('full_name') == repository
            and run.get('head_repository', {}).get('full_name') == repository
            and run.get('event') in ('push', 'workflow_dispatch')
            and run.get('head_branch') in ('main', 'codex/firefox-158-port')
            and run.get('path') in paths)


def completed_gate(jobs, kind):
    suffix = kind + '-engine-complete'
    return any(job.get('name', '').split(' / ')[-1] == suffix
               and job.get('status') == 'completed' and job.get('conclusion') == 'success' for job in jobs)


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True))


def find(repository, kind, key):
    # Bound API work; expired/deleted builds are a cold miss, never an unverified hit.
    name = f'{kind}-macos-arm64-{key}'
    records = api(f'repos/{repository}/actions/artifacts?' + urlencode({'name': name, 'per_page': 100}))
    for artifact in records['artifacts'][:20]:
        if artifact.get('expired') or artifact.get('name') != name:
            continue
        run_id = artifact['workflow_run']['id']
        run = api(f'repos/{repository}/actions/runs/{run_id}')
        if not trusted_run(run, repository, kind) or artifact['workflow_run']['head_sha'] != run['head_sha']:
            continue
        jobs = []
        page = 1
        while True:
            result = api(f'repos/{repository}/actions/runs/{run_id}/jobs?per_page=100&page={page}')
            jobs += result['jobs']
            if len(result['jobs']) < 100:
                break
            page += 1
        if completed_gate(jobs, kind):
            return {'found': 'true', 'artifact-id': str(artifact['id']),
                    'producer-run': str(run_id), 'producer-sha': run['head_sha'], 'key': key}
    return {'found': 'false', 'key': key}


def outputs(values):
    print(json.dumps(values, indent=2))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            for name, value in values.items():
                stream.write(f'{name}={value}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('key', 'find', 'seal', 'verify'))
    parser.add_argument('--kind', choices=tuple(INPUTS), required=True)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--producer-sha')
    parser.add_argument('--producer-run')
    args = parser.parse_args()
    key = input_key(ROOT, args.kind)
    if args.mode == 'key':
        outputs({'key': key})
    elif args.mode == 'find':
        outputs(find(os.environ['GITHUB_REPOSITORY'], args.kind, key))
    else:
        if not args.directory:
            parser.error('directory required')
        sha = args.producer_sha or os.environ['GITHUB_SHA']
        run = args.producer_run or os.environ['GITHUB_RUN_ID']
        record = (seal if args.mode == 'seal' else verify)(args.directory, args.kind, key, sha, run)
        if args.mode == 'verify':
            # Keep producer identity intact; bind it to the consumer without editing receipts.
            (args.directory.parent / 'engine-consumption.json').write_text(json.dumps({
                'consumerSha': os.environ.get('GITHUB_SHA'), 'build': record}, indent=2) + '\n')
        outputs({'key': key, 'producer-sha': sha, 'producer-run': run})


if __name__ == '__main__':
    main()
