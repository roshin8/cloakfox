"""Independent macOS runner telemetry, published outside the Actions log stream."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import stat
import threading
import time
import urllib.request


def process_started(pid):
    try:
        return subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def archive_snapshot(directory, now, previous):
    archive = Path(directory) / 'workspace.tar.gz'
    result = {'exists': False, 'receiptPresent': False}
    try:
        info = archive.lstat()
        if not stat.S_ISREG(info.st_mode):
            return result
        result.update(exists=True, bytes=info.st_size, modifiedAtUnix=info.st_mtime,
                      modifiedAgeSeconds=round(max(0, now-info.st_mtime), 1),
                      fileIdentity=[info.st_dev, info.st_ino])
        receipt = archive.with_suffix('.json')
        result['receiptPresent'] = receipt.is_file() and not receipt.is_symlink()
    except OSError:
        return result
    prior = (previous or {}).get('checkpointArchive', {})
    interval = now - (previous or {}).get('sampleTimeUnix', now)
    same_file = prior.get('fileIdentity') == result['fileIdentity']
    last_growth = prior.get('lastObservedGrowthUnix', now) if same_file else now
    if same_file and interval > 0:
        delta = info.st_size-prior['bytes']
        result['sizeDeltaBytes'] = delta
        result['bytesPerSecond'] = round(delta/interval, 1)
        result['sampleIntervalSeconds'] = round(interval, 1)
        if delta > 0:
            last_growth = now
        elif delta < 0:
            result['sizeReset'] = True
            result['bytesPerSecond'] = None
    result['lastObservedGrowthUnix'] = last_growth
    result['secondsSinceObservedGrowth'] = round(max(0, now-last_growth), 1)
    # Receipt presence and CPU activity are observations, not proof that upload
    # completed. No archive reads, directory scans, or expensive hashing here.
    return result


def snapshot(root, evidence=None, previous=None):
    root = Path(root)
    now = time.time()
    result = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'harnessPid': os.getpid(), 'sampleTimeUnix': now}
    stage = root / 'evidence/stage.json'
    try:
        state = json.loads(stage.read_text())
        result['stage'] = state
        result['stageAgeSeconds'] = round(now - stage.stat().st_mtime, 1)
        name = state.get('stage', '')
        if name and Path(name).name == name:
            log = root / 'evidence' / (name + '.log')
            if log.is_file():
                result.update(logBytes=log.stat().st_size, logAgeSeconds=round(now - log.stat().st_mtime, 1))
                # Preserve native compiler evidence independently of the runner's
                # console upload. Restrict this to framework output: fetch/setup
                # logs may contain remote URLs or credentials and are excluded.
                if name == 'framework':
                    with log.open('rb') as source:
                        size = source.seek(0, os.SEEK_END)
                        source.seek(max(0, size - 12000))
                        tail = source.read(12000)
                    # Ignore a partial UTF-8 character at the bounded start.
                    result['compilerLogTail'] = tail.decode('utf-8', errors='ignore')
                    result['compilerLogTailTruncated'] = size > len(tail)
    except (OSError, ValueError):
        result['stage'] = {'state': 'not-yet-available'}
    rows = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,time=,rss=,stat=,comm='], text=True, timeout=5)
    processes = []
    for row in rows.splitlines():
        fields = row.split(None, 5)
        if len(fields) != 6:
            continue
        pid, parent, cpu, rss, state, command = fields
        parts = cpu.replace('-', ':').split(':')
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        processes.append({'pid': int(pid), 'parentPid': int(parent), 'cpuSeconds': seconds,
                          'rssKiB': int(rss), 'state': state, 'executable': command})
    owned = {os.getpid()}
    stage_child = (result.get('stage', {}).get('childPid')
                   if result.get('stage', {}).get('state') == 'running' else None)
    parent = next((p['parentPid'] for p in processes if p['pid'] == stage_child), None)
    remembered = previous or {}
    if parent is not None:
        started = process_started(parent)
        if started:
            result.update(buildHarnessPid=parent, buildHarnessStartedAt=started)
            owned.update((stage_child, parent))
    elif remembered.get('buildHarnessPid') and remembered.get('buildHarnessStartedAt'):
        parent = remembered['buildHarnessPid']
        result.update(buildHarnessPid=parent, buildHarnessStartedAt=remembered['buildHarnessStartedAt'])
        # Retain the Python archiver after Ninja exits, but never adopt a PID
        # that has been reused by an unrelated process.
        if any(p['pid'] == parent for p in processes) and process_started(parent) == remembered['buildHarnessStartedAt']:
            owned.add(parent)
    harness = next((p for p in processes if p['pid'] == result.get('buildHarnessPid') and p['pid'] in owned), None)
    result['buildHarnessAlive'] = harness is not None
    if harness:
        result['buildHarnessCpuSeconds'] = harness['cpuSeconds']
        same = (result.get('buildHarnessPid') == remembered.get('buildHarnessPid') and
                result.get('buildHarnessStartedAt') == remembered.get('buildHarnessStartedAt'))
        if same and 'buildHarnessCpuSeconds' in remembered:
            result['buildHarnessCpuDeltaSeconds'] = max(0, round(harness['cpuSeconds']-remembered['buildHarnessCpuSeconds'], 2))
    if evidence is not None:
        result['checkpointArchive'] = archive_snapshot(evidence, now, previous)
    while True:
        expanded = owned | {p['pid'] for p in processes if p['parentPid'] in owned}
        if expanded == owned:
            break
        owned = expanded
    # Observe the Actions agent and upload worker as well as compiler children.
    # These are executable names only; never publish command-line arguments.
    result['runnerProcesses'] = [p for p in processes if Path(p['executable']).name
                                 in ('Runner.Worker', 'Runner.Listener', 'node')]
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        try:
            result['vmStat'] = subprocess.check_output(['vm_stat'], text=True, timeout=5).strip()
            result['swapUsage'] = subprocess.check_output(['sysctl', '-n', 'vm.swapusage'], text=True, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            result['hostMemoryTelemetry'] = 'unavailable'
    result['processes'] = [p for p in processes if p['pid'] in owned]
    result['cpuSeconds'] = round(sum(p['cpuSeconds'] for p in result['processes']), 2)
    result['rssKiB'] = sum(p['rssKiB'] for p in result['processes'])
    return result


class Publisher:
    def __init__(self, repository, sha, token, segment):
        self.url = f'https://api.github.com/repos/{repository}/check-runs'
        self.sha, self.token, self.segment = sha, token, segment
        self.check_id = None

    def publish(self, data, finished=False):
        payload = {'name': 'Chromium runner telemetry / ' + self.segment,
                   # Each heartbeat is a neutral point-in-time observation. A
                   # runner loss must not leave an extra pending check forever.
                   'status': 'completed', 'conclusion': 'neutral',
                   'output': {'title': 'Runner telemetry; native build result is separate',
                              'summary': '```json\n' + json.dumps(data, indent=2) + '\n```'}}
        if self.check_id is None:
            payload['head_sha'] = self.sha
        request = urllib.request.Request(self.url + (f'/{self.check_id}' if self.check_id else ''),
                                         data=json.dumps(payload).encode(),
                                         headers={'Authorization': 'Bearer ' + self.token,
                                                  'Accept': 'application/vnd.github+json',
                                                  'Content-Type': 'application/json'},
                                         method='PATCH' if self.check_id else 'POST')
        with urllib.request.urlopen(request, timeout=5) as response:
            self.check_id = json.load(response)['id']


class Observer:
    def __init__(self, root, evidence):
        self.root, self.evidence = Path(root), Path(evidence)
        self.evidence.mkdir(parents=True, exist_ok=True)
        # Remove the diagnostic credential before Pipeline copies its child env.
        token = os.environ.pop('CHROMIUM_TELEMETRY_TOKEN', '')
        self.publisher = (Publisher(os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA'], token,
                                    os.environ.get('CHROMIUM_SEGMENT', '?')) if token else None)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.run, name='chromium-observer', daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        self.thread.join(timeout=22)

    def run(self):
        previous = None
        while True:
            finished = self.stopped.is_set()
            try:
                data = snapshot(self.root, self.evidence, previous=previous)
                previous = data
                data['finished'] = finished
                if not self.publisher:
                    data['remoteTelemetry'] = 'unavailable: no diagnostic token'
                path = self.evidence / 'runner-telemetry.json'
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(data, indent=2) + '\n')
                temporary.replace(path)
                with (self.evidence / 'runner-telemetry.jsonl').open('a') as output:
                    output.write(json.dumps(data) + '\n')
                if self.publisher:
                    self.publisher.publish(data, finished=finished)
            except Exception as error:
                # Observability is not a browser/runtime waiver or a build gate.
                with (self.evidence / 'runner-telemetry-errors.log').open('a') as output:
                    output.write(f'{datetime.datetime.now(datetime.timezone.utc).isoformat()} {type(error).__name__}: {error}\n')
            if finished:
                return
            self.stopped.wait(60)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Observe the whole source job, including checkpoint upload')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--minutes', type=int, default=350)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not 1 <= args.minutes <= 350:
        parser.error('Job observation requires Actions and a bounded lifetime')
    observer = Observer(args.root, args.evidence)
    observer.start()
    deadline = time.monotonic() + args.minutes * 60
    try:
        while time.monotonic() < deadline and not (args.evidence / 'job-observer.stop').exists():
            time.sleep(1)
    finally:
        observer.stop()
