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
    while True:
        expanded = owned | {p['pid'] for p in processes if p['parentPid'] in owned}
        if expanded == owned:
            break
        owned = expanded
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
