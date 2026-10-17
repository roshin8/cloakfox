"""Independent macOS runner telemetry, published outside the Actions log stream."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request


def snapshot(root):
    root = Path(root)
    now = time.time()
    result = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'harnessPid': os.getpid()}
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
    for process in processes:
        if process['pid'] == stage_child:
            owned.update((stage_child, process['parentPid']))
            result['buildHarnessPid'] = process['parentPid']
            break
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
        while True:
            finished = self.stopped.is_set()
            try:
                data = snapshot(self.root)
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
