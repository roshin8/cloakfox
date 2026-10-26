"""Hosted-only archive compatibility test; never execute restored engine bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

import chromium_checkpoint as checkpoint

PRODUCER = '284e0c27ac7078cf047615c88e5512725071b46e'
ARCHIVE_SHA = '942a814dd7d1b274c71c894f0854d457d9106c8dc3d36a603335f3dff4352d33'
ARCHIVE_BYTES = 13883524259


def manifest(root, output):
    """Hash every file plus exact timestamps, modes and link relationships."""
    root = Path(root)
    links = {}
    count = 0
    with Path(output).open('w') as stream:
        for parent, directories, files in os.walk(root, followlinks=False):
            directories.sort(); files.sort()
            for name in ['.'] if Path(parent) == root else []:
                info = root.lstat()
                stream.write(json.dumps(['.', 'dir', info.st_mode & 0o777, info.st_mtime_ns])+'\n')
            for name in sorted(directories+files):
                path = Path(parent)/name
                info = path.lstat()
                relative = path.relative_to(root).as_posix()
                row = [relative, info.st_mode & 0o777, info.st_mtime_ns]
                if stat.S_ISLNK(info.st_mode):
                    row += ['symlink', os.readlink(path)]
                elif stat.S_ISREG(info.st_mode):
                    row += ['file', info.st_size, checkpoint.digest(path)]
                    if info.st_nlink > 1:
                        key = (info.st_dev, info.st_ino)
                        row += ['hardlink', links.setdefault(key, relative)]
                elif stat.S_ISDIR(info.st_mode):
                    row += ['dir']
                else:
                    raise ValueError('Unexpected special file in checkpoint')
                stream.write(json.dumps(row)+'\n')
                count += 1
                if count % 50000 == 0:
                    print(f'CHECKPOINT manifest files={count}', flush=True)
    return {'entries': count, 'sha256': checkpoint.digest(output)}


def phase(directory, name):
    (directory/'phase').write_text(name)
    print('CHECKPOINT TEST phase='+name, flush=True)


def run(directory, incoming):
    directory = Path(directory).resolve()
    runner_temp = Path(os.environ['RUNNER_TEMP']).resolve()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise RuntimeError('Checkpoint roundtrip requires a disposable hosted runner')
    if directory != runner_temp/'checkpoint-roundtrip':
        raise ValueError('Unexpected diagnostic workspace')
    root = directory/'workspace'
    archive = Path(incoming)/'workspace.tar.gz'
    receipt = json.loads(archive.with_suffix('.json').read_text())
    if (receipt.get('identity', {}).get('gitSha') != PRODUCER or receipt.get('sha256') != ARCHIVE_SHA
            or receipt.get('bytes') != ARCHIVE_BYTES):
        raise ValueError('Unexpected preserved checkpoint producer or receipt')
    # restore itself rehashes the full archive and validates every member/link.
    identity = receipt['identity']
    started = time.monotonic()
    phase(directory, 'restore-original')
    checkpoint.restore(root, archive, identity)
    phase(directory, 'manifest-before')
    before = manifest(root, directory/'before.jsonl')
    phase(directory, 'native-save')
    native = directory/'workspace.tar.zst'
    checkpoint.save(root, native, identity, provenance={'diagnosticOnly': True, 'originalProducer': PRODUCER})
    # Only discard this newly extracted diagnostic copy, never the input artifact,
    # source caches, current builds, or any user checkout. Required for disk bounds.
    phase(directory, 'release-diagnostic-copy')
    if root.parent != directory or root.is_symlink():
        raise ValueError('Unsafe diagnostic cleanup path')
    shutil.rmtree(root)
    phase(directory, 'restore-native')
    checkpoint.restore(root, native, identity)
    phase(directory, 'manifest-after')
    after = manifest(root, directory/'after.jsonl')
    if before != after:
        raise RuntimeError('Native checkpoint content/metadata manifest differs after restore')
    result = {'verified': True, 'diagnosticOnly': True, 'compilerExecuted': False,
              'producerSha': PRODUCER, 'originalSha256': ARCHIVE_SHA, 'originalBytes': ARCHIVE_BYTES,
              'manifest': after, 'nativeReceipt': json.loads(native.with_suffix('.json').read_text()),
              'seconds': round(time.monotonic()-started, 1),
              'hostEligibilityForCompilation': 'not assessed; restored binaries were not executed'}
    (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    phase(directory, 'verified')


def observe(directory):
    from chromium_observer import Publisher, archive_snapshot
    directory = Path(directory)
    token = os.environ.pop('CHROMIUM_TELEMETRY_TOKEN')
    publisher = Publisher(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA'], token, 'checkpoint-roundtrip')
    previous = None
    deadline = time.monotonic()+230*60
    while True:
        finished = (directory/'stop').exists() or time.monotonic()>deadline
        now = time.time()
        data = {'sampleTimeUnix': now, 'finished': finished,
                'phase': (directory/'phase').read_text() if (directory/'phase').exists() else 'download',
                'freeBytes': shutil.disk_usage(directory).free,
                'checkpointArchive': archive_snapshot(directory, now, previous)}
        try:
            for name, args in [('processes',['ps','-axo','pid=,ppid=,rss=,time=,comm=']),
                               ('vmStat',['vm_stat']), ('swapUsage',['sysctl','-n','vm.swapusage'])]:
                raw = subprocess.check_output(args, text=True, timeout=8)
                if name == 'processes':
                    raw = '\n'.join(line for line in raw.splitlines()
                                    if Path(line.split()[-1]).name in ('Python','python3','python3.12','tar','zstd','Runner.Listener','Runner.Worker','node'))
                data[name] = raw[-18000:]
            with (directory/'telemetry.jsonl').open('a') as output:
                output.write(json.dumps(data)+'\n')
            publisher.publish(data, finished=finished)
        except Exception as error:
            with (directory/'observer-errors.log').open('a') as output:
                output.write(type(error).__name__+'\n')
        previous = data
        if finished:
            return
        for _ in range(15):
            if (directory/'stop').exists(): break
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run','observe'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--incoming', type=Path)
    args = parser.parse_args()
    if args.mode == 'observe': observe(args.directory)
    else: run(args.directory, args.incoming)
