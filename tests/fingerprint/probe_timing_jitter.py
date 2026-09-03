"""Native performance.now() presentation regression probe.

The visible clock must be keyed for windows and workers without replacing the
native Performance.prototype.now method. The keyed interpolation must remain
monotonic and stable across reloads in one browser session.

Exit codes: 0 pass · 1 regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_timing_jitter.py
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE = r"""
const done = arguments[arguments.length - 1];

(async () => {
  const target = 2000;
  if (performance.now() < target) {
    await new Promise(resolve => setTimeout(resolve, target - performance.now()));
  }
  const proto = Object.getOwnPropertyDescriptor(Performance.prototype, "now");
  const own = Object.getOwnPropertyDescriptor(performance, "now");
  return {
    samples: Array.from({length: 4000}, () => performance.now()),
    ownNow: !!own,
    nativeNow: !!proto && Function.prototype.toString.call(proto.value)
                      .includes("[native code]"),
    workerSamples: await new Promise((resolve, reject) => {
      const src = `postMessage(Array.from({length: 256}, () => performance.now()))`;
      const worker = new Worker(URL.createObjectURL(
        new Blob([src], {type: "text/javascript"})));
      worker.onmessage = event => resolve(event.data);
      worker.onerror = reject;
    }),
  };
})().then(done, error => done({probeError: String(error)}));
"""


def run(bin_path: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            'user_pref("cloakfox.enabled", true);\n', encoding="utf-8"
        )
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(
            options=opts,
            service=Service(
                service_args=["--allow-system-access"],
                log_output=str(Path(prof) / "g.log"),
            ),
        )
        try:
            d.set_page_load_timeout(30)
            d.set_script_timeout(30)
            loads = []
            for query in ("first", "second"):
                d.get(f"https://example.com/?timing_probe={query}")
                time.sleep(1.3)
                loads.append(d.execute_async_script(PROBE))
            return loads
        finally:
            d.quit()


def is_monotonic(samples: list[float]) -> bool:
    return all(
        current >= previous
        for previous, current in zip(samples, samples[1:])
    )


def has_fraction(samples: list[float]) -> bool:
    return any(
        not math.isclose(value, round(value), rel_tol=0.0, abs_tol=1e-9)
        for value in samples
    )


def bucket_fractions(samples: list[float]) -> dict[int, float]:
    observed: dict[int, set[float]] = {}
    for value in samples:
        bucket = math.floor(value)
        observed.setdefault(bucket, set()).add(round(value - bucket, 12))
    return {
        bucket: next(iter(fractions))
        for bucket, fractions in observed.items()
        if len(fractions) == 1
    }


def unsalted_predict(ms: int) -> float:
    x = ((ms & 0xFFFFFFFF) * 2654435761) & 0xFFFFFFFF
    x ^= 0xDEADBEEF
    return (x % 1000) / 1000


def main(bin_path: str) -> int:
    try:
        loads = run(bin_path)
    except Exception as error:
        print(f"ERROR — timing probe could not run: {error}")
        return 2

    fails = []
    for index, result in enumerate(loads, start=1):
        if "probeError" in result:
            fails.append(
                f"load#{index}: JavaScript probe failed: {result['probeError']}"
            )
            continue

        samples = result["samples"]
        worker_samples = result["workerSamples"]
        print(
            f"  load#{index}: main={len(samples)} worker={len(worker_samples)} "
            f"own-now={result['ownNow']} native-now={result['nativeNow']} "
            f"main-fractional={has_fraction(samples)} "
            f"worker-fractional={has_fraction(worker_samples)}"
        )

        if not is_monotonic(samples):
            fails.append(f"load#{index}: window performance.now() decreased")
        if not has_fraction(samples):
            fails.append(f"load#{index}: window performance.now() stayed whole-ms")
        if result["ownNow"]:
            fails.append(f"load#{index}: performance has an own now property")
        if not result["nativeNow"]:
            fails.append(f"load#{index}: Performance.prototype.now is not native")
        if not is_monotonic(worker_samples):
            fails.append(f"load#{index}: worker performance.now() decreased")
        if not has_fraction(worker_samples):
            fails.append(f"load#{index}: worker performance.now() stayed whole-ms")

        fractions = bucket_fractions(samples)
        predictable = sum(
            math.isclose(
                fraction,
                unsalted_predict(bucket),
                rel_tol=0.0,
                abs_tol=1e-9,
            )
            for bucket, fraction in fractions.items()
        )
        if fractions and predictable / len(fractions) > 0.25:
            fails.append(
                f"load#{index}: unsalted hash reproduced {predictable}/"
                f"{len(fractions)} observed bucket fractions"
            )

    if len(loads) == 2 and all("samples" in load for load in loads):
        first = bucket_fractions(loads[0]["samples"])
        second = bucket_fractions(loads[1]["samples"])
        shared = sorted(first.keys() & second.keys())
        stable = [
            bucket
            for bucket in shared
            if math.isclose(
                first[bucket], second[bucket], rel_tol=0.0, abs_tol=1e-9
            )
        ]
        print(f"  reload coherence: {len(stable)}/{len(shared)} shared buckets stable")
        if not shared:
            fails.append("reloads observed no common integer bucket")
        elif len(stable) != len(shared):
            fails.append(
                f"reload interpolation changed for {len(shared) - len(stable)}/"
                f"{len(shared)} shared buckets"
            )

    print()
    if fails:
        print("FAIL — timing presentation regressed:")
        for failure in fails:
            print(f"  - {failure}")
        return 1

    print(
        "PASS — native window and worker clocks are fractional, monotonic, "
        "and reload-coherent"
    )
    return 0


if __name__ == "__main__":
    binary = os.environ.get("CLOAKFOX_BIN")
    if not binary or not os.path.exists(binary):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(binary))
