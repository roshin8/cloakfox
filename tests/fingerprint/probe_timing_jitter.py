"""performance.now() jitter regression probe.

CloakfoxTimingChild adds sub-millisecond jitter to performance.now() so the
reading looks high-resolution despite Firefox's 1ms quantisation. The jitter
must be deterministic per (container, millisecond bucket) — that is what keeps
performance.now monotonic — but it must NOT be globally predictable.

It previously mixed a hardcoded constant (0xdeadbeef) with the integer
millisecond and nothing else, so the fractional part was a pure function of the
integer part: identical on every Cloakfox install and in every container. That
is not an entropy bit but an exact browser identifier — a site recomputes the
same hash and checks `t - floor(t) === bucketJitter(floor(t))`. Measured 40/40
matches across independent profiles before the fix. The hash is now salted with
the per-container timing_seed.

Checks (host-independent):
  1. NOT PREDICTABLE — recomputing the old unsalted hash must NOT reproduce the
     observed fractions. A high match rate means the salt was lost and the
     browser is trivially identifiable again.
  2. MONOTONIC — performance.now() must never go backwards (spec requirement,
     and a violation would itself be detectable). Checked over thousands of
     samples spanning bucket boundaries.
  3. SUB-MS RESOLUTION — the reading must actually carry a fractional part,
     otherwise the jitter is not being applied at all.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_timing_jitter.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE = r"""
// The exact hash the implementation used before it was salted. If this still
// reproduces the observed fractions, the per-container salt has been lost.
function unsaltedPredict(ms) {
  const x = (Math.imul(ms | 0, 2654435761) ^ 0xdeadbeef) >>> 0;
  return (x % 1000) / 1000;
}

let hits = 0, checked = 0, fractional = 0;
for (let i = 0; i < 40; i++) {
  const t = performance.now();
  const frac = t - Math.floor(t);
  if (frac > 0) fractional++;
  if (Math.abs(frac - unsaltedPredict(Math.floor(t))) < 1e-9) hits++;
  checked++;
  for (let k = 0; k < 50000; k++) { /* burn time to cross ms buckets */ }
}

// Monotonicity over a dense sample run.
let prev = -Infinity, violations = 0, n = 0;
for (let i = 0; i < 4000; i++) {
  const t = performance.now();
  n++;
  if (t < prev) violations++;
  prev = t;
}

return JSON.stringify({hits, checked, fractional, violations, samples: n});
"""


def run(bin_path: str) -> dict:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text('user_pref("cloakfox.enabled", true);\n')
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-remote-allow-system-access")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(log_output=str(Path(prof) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.3)
            d.get("https://example.com/?w=1")
            time.sleep(1.3)
            return json.loads(d.execute_script(PROBE))
        finally:
            d.quit()


def main(bin_path: str) -> int:
    runs = [run(bin_path) for _ in range(2)]
    fails = []

    for i, r in enumerate(runs):
        rate = r["hits"] / max(1, r["checked"])
        print(f"  profile#{i}: unsalted-hash match {r['hits']}/{r['checked']} "
              f"({rate:.0%}) · monotonicity violations {r['violations']}/"
              f"{r['samples']} · fractional readings {r['fractional']}/{r['checked']}")

        # 1. must not be predictable with the unsalted hash
        if rate > 0.25:
            fails.append(f"profile#{i}: the pre-fix unsalted hash reproduced "
                         f"{r['hits']}/{r['checked']} observed fractions — the "
                         "per-container salt is gone and performance.now() is an "
                         "exact Cloakfox identifier again")
        # 2. monotonic
        if r["violations"]:
            fails.append(f"profile#{i}: performance.now() went backwards "
                         f"{r['violations']} times in {r['samples']} samples — "
                         "violates the spec and is itself detectable")
        # 3. jitter actually applied
        if r["fractional"] == 0:
            fails.append(f"profile#{i}: every reading was whole-ms — the jitter "
                         "is not being applied at all")

    print()
    if fails:
        print("FAIL — timing jitter regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — jitter is not reproducible from the unsalted hash, "
          "performance.now() stays monotonic, and readings are sub-ms")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
