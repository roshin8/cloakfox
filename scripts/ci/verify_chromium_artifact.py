#!/usr/bin/env python3
"""Verify same-run source provenance before launching either test companion."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tarfile


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def verify(archive, evidence, destination, expected_sha):
    receipts = list(evidence.rglob('source-provenance.json'))
    checksums = list(evidence.rglob('chromium-apps.sha256'))
    if len(receipts) != 1 or len(checksums) != 1:
        raise ValueError('Exactly one source provenance and archive checksum required')
    record = json.loads(receipts[0].read_text())
    if 'appGitSha' in record or 'engineProducerSha' in record:
        spec = importlib.util.spec_from_file_location('engine_artifact', Path(__file__).with_name('engine_artifact.py'))
        engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(engine)
        if (not expected_sha or record.get('appGitSha') != expected_sha
                or not record.get('engineProducerSha')
                or record.get('gitSha') != record.get('engineProducerSha')
                or record.get('engineKey') != engine.input_key(Path(__file__).resolve().parents[2], 'chromium')):
            raise ValueError('Current app commit or reusable engine provenance mismatch')
    elif not expected_sha or record.get('gitSha') != expected_sha:
        raise ValueError('Source artifact is not from this checkout commit')
    if digest(archive) != checksums[0].read_text().split()[0]:
        raise ValueError('Companion archive checksum differs from source job')
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter='data')
    framework = destination / 'patched-client/Release/CloakfoxChromium.app/Contents/Frameworks/Chromium Embedded Framework.framework/Versions/A/Chromium Embedded Framework'
    actual = digest(framework)
    if {actual, record['sourceFrameworkSha256'], record['sdkFrameworkSha256'], record['embeddedFrameworkSha256']} != {actual}:
        raise ValueError('Embedded framework differs from the source/SDK provenance')
    print('Verified current app and source/SDK/embedded framework SHA256:', actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    verify(args.archive, args.evidence, args.destination, os.environ.get('GITHUB_SHA'))


if __name__ == '__main__':
    main()
