# SAB linkability investigation: single-device baseline

## Outcome

The requested cross-identity tracking hypothesis remains unproven. A native SAB
clock produced often-repeatable workload measurements across browser launches,
containers, and local origins on one physical machine. There were also sizeable
outliers. Without other devices, neither uniqueness nor false-match rates can
be estimated. The installed browser did not apply our requested distinct
personas, so this is not a validation of current Cloakfox identity isolation.

No production code, shipping preferences, or existing user profiles changed.

## Verified experiment

- Installed Cloakfox `146.0.1-beta.25`, runtime build `20260502035605`.
- Executable: `/Applications/Cloakfox.app/Contents/MacOS/cloakfox`.
- XUL SHA-256: `37195903f93d350ffd9bf483acff05a5e61cf5381cf0ec619e54b8e9889af345`.
- Six fresh temporary profiles and browser launches, sequentially on one host.
- Each launch tested actual container IDs 1 and 2 on `127.0.0.1` and `localhost`.
  The privileged principal check verified all 24 container IDs. These are local
  loopback origins, not a test of production-site persona routing.
- Four cases per launch, with execution order reversed on alternating launches.
- Each page measured five workloads 40 times after 12 warmup rounds: 4,800
  retained samples. Each workload returned the same checksum in all 960 samples.
- A dedicated worker continuously incremented a shared atomic counter. The main
  thread measured counter differences around computations, without timestamps.
  The worker was terminated after each page run. No artificial counter batch
  pauses were present in the final experiment.
- `cloakfox.enabled=true`; both SAB jitter and SAB serialization explicitly off.
  This is a native-clock baseline, not a test of either proposed mitigation.
- Workloads: 20,000 and 200,000 dependent integer operations; 40,000 dependent
  square roots; 100,000 dependent pointer reads over 128 KiB and 8 MiB arrays.

## Results

The unit of the following descriptive statistics is a page-run median (40
measurements), not an individual sample. Typical deviation means median
absolute deviation divided by the median of the 24 page-run medians. It is not
a confidence interval or a bound on future variation.

| Workload | Median counter delta | Typical deviation | Largest deviation |
|---|---:|---:|---:|
| Integer 20k | 18,242.5 | 0.510% | 33.51% |
| Integer 200k | 173,842.25 | 0.077% | 21.38% |
| Square root 40k | 92,455.5 | 0.063% | 20.97% |
| Pointer reads, 128 KiB | 127,139.25 | 1.088% | 50.82% |
| Pointer reads, 8 MiB | 3,190,608.25 | 3.693% | 14.65% |

The largest deviations occurred in the first page of the sixth launch. Their
cause was not measured; do not attribute them to a specific scheduler, power,
thermal, or background-load effect. All outliers were retained.

A long-versus-short integer-workload threshold fitted on the first three
complete browser launches classified 947 of 960 samples correctly in the last
three launches (98.65%). This is only a positive control demonstrating a useful
measurement instrument. It is explicitly NOT device-identification accuracy.

## Excluded attempts and environment limitations

The first attempt used a counter that yielded after 1,048,576 increments. Its
8 MiB workload medians repeatedly equalled that artificial batch size, while
other workloads often returned zero. That run was stopped and excluded from
the results above; its partial data remains as `raw.json` for transparency.

The installed browser returned the same native macOS user agent in both
containers despite distinct Windows/Linux test overlays. Adding the legacy
`roverfox.s.*` overlay namespace did not satisfy the persona preflight either.
This establishes a failed test setup, not the root cause of a product bug.
No verified spoofed-persona results are claimed.

The local development binary at
`firefox-src/obj-aarch64-apple-darwin/dist/bin/cloakfox` exited with
`Couldn't load XPCOM.` Selenium initially selected stock Firefox 155 instead;
the user-agent preflight rejected that run. Subsequent runs explicitly pinned
the geckodriver executable to prevent automatic browser substitution. Only
installed Cloakfox runtime build 20260502035605 appears in the final dataset.

## Reproduction artifacts

Exploratory scripts and raw data are under
`/tmp/cloakfox-sab-linkability.yH3kaZ/` (temporary, not a maintained regression
suite): `experiment.py`, `experiment.js`, `analyze.py`, `baseline-raw.json`, and
`summary.json`. The earlier excluded partial run is `raw.json`.

```sh
SAB_BASELINE=1 uv run --with selenium python /tmp/cloakfox-sab-linkability.yH3kaZ/experiment.py
uv run python /tmp/cloakfox-sab-linkability.yH3kaZ/analyze.py
node --check /tmp/cloakfox-sab-linkability.yH3kaZ/experiment.js
```

The analysis asserts complete coverage of the 24 cases, correct container IDs,
cross-origin isolation, 200 samples per case, and consistent workload checksums.
All those checks and JavaScript syntax validation passed. Browser processes
created by this experiment were closed.

## What would answer the tracking question

A runnable current Cloakfox build must first pass distinct-persona preflight.
Then collect multiple sessions and identities from multiple physical devices,
including similar hardware. Train any matching rule on separate sessions from
the evaluation sessions; report true-match and false-match rates without
tuning on the evaluation data. Repeat over longer periods and controlled load
and power changes. The present short single-host run supplies neither those
negative controls nor those robustness conditions.

These results support investigating SAB-derived features. They do not establish
a reliable device identifier, justify a particular performance penalty, or
prove that current Cloakfox identities can be linked.
