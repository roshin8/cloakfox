"""Sign verified canonical libraries before sealing their final manifest in an app."""
import argparse
import importlib.util
from pathlib import Path
import subprocess


def builder():
    path = Path(__file__).resolve().parents[1] / 'build-canonical-gpu.py'
    spec = importlib.util.spec_from_file_location('canonical_gpu_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(bundle, commit):
    metadata = builder().verify_integrity_manifest(bundle)
    if metadata.get('gitSha') != commit:
        raise ValueError('Canonical GPU artifact commit mismatch')
    return metadata


def sign_bundle(bundle, commit, run=subprocess.run):
    build = builder()
    metadata = build.verify_integrity_manifest(bundle)
    if metadata.get('gitSha', commit) != commit:
        raise ValueError('Canonical GPU artifact commit mismatch')
    for name in build.LIBRARIES:
        run(['codesign', '--force', '--sign', '-', str(bundle / name)], check=True)
    metadata['gitSha'] = commit
    build.write_integrity_manifest(bundle, metadata)
    verify(bundle, commit)


def sign_app(app, commit, run=subprocess.run):
    bundle = app / 'Contents/Resources/canonical-gpu'
    metadata = verify(bundle, commit)
    # Retain existing nested-app signing behavior, then refresh the hashes of
    # the now signed leaf libraries before creating the final outer seal.
    run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
    builder().write_integrity_manifest(bundle, metadata)
    run(['codesign', '--force', '--sign', '-', str(app)], check=True)
    run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    verify(bundle, commit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('bundle', 'app', 'verify'))
    parser.add_argument('--path', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if args.mode == 'bundle':
        sign_bundle(args.path, args.commit)
    elif args.mode == 'app':
        sign_app(args.path, args.commit)
    else:
        verify(args.path, args.commit)
