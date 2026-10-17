"""Build the real TLS loopback fixture on the current runtime runner.

The fixture uses BoringSSL private APIs, so its upstream revision is immutable.
No downloaded executable or cross-run cache is trusted.
"""
import argparse
import hashlib
import json
import os
import signal
import tempfile
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BORINGSSL_COMMIT = '5b83e5d1abf0ae0033ae52ab579d906b67633b2c'
BORINGSSL_REMOTE = 'https://boringssl.googlesource.com/boringssl'
FIXTURE = ROOT / 'tests/network/alps_server.cc'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, *, cwd=None, timeout=600, terminate_grace=5):
    # File-backed output cannot deadlock on an inherited descendant pipe.
    with tempfile.TemporaryFile(mode='w+t') as output:
        process = subprocess.Popen(argv, cwd=cwd, text=True, stdout=output,
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                   start_new_session=True)
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=terminate_grace)
                except subprocess.TimeoutExpired:
                    pass
                # Kill remaining owned descendants even if their leader exited.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=terminate_grace)
                raise
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, argv)
        finally:
            output.seek(0)
            captured = output.read()
            print(captured, end='', flush=True)
    return captured.strip()


def build(work, commit):
    work.mkdir(parents=True, exist_ok=True)
    source = work / 'boringssl'
    # A fresh source tree per invocation avoids silently reusing modified headers.
    source.mkdir()
    run(['git', 'init', str(source)])
    run(['git', 'remote', 'add', 'origin', BORINGSSL_REMOTE], cwd=source)
    run(['git', 'fetch', '--depth=1', 'origin', BORINGSSL_COMMIT], cwd=source)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=source)
    if run(['git', 'rev-parse', 'HEAD'], cwd=source) != BORINGSSL_COMMIT:
        raise ValueError('BoringSSL checkout does not match pinned commit')
    output = work / 'build'
    run(['cmake', '-S', str(source), '-B', str(output), '-GNinja',
         '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF'])
    run(['cmake', '--build', str(output), '--target', 'ssl', 'crypto', '--parallel', '2'])
    binary = work / 'alps-server'
    run(['c++', '-std=c++17', '-I', str(source / 'include'), '-I', str(source),
         str(FIXTURE), str(output / 'libssl.a'), str(output / 'libcrypto.a'),
         '-lz', '-o', str(binary)])
    (work / 'manifest.json').write_text(json.dumps({
        'commit': commit, 'boringsslCommit': BORINGSSL_COMMIT,
        'fixtureSha256': digest(FIXTURE), 'binarySha256': digest(binary),
    }, indent=2) + '\n')
    verify(work, commit)


def verify(work, commit):
    manifest = json.loads((work / 'manifest.json').read_text())
    if manifest['commit'] != commit or manifest['boringsslCommit'] != BORINGSSL_COMMIT:
        raise ValueError('ALPS fixture commit mismatch')
    if manifest['fixtureSha256'] != digest(FIXTURE) or manifest['binarySha256'] != digest(work / 'alps-server'):
        raise ValueError('ALPS fixture hash mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'verify'))
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    globals()[args.action](args.work_dir.resolve(), args.commit)


if __name__ == '__main__':
    main()
