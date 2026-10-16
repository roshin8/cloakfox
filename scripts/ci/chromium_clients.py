#!/usr/bin/env python3
"""Build current macOS app clients from a verified immutable Chromium source SDK."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engines/chromium'


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def restore_sdk(package, destination, producer_sha):
    record = json.loads((package / 'source-provenance.json').read_text())
    archive = package / 'source-sdk.tar.gz'
    if record.get('gitSha') != producer_sha or record.get('sdkArchiveSha256') != digest(archive):
        raise ValueError('SDK producer/archive mismatch')
    destination.mkdir(parents=True, exist_ok=False)
    checkpoint = load('chromium_checkpoint')
    with tarfile.open(archive) as bundle:
        for member in bundle:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'source-sdk':
                raise ValueError('Unsafe SDK member')
            checkpoint.require_space(destination, member.size)
            bundle.extract(member, destination, filter='data')
    sdk = destination / 'source-sdk'
    actual = digest(sdk / 'Release/Chromium Embedded Framework.framework/Chromium Embedded Framework')
    if {actual, record.get('sourceFrameworkSha256'), record.get('sdkFrameworkSha256')} != {actual}:
        raise ValueError('Restored SDK differs from compiled source framework')
    return sdk, record


def app_provenance(record, embedded, consumer_sha, key, producer_run):
    if {embedded, record['sourceFrameworkSha256'], record['sdkFrameworkSha256']} != {embedded}:
        raise ValueError('Current client source/SDK/embedded hashes differ')
    return {**record, 'engineProducerSha': record['gitSha'], 'engineProducerRun': producer_run,
            'engineKey': key, 'appGitSha': consumer_sha, 'embeddedFrameworkSha256': embedded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--producer-sha', required=True)
    parser.add_argument('--producer-run', required=True)
    args = parser.parse_args()
    artifacts = load('engine_artifact')
    key = artifacts.input_key(ROOT, 'chromium')
    artifacts.verify(args.package, 'chromium', key, args.producer_sha, args.producer_run)
    sdk, record = restore_sdk(args.package, args.root, args.producer_sha)
    pipeline = load('chromium_source').Pipeline(args.root)
    pipeline.run('baseline-sdk', [sys.executable, ENGINE / 'fetch_cef.py', '--cache-dir', args.root / 'sdk-template'])
    lock = json.loads((ENGINE / 'cef-lock.json').read_text())
    template = args.root / 'sdk-template' / lock['archive'].removesuffix('.tar.bz2')
    for label, which_sdk in [('patched', sdk), ('baseline', template)]:
        build = args.root / (label + '-client')
        pipeline.run(label + '-configure', ['cmake', '-S', ENGINE, '-B', build, '-G', 'Ninja',
                     '-DCMAKE_BUILD_TYPE=Release', '-DCEF_ROOT=' + str(which_sdk)])
        pipeline.run(label + '-compile', ['cmake', '--build', build, '--parallel', '3'])
        pipeline.run(label + '-cpp-tests', ['ctest', '--test-dir', build, '--output-on-failure'])
    framework = args.root / 'patched-client/Release/CloakfoxChromium.app/Contents/Frameworks/Chromium Embedded Framework.framework/Versions/A/Chromium Embedded Framework'
    embedded = digest(framework)
    record = app_provenance(record, embedded, os.environ['GITHUB_SHA'], key, args.producer_run)
    (pipeline.logs / 'source-provenance.json').write_text(json.dumps(record, indent=2) + '\n')
    archive = args.root / 'chromium-apps.tar.gz'
    pipeline.run('package', ['tar', '-czf', archive, '-C', args.root,
                 'patched-client/Release/CloakfoxChromium.app', 'baseline-client/Release/CloakfoxChromium.app'])
    (pipeline.logs / 'chromium-apps.sha256').write_text(digest(archive) + '  chromium-apps.tar.gz\n')
    shutil.copy2(args.package / artifacts.MANIFEST, pipeline.logs / 'engine-artifact.json')


if __name__ == '__main__':
    main()
