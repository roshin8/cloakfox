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

Exit code: 0 if every probe passed (2/inconclusive is not a failure), else 1.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Probes that need a special environment or are one-off spikes rather than
# regression tests, with the reason they are skipped by default.
SKIP = {
    "probe_font_spike.py": "phase-0 spike, needs a hand-staged test font",
    "run_all.py": "this driver",
}


def discover() -> list[Path]:
    return sorted(p for p in HERE.glob("probe_*.py") if p.name not in SKIP)


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
    args = ap.parse_args()

    probes = discover()
    if args.k:
        probes = [p for p in probes if args.k in p.name]

    if args.list:
        for p in probes:
            print(p.name)
        for name, why in SKIP.items():
            print(f"{name}  (skipped: {why})")
        return 0

    binary = os.environ.get("CLOAKFOX_BIN")
    if not binary or not os.path.exists(binary):
        print("CLOAKFOX_BIN not set or binary missing", file=sys.stderr)
        return 2
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
            try:
                cp = subprocess.run([sys.executable, str(p)], capture_output=True,
                                    text=True, timeout=args.timeout,
                                    env={**os.environ})
                code, out = cp.returncode, (cp.stdout or "") + (cp.stderr or "")
            except subprocess.TimeoutExpired:
                code, out = 3, f"TIMEOUT after {args.timeout}s"
            if code in (0, 2) or attempts > args.retries:
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
        label = {0: "PASS", 1: "FAIL", 2: "SKIP/INCONCLUSIVE", 3: "TIMEOUT"}.get(code, f"EXIT{code}")
        print(f"    {label} ({took:.0f}s) {verdict[:90]}")

    print("\n" + "=" * 78)
    print(f"{'PROBE':<42} {'RESULT':<18} {'TIME':>6}")
    print("-" * 78)
    failed = []
    for name, code, took, verdict, out in results:
        label = {0: "PASS", 1: "FAIL", 2: "SKIP/INCONCL", 3: "TIMEOUT"}.get(code, f"EXIT{code}")
        print(f"{name:<42} {label:<18} {took:>5.0f}s")
        if code not in (0, 2):
            failed.append((name, out))
    print("=" * 78)
    passed = sum(1 for _, c, _, _, _ in results if c == 0)
    skipped = sum(1 for _, c, _, _, _ in results if c == 2)
    print(f"{passed} passed · {len(failed)} failed · {skipped} skipped/inconclusive")

    for name, out in failed:
        print(f"\n----- {name} output -----")
        print("\n".join(out.splitlines()[-25:]))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
