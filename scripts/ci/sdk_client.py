#!/usr/bin/env python3
"""Consume a versioned SDK. Chromium compilation is deliberately not supported."""
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tarfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root):
    entries = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(current) / name
            relative = path.relative_to(root).as_posix()
            mode = stat.S_IMODE(path.lstat().st_mode)
            if path.is_symlink():
                require(path.resolve(strict=True).is_relative_to(root.resolve()), 'external SDK link')
                entry = {'kind': 'link', 'target': os.readlink(path), 'mode': mode}
            elif path.is_file():
                entry = {'kind': 'file', 'sha256': digest(path), 'size': path.stat().st_size, 'mode': mode}
            elif path.is_dir():
                entry = {'kind': 'directory', 'mode': mode}
            else:
                raise ValueError('unsupported SDK entry: ' + relative)
            entries[relative] = entry
    return entries


def sdk_filter(member, destination):
    # Retain data_filter's containment/type/link checks, but preserve the SDK's
    # read-only resources and directory modes. Never restore special mode bits.
    safe = tarfile.data_filter(member, destination)
    require(member.mode & ~0o777 == 0, 'unsafe SDK mode bits')
    return safe.replace(mode=member.mode) if safe.isfile() or safe.isdir() else safe


def native_inputs(source, revision):
    patterns = ('engines/chromium/*lock.json', 'engines/chromium/cef-runtime-patches.json',
                'engines/chromium/apply_*_patch.py', 'engines/chromium/patches/*',
                'engines/chromium/build_identity.py', 'engines/chromium/clt_sdk_info.py',
                'engines/chromium/prepare_clt_build.py', 'engines/chromium/source_preflight.py',
                'engines/chromium/fetch_cef.py', 'scripts/ci/chromium_source.py',
                'scripts/ci/chromium_host_identity.py', 'scripts/ci/chromium_host_tools.py',
                'scripts/ci/prepare_macos.py')
    listing = subprocess.check_output(['git', '-C', str(source), 'ls-tree', '-r', '-z', revision])
    return [entry for entry in listing.split(b'\0') if entry and any(
        fnmatch.fnmatchcase(entry.split(b'\t', 1)[1].decode(), pattern) for pattern in patterns)
        and entry.split(b'\t', 1)[1] != b'engines/chromium/sdk-lock.json']


def verify_caller(source, lock):
    paths = ['engines/chromium', 'engines/shared', 'additions/cloakcfg/engine-host',
             'tests/engines', 'tests/network', 'tests/fingerprint',
             'scripts/ci/run_engine_tests.py', 'scripts/ci/runner_probe.py',
             'scripts/setup-fingerprint-libraries.py',
             ':(exclude)engines/chromium/sdk-lock.json',
             ':(exclude)engines/chromium/ci-media-fixture.patch']
    changed = subprocess.check_output(['git', '-C', str(source), 'diff', '--name-only',
                                      lock['clientRevision'], 'HEAD', '--', *paths], text=True)
    require(not changed, 'Client/native/test inputs differ from the reviewed client pin: ' + changed +
            'Update the client pin for compatible changes or publish a new SDK for native changes. '
            'CI will not rebuild Chromium or validate an unrelated older client.')
    require(native_inputs(source, 'HEAD') == native_inputs(source, lock['sdkSourceRevision']),
            'Current native inputs differ from the SDK source revision')


def verify_sdk(package, lock, source, destination):
    manifest = package / 'sdk-import.json'
    require(digest(manifest) == lock['manifestSha256'], 'SDK manifest digest mismatch')
    record = json.loads(manifest.read_text())
    require(record['schema'] == 1 and record['origin'] == 'locally-built-sdk-import', 'SDK origin mismatch')
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(revision == lock['clientRevision'], 'client revision mismatch')
    require(record['clientRevision'] == lock['sdkSourceRevision'], 'SDK source revision mismatch')
    require(native_inputs(source, revision) == native_inputs(source, lock['sdkSourceRevision']),
            'client native inputs require a different SDK')
    for field in ('archiveSha256', 'archiveBytes', 'frameworkSha256'):
        require(record[field] == lock[field], 'SDK lock mismatch: ' + field)
    archive = package / lock['archiveName']
    require(archive.stat().st_size == lock['archiveBytes'] and digest(archive) == lock['archiveSha256'],
            'SDK archive digest/size mismatch')
    locks, expected = {}, {}

    def chain(name):
        path = source / 'engines/chromium' / name
        data = json.loads(path.read_text())
        if data.get('applyAfter'):
            chain(data['applyAfter'])
        locks[name] = digest(path)
        for entry in data['inputs']:
            expected[entry['path']] = entry['afterSha256']

    chain(lock['patchLock'])
    require(record['patchLocks'] == locks and record['sourceFiles'] == expected, 'SDK source lock mismatch')
    sdk_name = record['sdkRoot']
    require(PurePosixPath(sdk_name).name == sdk_name and sdk_name not in ('.', '..', ''), 'invalid SDK root')
    require(not destination.exists(), 'SDK destination already exists')
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == sdk_name,
                    'unsafe archive path')
            require(path.as_posix() not in names, 'duplicate archive path')
            names.add(path.as_posix())
            require(member.isfile() or member.isdir() or member.issym() or member.islnk(), 'unsafe archive type')
        bundle.extractall(destination, members=members, filter=sdk_filter)
    sdk = destination / sdk_name
    require(inventory(sdk) == record['entries'], 'SDK inventory mismatch (files, hashes, modes, links)')
    require(digest(sdk / lock['frameworkPath']) == lock['frameworkSha256'], 'SDK framework digest mismatch')
    return sdk, record


def run(args, source):
    subprocess.run([str(arg) for arg in args], cwd=source, check=True)


def build_clients(source, package, lock_path, work):
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted',
            'native client builds require a GitHub-hosted runner')
    lock = json.loads(lock_path.read_text())
    work.mkdir(parents=True, exist_ok=False)
    sdk, record = verify_sdk(package, lock, source, work / 'sdk')
    # Explicitly recorded client-only test fixture. No SDK/engine bytes change.
    patch = lock_path.parent / lock['clientPatch']
    require(digest(patch) == lock['clientPatchSha256'], 'client fixture patch digest mismatch')
    run(['git', 'apply', '--check', patch], source)
    run(['git', 'apply', patch], source)
    evidence = source / 'evidence'
    evidence.mkdir(exist_ok=True)
    verification = {key: record[key] for key in ('origin', 'archiveSha256', 'frameworkSha256',
                    'clientRevision', 'patchLocks', 'knownValidationFailures')}
    verification['sdkSourceRevision'] = record['clientRevision']
    verification['clientRevision'] = lock['clientRevision']
    verification['clientPatchSha256'] = lock['clientPatchSha256']
    verification['controllerRevision'] = os.environ['GITHUB_SHA']
    (evidence / 'sdk-verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    # Download an upstream binary SDK as the negative control, never compile it.
    run(['python3', 'engines/chromium/fetch_cef.py', '--cache-dir', work / 'baseline-template'], source)
    cef = json.loads((source / 'engines/chromium/cef-lock.json').read_text())
    baseline = work / 'baseline-template' / cef['archive'].removesuffix('.tar.bz2')
    for label, selected in [('patched', sdk), ('baseline', baseline)]:
        build = work / (label + '-client')
        run(['cmake', '-S', source / 'engines/chromium', '-B', build, '-G', 'Ninja',
             '-DCMAKE_BUILD_TYPE=Release', '-DCEF_ROOT=' + str(selected)], source)
        run(['cmake', '--build', build, '--parallel', '3'], source)
        run(['ctest', '--test-dir', build, '--output-on-failure'], source)
    binary_relative = 'Release/CloakfoxChromium.app/Contents/MacOS/CloakfoxChromium'
    app = work / 'patched-client/Release/CloakfoxChromium.app'
    embedded = app / 'Contents/Frameworks/Chromium Embedded Framework.framework/Versions/A/Chromium Embedded Framework'
    require(digest(embedded) == lock['frameworkSha256'], 'embedded engine mismatch')
    probe = work / 'patched-client/Release/host_surface_probe'
    require(probe.is_file(), 'missing native surface probe')
    archive = work / 'clients.tar.gz'
    run(['tar', '-czf', archive, '-C', work, 'patched-client/Release', 'baseline-client/Release'], source)
    verification.update({'embeddedFrameworkSha256': digest(embedded), 'appsArchiveSha256': digest(archive),
                         'appsArchiveBytes': archive.stat().st_size})
    (evidence / 'sdk-verification.json').write_text(json.dumps(verification, indent=2) + '\n')
    with open(os.environ['GITHUB_ENV'], 'a') as environment:
        for key, value in {'CLOAKFOX_CHROMIUM_BIN': work / 'patched-client' / binary_relative,
                           'CLOAKFOX_UNPATCHED_CHROMIUM_BIN': work / 'baseline-client' / binary_relative,
                           'CLOAKFOX_NATIVE_SURFACE_PROBE': probe}.items():
            environment.write(f'{key}={value}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    arguments = parser.parse_args()
    build_clients(Path.cwd(), arguments.package.resolve(), arguments.lock.resolve(), arguments.work.resolve())
