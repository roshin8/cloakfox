# SAB clock suppression: measured privacy and compatibility tradeoff

## Decision

Firefox's existing `dom.workers.serialized-sab-access` mechanism suppressed the
tested shared-memory clock on both installed Firefox and installed Cloakfox.
It preserves the tested SAB, Atomics wait/notify, and shared Wasm values. It also
increased median completion time of a two-worker workload by 15.3% in four
paired exploratory runs, exceeding the approved 5% performance budget.

No shipping preference changes are justified by these results under the current
budget. The earlier intermittent jitter implementation still has no demonstrated
privacy benefit. These diagnostics replace population-MAD increase as the next
investigation's evidence, not as a new universal privacy acceptance threshold.

## Privacy experiment

One worker increments a shared counter in finite batches. A worker observer and
a main-thread observer read the counter around synchronous fixed workloads of
2,000 or 20,000 dependent integer operations. No timer is used to classify the
workload. Labels are balanced and shuffled in pairs. A threshold is fitted to
100 training observations and scored on 100 held-out observations per realm.
Each policy uses a fresh browser profile. Task-boundary yields allow execution
to progress under serialization without waiting synchronously on another thread.

| Browser/run | Native worker accuracy | Native main accuracy | Serialized worker/main accuracy | Serialized nonzero deltas |
|---|---:|---:|---:|---:|
| Firefox 155.0.1 | 99% | 83% | 50% / 50% | 0% / 0% |
| Cloakfox 146.0.1-beta.25 | 64% | 93% | 50% / 50% | 0% / 0% |
| Cloakfox, serialized-first repetition | 80% | 97% | 50% / 50% | 0% / 0% |

The counter continued to progress across tasks with serialization. This is
evidence of suppression during the tested synchronous measurement intervals,
not proof against all timing channels, cross-session hardware identification,
long-running adversarial workloads, or detection of the serialization policy.
Samples within a browser run are correlated; descriptive confidence intervals
must not be interpreted as independent cross-machine evidence.

Firefox build ID: `20260903215306`. Installed Cloakfox build ID:
`20260502035605`; source revision
`86bb7f6af6312ba3c0161085f854bcdff68f1a91`. Neither installed binary contains the
current branch's SAB jitter feature. Its registered default is absent, and the
probe explicitly marks such a requested policy inconclusive. These results do
not validate the unbuilt current branch.

Raw local artifacts from this investigation:

- `/tmp/sab-privacy-firefox.json`
- `/tmp/sab-privacy-cloakfox.json`
- `/tmp/sab-privacy-cloakfox-reversed.json`

## Compatibility and parallel cost

With serialization enabled in a fresh installed-Cloakfox profile, the existing
correctness fixture returned exact dedicated count 4,096, successful Atomics
wait/notify, and exact shared-Wasm count 4,096. SharedWorker and ServiceWorker
were capability-backed skips on this build.

Two workers then each performed 100,000,000 atomic additions into separate
cache-line-spaced slots of one shared buffer. All final counts were exact.
Browser profiles were fresh; policy order reversed on alternating pairs.
Native completion times in ms:
`[2789.48, 3105.32, 2709.56, 2854.28]`.
Serialized completion times in ms:
`[3260.20, 3246.80, 3279.30, 3248.04]`.
Medians: 2,821.88 ms and 3,254.12 ms; slowdown: 15.3174%.

This exploratory parallel benchmark is deliberately distinct from the earlier
single-worker 5-million-addition benchmark. Passing the latter does not bound
the parallelism lost by serializing shared-memory threads. Four pairs do not
replace the twenty-pair release gate or application-level compatibility tests.

## Reproduction

From the repository root, with Selenium available:

```sh
uv run --with selenium python tests/fingerprint/probe_sab_privacy.py \
  --binary /Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  --output /tmp/sab-privacy.json --policies native serialized
uv run --with selenium python tests/fingerprint/probe_sab_privacy.py \
  --binary /Applications/Cloakfox.app/Contents/MacOS/cloakfox \
  --output /tmp/sab-privacy-reversed.json --policies serialized native
uv run --with selenium python tests/fingerprint/measure_sab_parallel_cost.py \
  --binary /Applications/Cloakfox.app/Contents/MacOS/cloakfox
```

Firefox 146 source routes SAB structured cloning into `JSExecutionManager`
when serialization is enabled. The manager allows one concurrent JS execution
and uses a 50 ms worker time slice. The source warns about deadlocks if a
blocking path fails to yield execution permission. Broader testing of spin
loops, multiple tabs, nested workers, and threaded Wasm remains necessary.

Mozilla describes this mechanism in
[Safely reviving shared memory](https://hacks.mozilla.org/2020/07/safely-reviving-shared-memory/).
An explicit strict-mode performance tradeoff is required before integrating
serialization as a default or product setting. Per-site control would need a
separate design because the current Firefox mechanism is process-global.
