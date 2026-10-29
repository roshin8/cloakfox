# Independent review: full fpgen GPU expansion

Reviewed the scoped uncommitted importer, generator, generated evidence/registries,
native OS binding, observed-GPU settings explanation, tests/probes and task docs.
Unrelated changes were excluded. No actionable P1/P2 findings were identified.

Verified from the pinned archive and generated artifacts:

- 886 conditional paths and 1,183 contexts; 23 admitted paths deduplicate into
  nine Windows identities. Incomplete/foreign-owner paths remain blocked.
- The four protected profiles are unchanged. The original three observed
  profiles retain their codes and complete JSON contents, apart from added
  source lineage. Existing descriptors therefore retain their catalog identity.
- Every admitted path has the same full observed GL parameter values as an
  equivalent legacy seed, except the renderer label. This comparison includes
  miscellaneous mutable initial state omitted from the generator's static
  projection; no new mismatches were found in the actual pinned inputs.
- Generated JS/native selection retains exact renderer/vendor and OS matching.
  Owner, secret, source/policy descriptor checks and native execution admission
  remain required. This expansion does not alter privacy exclusions or toggles.
- Scoped probes cover both worker modes, blank frames, resource operations,
  precise/PBO readback protection, owners, sites and restart persistence. Their
  expected HMAC values are explicitly described as source-derived expectations,
  not measurements of otherwise-private native state.

Checks run successfully: full and legacy offline importer `--check`, generator
`--check`, five full-import tests, six generator tests and three observed JS
profile tests. The importer reproduction also verifies the compressed corpus
against its checked-in bytes. No browser, application build or installed/profile
mutation was performed during this review.

This is a source/data review, not a runtime sign-off. The separate Firefox 159
build and headless runtime probes were still pending at review time; their actual
results must be reported separately before claiming native execution coverage.

## Follow-up: library probe and build manifest sorting

One P2 finding in the newly added `probe_full_gpu_libraries.py`: lines 135 and
149 hash optional canvas results without validating that real images were
collected. `stable_hash(None)` or a stable FingerprintJS canvas sentinel can
therefore satisfy the repeat assertion at line 154 and be reported as equal
cross-owner pixels at line 164. Require a nonempty `data:image/` CreepJS dataURI
and actual FingerprintJS rawCanvas geometry/text images before making those
comparisons; missing/sentinel values must fail collection checks.

The GPU identity and capability assertions are nonvacuous, and the shared
CreepJS recognition helper rejects missing collectors/trash reports. Fixture
verification checks the clean pinned CreepJS checkout and both library bundle
hashes. WebGPU absence is explicitly inconclusive; exceptions fail. Coverage is
correctly limited to one sample per identity with repeat/second-owner coverage
only for the first identity. This probe complements native privacy/resource
tests; it does not itself exercise precise/PBO readback controls.

The `moz.build` change only sorts existing entries: comparing sorted before/after
lines confirms no additions/removals. Python AST parsing of the new probe passed.
The coordinator reports a successful native build; this reviewer did not run a
build or browser, and runtime results were still pending in this follow-up.

Scoped fix recheck: the new `canvas_evidence` helper rejects missing/sentinel/
empty images, and its two tests passed. However, the first integration overwrote
the helper result with CreepJS `canvasWebgl` before reading `sha256`/`collected`,
causing a `KeyError` in the CreepJS branch. Keep the image-evidence variable
separate from the WebGL collector before running the runtime probe.

Final scoped recheck: resolved. `summarize_library` now keeps `image_evidence`
separate from the WebGL collector and checks collection before reporting hashes.
Repeat checks require collected images; cross-owner equality is null when
collection failed. All three tests pass, including the actual CreepJS summary
path with valid and missing image evidence. The P2 and its integration blocker
are closed; runtime execution remains the coordinator's separate validation.

Worker fixture correction source-confirmed: `WorkerNavigator.webidl:10` includes
`NavigatorID`; that mixin declares `platform` at `Navigator.webidl:55`, while
`oscpu` is declared only on a partial `Navigator` interface at line 179. The
updated probe requires the owned platform and `hasOscpu=false` for both classic
and module workers (with undefined serialized as null), and requires both owned
platform/oscpu plus `hasOscpu=true` for the blank window frame. This corrects the
fixture's unsupported worker property expectation without relaxing an exposed
identity assertion. The coordinator reports 16 corresponding fixture failures
in preserved attempt 1; the full native/library reruns remain pending. No browser
was run for this source confirmation.

Final targeted fixture review: pinned FingerprintJS `dist/fp.cjs.js:2794`
explicitly avoids debug-renderer information on Gecko. The corrected probe
requires its intentionally empty unmasked fields, nonempty masked basics and
six numeric capabilities. Separate, clearly labeled native WebGL1/2 queries
still require the exact catalog vendor/renderer; no upstream library is edited.
All four library helper tests pass.

Reference-mode restart setup now persists explicit reference/observed choices
through `setOverrides`, with the exact GPU/OS identity required by its preflight,
then applies saved overrides. This matches `applyOverrides`, which distinguishes
an absent observed choice from explicit false and defaults eligible identities
to observed mode only when absent. Saved choices are checked before and after
restart, while exact descriptor and secret assertions remain intact. No further
actionable findings in these scoped fixture corrections. The coordinator reports
8,383 observed native checks and 1,052 backend checks passing; corrected library
and protected-reference runtime reruns are separate pending validation.

Review closed after the final settings-probe update. Its obsolete three-name /
106-record expectation is replaced with executable-catalog identity count, OS,
families, full-corpus path count, admission exclusions, local/no-upload wording,
persona providers and the same pinned release link. This preserves the intended
coverage/limitations check for the expanded UI. The restart fixture uses the
normal manual-override validation path; existing privacy and exact descriptor
assertions remain present. No open actionable review findings remain.

Latest coordinator-reported runtime status: protected reference 1,707 checks,
libraries 167 checks and fpgen 59 checks pass. The final nine-identity native run
with explicitly saved toggles is pending; prior native/backend results above
remain separate evidence. These reported runtime counts were not independently
rerun by this reviewer. Reproduce this review's executable checks from the repo
root with the two importer `--check` commands in `importer.md`, generator
`python3 scripts/generate-gpu-reference-profiles.py --check`, Python unittest
discovery for `test_full_gpu_reference_import.py`,
`test_gpu_reference_generator.py`, `test_full_gpu_libraries.py`, and
`node --test tests/fingerprint/test_gpu_observed_profiles.mjs`.

Coordinator final runtime receipt: all final runs completed successfully, including 8,419 observed-profile checks with explicit saved toggles, 1,707 protected-reference checks and 167 library checks. Total11,948 checks across ten probes; no failures or inconclusive outcomes. See acceptance-summary.json and archived raw reports. This paragraph records execution evidence separately from the independent source review.
