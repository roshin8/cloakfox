# Execution ledger

Approved objective: complete optional canvas rendering pipeline, with no privacy
downgrade and installed-binary acceptance. The full objective remains unfinished.

Ruling: execute the backing/policy project first behind the internal preference,
without a public complete-mode label or extraction cutover. The approved spec
requires these release gates; shipping a smaller implementation as complete would
mislead users and could expose native output. Cost: the complete requested feature
is not available until dependent renderer/font/provenance/GPU projects are done.

Ruling: user explicitly approved architecture and implementation; do not ask for
repeat authorization for this reversible experiment. Existing worktree and prior
changes are preserved; no commit/push is implied by this request.

Task1: strict authoritative preference policy implemented. New tests observed RED
(missing policy/default/backfill), then7 opt-in tests GREEN; full Node258 GREEN.
Public graphics toggles remain independent; no new public checkbox introduced.

Task2: context creation capture and basic Skia-only allocation implemented. Actual
compiled C++ fixtures execute policy, allocation routing, provider backend gates
and creation freezing;3 tests GREEN. Before-feature snapshot proves RED for
borrowed-target enforcement and owner capture. Creation captures exact default or
nondefault container; master-off/system keep native allocation at creation.

Review: fresh reviewer found a misplaced member check in AdjustedTargetForFilter,
causing build failure. Moved it into BorrowTarget. Added actual BorrowTarget code
execution test, RED on previous source and GREEN on corrected source. Native build
then passes. Strict replay139 patches,353 matching targets, no drift/fuzz/offset.

Runtime fixture rulings: omit only timing session-key metadata from restart config
equality, matching existing restart tests; those keys intentionally rotate, while
persona fields, seeds and sentinels stay equal. Firefox prevents changing a typed
Boolean preference to string; test that rejection without policy change instead
of assuming the setter succeeds. Malformed persisted types remain unit-covered.

Development: internal policy12 checks, canvas consistency589, glyph mode40,
settings13, GPU42, graphics privacy and worker-canvas probes pass. Pinned unmodified
CreepJS/FingerprintJS48 executions/456 checks pass. These are consistency/regression
tests, not evidence that known-fill inversion or all native output recovery is
prevented. Installed acceptance is pending below.

Outstanding full release: canonical fonts/shaping/raster, image/SVG/media upstream
producers, privacy provenance through copies/bitmaps/workers/video/GPU transfers,
canonical GPU rendering, cross-host differential acceptance and safe removal of
extraction noise. Sources/fonts are available; their portable integration is not
implemented. Do not mark the full pipeline complete.

Installed acceptance: backing policy12, settings13, GPU42, graphics+worker guards
pass; on/off/all-three matrix1767 canvas checks and144 library runs/1368checks
pass. Python58/Node258 pass. Original glyph probe38/40: first HTML off sample
mismatched later off/wrong-type hashes. Instrumented diagnostic40/40 without
reproduction; cause unresolved, do not treat a clean retry as a fix.

Full privacy acceptance FAILS: all6 known-fill cases recover native path/gradient
pixels exactly. Complete renderer not implemented. Previous installed build
restored after test; prototype retained intact at install.json testedAppRetainedAt.
Source/patch/internal-toggle work remains for continuation. No claim of completion,
no extraction removal, no public complete-mode checkbox, no commit/push.
