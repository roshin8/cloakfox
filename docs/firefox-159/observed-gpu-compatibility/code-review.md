# Independent observed GPU review

Review baseline: `65117fec36`. Reviewer inspected the current additions policy,
generator/catalog, settings handlers, offline audit and probe changes on
2026-10-28. The native freeze and subsequent test-fixture deltas were reviewed below.
No browser was launched, no browser build was run, and no production file was
modified by this reviewer.

## Findings and resolution

- **P2 — library recognition assertion can pass when WebGL was not collected.**
  `tests/fingerprint/probe_fingerprint_libraries.py:267` checks only absence of
  two trash entries. It does not require `fingerprint.canvasWebgl` or its
  parameters. The pinned CreepJS `src/webgl/index.ts:269–273` returns without
  collecting WebGL when context creation fails, while other fingerprint
  components still finish. Its detection guards also do nothing with missing
  parameters. Require a real collected WebGL component and populated parameter
  set/renderer before declaring recognition; add a negative missing-component
  fixture. Resolved during review: `library_audit_common.observed_gpu_recognized` now requires the collected WebGL hash, renderer, texture/viewport/index/LOD parameters and an explicit warning array. The probe calls this helper. Independent rerun of `test_observed_gpu_recognition.py`: 3 passed, including absent collector/parameters/hash and both detector warnings. No remaining action for this finding.

## Verified current behavior

- Generated observed records are exactly Intel, AMD and Nvidia codes
  `36866`, `36867`, `36868`; descriptor version 4 and mode
  `observed-reference` are independently validated in JS and native core.
- All four previous executable reference profile objects compare equal to the
  baseline. Existing Apple reference capability/precision adaptations remain.
  Apple has no observed catalog entry, so the observed request fails admission.
- Native `ForGlobal` takes the principal's exact container owner, rejects
  foreign descriptor owners and malformed observed booleans, requires reference
  request `true`, selects the exact eligible complete catalog, and retains
  site/secret binding. Client context creation requires canonical backing and
  captures profile/config once, including restoration and offscreen owner guards.
- UI and override writes preflight the full requested change, disable observed
  together with reference, preserve recovery by allowing saved requests to turn
  off after dependency loss, and retain other owners' identity/overrides.
- The offline audit is diagnostic only and does not enter production admission;
  production profiles contain complete records rather than detector hash values.
  The live library probe verifies pinned unmodified fixture provenance.

## Reviewer validation

- `node --test tests/fingerprint/test_gpu_observed_profiles.mjs tests/fingerprint/test_container_rendering_options.mjs tests/fingerprint/test_observed_gpu_audit.mjs`: 18 passed, 0 skipped.
- `python3 scripts/generate-gpu-reference-profiles.py --check`: passed.
- Parsed baseline and current `gpu-reference-executable.json`: old `profiles`
  arrays equal; observed catalog contains exactly the three codes above.

The source review below covers typed bias/state/index behavior. Runtime certification is recorded separately in the coordinator’s phase receipts and final acceptance summary.

## Frozen native source review

Reviewed `cloakfox-observed-gpu-execution.patch` SHA256
`5ff59fcb984245e7b47554924276a52cb20aff8a8f7ce3797dee8e03c61d0e45`.
Independently recomputed all six source checksums and the patch checksum against
`/tmp/cloakfox-observed-native-freeze.json`; all match. No native source blocker
identified in this snapshot.

- Stencil defaults are initialized through `fStencilFuncSeparate` and
  `fStencilMaskSeparate` before Gecko reads/caches the real GL masks. Author
  changes still use the existing state mutation path.
- The typed fragment AST pass enumerates all nine ANGLE texture bias operators,
  including legacy 3D forms. It wraps only the final scalar bias expression in
  native `clamp(-2,2)`, with postorder traversal retaining nested/side-effecting
  expressions once. Explicit LOD, gradient calls and user functions remain on
  their existing operators.
- The embedder resource defaults to zero and only observed profile codes select
  two. Compiler resource serialization includes the field, avoiding policy
  collision in the translator resources key. Existing exact-owner context policy
  capture supplies the code on context creation/restoration.
- The observed WebGL2 element maximum is `0xfffffffe`. Existing
  `WebGLBuffer::GetIndexedFetchMaxVert` already ignores `UINT32_MAX` as the fixed
  restart marker, with the backend restart machinery retained. This does not
  require a new validation/getter exception.
- The source/native core review does not replace runtime rendering, state,
  resource, restoration or compiler reuse evidence. Those checks are owned by
  the implementation coordinator and were not launched by this reviewer.

## Native runtime helper source review

Reviewed `tests/fingerprint/observed_gpu_execution.js` and its integration in
`probe_gpu_reference_profiles.py` for every observed profile owner, in both
windows and dedicated workers. The result is nonvacuous: each requested WebGL
context contributes a creation assertion, exceptions contribute a failure, the
caller requires nonempty checks and two contexts, and every returned assertion
is added to the probe's failure gate.

The helper exercises actual stencil rejection/write-mask drawing, distinct
nonblack mip colors for positive/negative dynamic and constant/projective bias,
WebGL2 offset variants, explicit LOD eight, and legal fixed uint32 restart with
ordinary/range/instanced calls and restart-only drawing. It retains the strict
readback policy. Syntax checks for JS and Python integration passed.

A test-fixture sequencing concern was sent to the coordinator: the initial
single-evaluation shader constructed `vec4(texture(...takeBias()).rgb,
calls==1.?1.:0.)`, relying on GLSL argument evaluation order. Explicitly assign
the sampled color to a local before inspecting `calls` to avoid a false failure.
Resolved by the coordinator using `sampleOnce()` with an explicitly sequenced local sample. At the coordinator's explicit request this reviewer added a test-only back-facing draw. Its first version incorrectly used unequal effective front/back references and write masks; Gecko correctly rejected those draws under WebGL's matching-state restriction, causing a preserved failed probe. This was a reviewer fixture error, not a production defect. The corrected helper retains equal effective references, value masks and write masks for every draw, while using front NEVER and back ALWAYS/EQUAL comparisons after reversing face classification. Both zero write masks preserve stencil9 during an attempted stencil10 write. It requires green then yellow fragments and four explicit no-error assertions, restores CCW classification, and passes JS syntax checking. Native source remains unchanged. Live probe output remains the coordinator's responsibility.

Reviewed subsequent test-only deltas: settings controls are now scrolled centrally
and center-point hit-tested before real WebDriver clicks, retaining the actual
settings event handlers. Observed library fixtures assign Intel to A, AMD to B
and Nvidia to default/Chrome, exercising all three admitted families while
preserving the previous reference-only library layout. No blocker found in these
deltas. Final saved runtime evidence remains to be reviewed.

Reviewed the subsequent `probe_canonical_geometry.py` synchronization delta:
the existing 10-second wait now also requires the fixed `100vw`/`100vh` content
probe to converge to the privileged selected-browser bounds within one app unit
(`1/60` CSS px). This waits for the separate asynchronous WebDriver resize while
retaining the existing actual resolution, canonical fixed geometry, screenshot
and layout assertions. Timeout still records failure. No production change or
acceptance-oracle relaxation was identified.

The first geometry synchronization review missed that this probe's privileged
`chrome()` helper leaves the driver in chrome context. The coordinator's rerun
caught the resulting missing content element; the corrected wait explicitly
restores content context before reading `viewportProbe`. This is a fixture
context correction, with all validation conditions retained.

Reviewed the font metric regression fixture correction: it now pins a public,
disposable internal HMAC secret alongside the existing base seeds/fonts, then
asserts those actual saved inputs before measurement. This removes an unpinned
random input from a two-sample quantized-width comparison. Existing native
baseline, noise magnitude, different-seed and same-profile restart assertions
are unchanged. No production edit or acceptance-oracle relaxation identified.


## Final independent verdict

No remaining actionable source or acceptance-evidence blocker was found for the
scoped optional Windows observed mode. The earlier recognition assertion finding
is resolved. Test-only fixture mistakes and their corrections are retained above;
production validation was not relaxed to accommodate them.

Independently verified against current files and raw results:

- All six native source hashes plus the tail patch still match the recorded
  freeze. The tested app's executable, XUL and four canonical backend artifacts
  match `acceptance-app.json`; all five changed app JS/UI resources match current
  source hashes and every recorded app copy. XUL SHA256 is
  `4e747b52fe248fd6e50ed4b618a233352109ee2a86d774b3404d5cda86f6d792`.
- Raw observed results contain 1,431 passing checks, no failures/inconclusive
  entries, three families and six exact owners. Each owner has 51 passing native
  execution assertions in both window and worker, with two context versions.
- Raw old-reference (1,035), backend admission (323), actual settings (82) and
  touch (32) checks have no failures; geometry raw failures are empty. All six
  native phase receipts passed against the same XUL hash.
- The broader receipt preserves 21 passes and the initial font failure. The
  targeted font receipt passes against the same XUL after the reviewed fixture
  repair; therefore each of the 22 regression probes has a passing result.
- Each of the three raw library summaries reports eight cases, three repeats,
  48 library executions and zero assertion failures, totaling 144 executions.
  Rechecked current fixture provenance: the pinned upstream Git state and both
  bundle hashes are unmodified. Re-applied the recognition helper to every raw
  observed CreepJS sample: all protected samples have real collected results
  and pass. Intel/AMD/Nvidia assignments match the claimed cases. Firefox
  identities report empty lie data; Chrome identities retain only the recorded
  WorkerGlobalScope SpiderMonkey/V8 mismatch. Previous modes' detector warnings
  remain present in their saved evidence.
- Final log tails confirm Node 392, Python 196 and CI-helper 16 passes, no skips.
  Re-ran generator `--check`: passed. Patch replay lists 168 successful patches;
  the preserved replay log has no fuzz, offsets, rejects or failures.

The current production diff stays within catalog/policy/settings and the frozen
native patch. The two changed `engines/chromium` files contain generated Gecko
inventory metadata only. This review establishes the recorded macOS arm64
acceptance scope; it does not certify physical vendor-driver emulation or other
host-platform rendering. Apple observed mode remains rejected and the previous
four reference profile objects remain unchanged.
