"""Run every Cloakfox fingerprint probe against a built binary and summarise.

The inherited tests/run-tests.sh is a Playwright runner from upstream Camoufox
and does not work on this branch (no Juggler). The real suite is these
standalone selenium probes; this driver runs them all and reports one table.

Each probe is a separate process that launches its own browser instance(s), so
the suite is slow (minutes) but fully isolated — a crash in one probe cannot
corrupt another. Probes are expected to exit 0 (pass), 1 (fail), 2 (could not
run / inconclusive, e.g. a vector unavailable on this host).

Usage:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/run_all.py [-k SUBSTRING] [--list]

Exit code: 0 only when every result passes or has an exact unexpired allowance.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import os
import subprocess
import signal
import tempfile
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Probes that need a special environment or are one-off spikes rather than
# regression tests, with the reason they are skipped by default.
SKIP = {
    "probe_font_spike.py": "phase-0 spike, needs a hand-staged test font",
    "probe_fingerprint_libraries.py": "required separately in CI after pinned fixture setup",
    "run_all.py": "this driver",
}


def validate_allowances(entries):
    if type(entries) is not list:
        raise ValueError('Allowances must be a list')
    seen = set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != {'probe', 'platform', 'reason', 'expires'}:
            raise ValueError('Each allowance needs exact probe, platform, reason and expiry')
        if not isinstance(entry['probe'], str) or not re.fullmatch(r'probe_[a-z0-9_]+\.py', entry['probe']):
            raise ValueError('Wildcard/invalid probe allowance')
        if entry['platform'] not in ('darwin', 'linux', 'win32'):
            raise ValueError('Allowance requires one exact supported platform')
        if not isinstance(entry['reason'], str) or not entry['reason'].strip():
            raise ValueError('Allowance requires a reason')
        try:
            if not isinstance(entry['expires'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', entry['expires']):
                raise ValueError('Date must use YYYY-MM-DD')
            datetime.date.fromisoformat(entry['expires'])
        except (TypeError, ValueError):
            raise ValueError('Allowance requires an ISO expiry date')
        key = (entry['probe'], entry['platform'])
        if key in seen:
            raise ValueError('Duplicate probe/platform allowance')
        seen.add(key)
    return entries


def accept_outcome(probe, code, allowances, platform, today):
    validate_allowances(allowances)
    return code == 0 or (code == 2 and any(
        entry['probe'] == probe and entry['platform'] == platform
        and datetime.date.fromisoformat(entry['expires']) >= today for entry in allowances))


def discover() -> list[Path]:
    return sorted(p for p in HERE.glob("probe_*.py") if p.name not in SKIP)


def probe_environment(path: Path, environment):
    environment = dict(environment)
    if root := environment.get('PROBE_REPORT_ROOT'):
        report = Path(root).resolve() / path.stem
        report.mkdir(parents=True, exist_ok=True)
        environment['REPORT_DIR'] = str(report)
    return environment


def run_probe(path: Path, timeout: float):
    # File-backed capture cannot hang waiting for inherited browser pipe handles.
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen([sys.executable, str(path)], stdout=log, stderr=subprocess.STDOUT,
                                   env=probe_environment(path, os.environ), start_new_session=(os.name == 'posix'))
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = 3
        finally:
            # Each POSIX attempt owns a new session. Clean its browser/server
            # descendants even when the probe itself exited before quitting them.
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        log.seek(0)
        output = log.read().decode('utf-8', errors='replace')
        if code == 3:
            output += f"\nTIMEOUT after {timeout}s"
        if os.environ.get('PROBE_REPORT_ROOT'):
            report = Path(probe_environment(path, os.environ)['REPORT_DIR'])
            (report / 'probe-output.txt').write_text(output)
        return code, output


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", metavar="SUBSTRING",
                    help="only run probes whose filename contains SUBSTRING")
    ap.add_argument("--list", action="store_true", help="list probes and exit")
    ap.add_argument("--timeout", type=int, default=900,
                    help="per-probe timeout in seconds (default 900)")
    ap.add_argument("--retries", type=int, default=1,
                    help="retries for a failing probe (default 1); browser "
                         "launches can fail spuriously under load")
    ap.add_argument('--allow-inconclusive', type=Path, default=HERE / 'inconclusive-allowances.json',
                    help='Exact, reasoned, expiring platform/probe allowances (default empty)')
    ap.add_argument('--report', type=Path, default=HERE / 'reports/probe-suite.json')
    args = ap.parse_args()
    try:
        policy = json.loads(args.allow_inconclusive.read_text())
        if type(policy) is not dict or set(policy) != {'schemaVersion', 'allowances'} or type(policy['schemaVersion']) is not int or policy['schemaVersion'] != 1:
            raise ValueError('Unsupported allowance policy schema')
        allowances = validate_allowances(policy['allowances'])
    except (OSError, ValueError, TypeError) as error:
        ap.error(str(error))
    today = datetime.datetime.now(datetime.timezone.utc).date()

    probes = discover()
    if args.k:
        probes = [p for p in probes if args.k in p.name]

    if args.list:
        for p in probes:
            print(p.name)
        for name, why in SKIP.items():
            print(f"{name}  (skipped: {why})")
        return 0

    if not probes:
        print('No probes selected; refusing an empty successful suite', file=sys.stderr)
        return 1
    binary = os.environ.get("CLOAKFOX_BIN")
    if not binary or not os.path.exists(binary):
        print("CLOAKFOX_BIN not set or binary missing", file=sys.stderr)
        return 1
    print(f"binary: {binary}")
    print(f"probes: {len(probes)}\n")

    results = []
    for p in probes:
        started = time.time()
        print(f"--- {p.name} ...", flush=True)
        # Each probe launches its own browser(s); under contention a launch can
        # fail spuriously (observed: probes that fail in a full run pass
        # individually). Retry a failure once before believing it, so the suite
        # verdict reflects the code rather than the machine.
        attempts = 0
        while True:
            attempts += 1
            code, out = run_probe(p, args.timeout)
            if accept_outcome(p.name, code, allowances, sys.platform, today) or attempts > args.retries:
                break
            print(f"    retry {attempts}/{args.retries} after exit {code} ...", flush=True)
            time.sleep(3)
        took = time.time() - started
        if attempts > 1 and code == 0:
            print(f"    (passed on attempt {attempts} — flaky launch, not a code failure)")
        # Surface the probe's own verdict line if it printed one.
        verdict = next((ln for ln in reversed(out.splitlines())
                        if ln.startswith(("PASS", "FAIL", "INCONCLUSIVE"))), "")
        results.append((p.name, code, took, verdict, out))
        label = {0: "PASS", 1: "FAIL", 2: ("ALLOW/INCONCLUSIVE" if accept_outcome(p.name, code, allowances, sys.platform, today) else "FAIL/INCONCLUSIVE"), 3: "TIMEOUT"}.get(code, f"EXIT{code}")
        print(f"    {label} ({took:.0f}s) {verdict[:90]}")

    print("\n" + "=" * 78)
    print(f"{'PROBE':<42} {'RESULT':<18} {'TIME':>6}")
    print("-" * 78)
    failed = []
    reported = []
    for name, code, took, verdict, out in results:
        label = {0: "PASS", 1: "FAIL", 2: ("ALLOW/INCONCL" if accept_outcome(name, code, allowances, sys.platform, today) else "FAIL/INCONCL"), 3: "TIMEOUT"}.get(code, f"EXIT{code}")
        print(f"{name:<42} {label:<18} {took:>5.0f}s")
        accepted = accept_outcome(name, code, allowances, sys.platform, today)
        allowance = next((entry for entry in allowances if entry['probe'] == name and entry['platform'] == sys.platform), None)
        reported.append({'probe': name, 'exitCode': code, 'accepted': accepted,
                         'seconds': took, 'verdict': verdict, 'output': out,
                         'allowance': allowance if code == 2 and accepted else None})
        if not accepted:
            failed.append((name, out))
    print("=" * 78)
    passed = sum(1 for _, c, _, _, _ in results if c == 0)
    skipped = sum(1 for name, c, _, _, _ in results if c == 2 and accept_outcome(name, c, allowances, sys.platform, today))
    print(f"{passed} passed · {len(failed)} failed · {skipped} explicitly allowed inconclusive")

    for name, out in failed:
        print(f"\n----- {name} output -----")
        print("\n".join(out.splitlines()[-25:]))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'platform': sys.platform, 'binary': binary,
        'allowancePolicy': str(args.allow_inconclusive), 'success': not failed,
        'results': reported}, indent=2) + '\n')
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
