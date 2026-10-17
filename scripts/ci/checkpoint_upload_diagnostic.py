"""Observe a hosted checkpoint transfer independently of the Actions worker.

Only fixed diagnostic counters are exported from runner logs, never raw lines.
This does not compile, extract or modify the checkpoint workspace.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

PRODUCER_SHA = '43aede189510fe56f98744bd7ecf11f894445285'
SIGNALS = ('OutOfMemoryException', 'HttpRequestException', 'SocketException',
           'No space left on device', 'Connection reset', 'timed out', 'TaskAgentSessionConflictException')


def process_summary(rows):
    selected, total = [], 0
    for row in rows.splitlines():
        fields = row.split(None, 4)
        if len(fields) != 5:
            continue
        pid, parent, rss, state, command = fields
        total += int(rss)
        name = Path(command).name
        if name in ('Runner.Worker', 'Runner.Listener', 'node', 'Python', 'python3', 'python3.12'):
            selected.append(dict(pid=int(pid), parentPid=int(parent), rssKiB=int(rss), state=state, executable=name))
    return {'runnerProcesses': selected, 'totalRssKiB': total}


def runner_log_summary(directory):
    result = []
    for path in sorted(Path(directory).glob('*.log'))[-12:]:
        if not path.is_file():
            continue
        with path.open('rb') as source:
            size = source.seek(0, os.SEEK_END)
            source.seek(max(0, size - 65536))
            tail = source.read(65536).decode('utf-8', errors='ignore')
        result.append({'kind': 'Worker' if path.name.startswith('Worker') else 'Runner',
                       'bytes': size, 'ageSeconds': round(time.time() - path.stat().st_mtime, 1),
                       'signals': {name: tail.count(name) for name in SIGNALS}})
    return result


def verify(directory):
    archive = Path(directory) / 'workspace.tar.gz'
    receipt = json.loads(archive.with_suffix('.json').read_text())
    if receipt.get('schemaVersion') != 1 or receipt.get('identity', {}).get('gitSha') != PRODUCER_SHA:
        raise ValueError('Unexpected checkpoint producer')
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != receipt.get('sha256') or archive.stat().st_size != receipt.get('bytes'):
        raise ValueError('Checkpoint archive differs from its exact producer receipt')
    return {'sha256': digest, 'bytes': archive.stat().st_size, 'producerSha': PRODUCER_SHA}


def command(args):
    return subprocess.check_output(args, text=True, timeout=8).strip()


def observe(directory):
    from chromium_observer import Publisher
    directory.mkdir(parents=True, exist_ok=True)
    token = os.environ.pop('CHROMIUM_TELEMETRY_TOKEN')
    publisher = Publisher(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA'], token, 'checkpoint-transfer-diagnostic')
    deadline = time.monotonic() + 40 * 60
    while True:
        finished = (directory / 'stop').exists() or time.monotonic() >= deadline
        data = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'finished': finished,
                'phase': (directory / 'phase').read_text().strip() if (directory / 'phase').exists() else 'starting',
                'freeBytes': shutil.disk_usage(directory).free}
        try:
            rows = command(['ps', '-axo', 'pid=,ppid=,rss=,stat=,comm='])
            data.update(process_summary(rows))
            data['vmStat'] = command(['vm_stat'])
            data['swapUsage'] = command(['sysctl', '-n', 'vm.swapusage'])
            data['runnerDiagnostics'] = []
            for row in rows.splitlines():
                fields = row.split(None, 4)
                if len(fields) == 5 and Path(fields[4]).name == 'Runner.Worker' and Path(fields[4]).is_absolute():
                    data['runnerDiagnostics'] = runner_log_summary(Path(fields[4]).parent.parent / '_diag')
                    break
            with (directory / 'telemetry.jsonl').open('a') as output:
                output.write(json.dumps(data) + '\n')
            publisher.publish(data, finished=finished)
        except Exception as error:
            # Do not export exception text: network exceptions may contain URLs.
            with (directory / 'observer-errors.log').open('a') as output:
                output.write(type(error).__name__ + '\n')
        if finished:
            return
        for _ in range(15):
            if (directory / 'stop').exists():
                break
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['observe', 'verify'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.mode == 'verify':
        print(json.dumps(verify(args.directory)))
    else:
        if os.environ.get('GITHUB_ACTIONS') != 'true' or platform.system() != 'Darwin' or platform.machine() != 'arm64':
            parser.error('Observation is restricted to hosted macOS arm64')
        observe(args.directory)
