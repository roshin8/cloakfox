# Required upstream fingerprint library gates

CreepJS and FingerprintJS are required CI runtime audits for both engines. Gecko runs the existing full audit on macOS and Linux (headed under Xvfb on Linux); Chromium runs its native companion audit on macOS arm64. Pinned setup checks upstream revision/package-lock and bundle SHA256 before execution. Upstream JavaScript and detector warnings are preserved unchanged.

Gecko tests eight cases, three samples of each library per case: native control, protected default, two containers, another site, Chrome-identity cases and return to the original site. It checks real collection, repeatability, window/worker identity, CSS agreement and canvas/audio isolation. This remains a regression contract, not certification of undetectability.

Chromium tests six cases with three **distinct document loads** of each library: A, B, A on another site, A returning, and two master-off controls with different seeds. The audit requires successful library components, finite positive audio samples (timeout/unsupported sentinels fail), native window/worker and CSS agreement, stable reloads, canvas/visitor-ID separation and original-site restoration. Master-off results must ignore container seeds. It does not claim that Chromium implements audio/font/screen/WebRTC isolation or cross-OS masking; those remain privacy parity gaps. The source-built native suite separately verifies implemented WebGL/WebGPU behavior.

Every required library step is a hard gate. Gecko collects other diagnostics after an audit failure, then its final always-run gate rejects any failed, cancelled or skipped required step. Chromium fails immediately on an audit error. CI uploads raw library samples, partial failures and detector flags. Missing fixtures/binaries, timeouts and incomplete samples cannot be accepted as successful library runs.

## Inconclusive policy

`tests/fingerprint/run_all.py` treats exit2 as failure by default, retries it under the existing retry policy, and writes a JSON verdict for each result. Its repository policy is [inconclusive-allowances.json](../../tests/fingerprint/inconclusive-allowances.json), currently empty. An allowance needs all four fields:

```json
{"probe":"probe_example.py","platform":"linux","reason":"Tracked hardware limitation with investigation reference","expires":"2026-10-20"}
```

Only that exact probe/platform may return2 through the inclusive expiry date (UTC). Wildcards, blank reasons, invalid dates and duplicate entries are rejected. Exit1, timeouts/crashes and invalid/missing setup still fail. Allowed inconclusive outcomes remain labelled as such, with reason/expiry in the report; they never become PASS. The font spike is a documented standalone experiment outside the regression suite; the library audit is excluded from run_all only because CI invokes it as a separate mandatory gate.

Chromium's existing unit runtime driver also rejects unexpected skipped native classes; its two explicit exclusions are full-Xcode-versus-CLT characterization and source replay, which is validated in the source-build stage. They do not waive library collection.

## Local verification

[Saved evidence summary](required-libraries-20261015/local-results.json): installed Gecko158 passed48 library executions/456checks; the existing source-built Chromium154 graphics/persona companion passed36executions/440checks. Raw personal-machine reports remain local under `/tmp/cloakfox-gecko-required-libraries` and `/tmp/cloakfox-chromium-required-libraries-final`; CI produces its own reports from fresh hosted artifacts. No native identity/locale increment verification is implied by the Chromium audit.

Seven policy/contract tests, five fixture-integrity tests, eight CI helper tests and actionlint pass. Mutation cases reject audio failure sentinels, missing samples, unstable canvas, worker disagreement and still-masked native controls. An owned CLI fixture proves unallowed exit2 makes the whole probe suite fail and an exact unexpired allowance is recorded correctly.

The prior hosted Chromium source run stopped before compilation on CEF's unprefixed tarball patch header. The CI helper now applies only those archive patches with `git apply -p0`; normal native patches keep their normal prefix. An integration fixture and replay of the actual pinned CEF patch against pristine pinned depot_tools verify the repair. Hosted full-source/runtime verification remains pending; the ongoing local native build is unchanged.
