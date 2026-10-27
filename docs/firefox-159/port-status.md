# Firefox 159 port — 2026-10-27

Isolated branch `codex/firefox-159-port`, based on `99cead4f453c4d1b96a6684c95afbda46d7e4448`.
Existing main checkout, its dirty container-tab work, Chromium source/patch locks and remote checkpoint build are preserved. No shared workflow cancellation or native cache mutation is authorized by this port.

The release-security failure was a valid freshness rejection (158.0 vs official stable159.0), not a script bug. Keep the gate fail-closed. Pin upstream159.0; fork build iteration resets to beta.1. A freshness receipt is not full build/release approval.

Official archive: https://archive.mozilla.org/pub/firefox/releases/159.0/source/firefox-159.0.source.tar.xz
SHA512 from Mozilla159.0/SHA512SUMS:
669241f3fc672d8240ddc4158b6125e5c2566bd0013a0a96a3874ee17bf0d9b3d91c842e653cb35eab0921829ce3660e9d795900b3c3a5488cd6020f85a0aac3
Archive verified before extraction.

## Execution

1. Snapshot existing checkpoint/build identity; create isolated worktree. Done.
2. Update Firefox pin and verify real official-feed freshness without bypass. Done: ready=true159.0; Python release tests28 (one skip), Node1 passed.
3. Stage current committed privacy additions and replay ordered patches against verified clean159 source. Initial replay completed: 158 patches, 141 successful, 17 conflicts. See patch-replay.json. This is not a completed native port.
4. Resolve port conflicts without dropping protections; run source tests and compatible checks.
5. Build/runtime verification requires enough independent disk/build capacity. Never consume or replace Chromium checkpoints to make space. Installed apps remain unchanged until a verified package is explicitly requested.

The Chromium feature inventory in this branch remains a historical158 parity baseline. Do not rewrite it or native Chromium patch locks to hide upstream differences.

## Current blockers and boundaries

The initial clean-source replay has conflicts in 17 patches (font list/anti-font, root build wiring, HTTP3/QUIC/NSS vendored changes, letterboxing/screen orientation, session-store cleanup, activity handling, timing, client hints, canvas text and Cocoa controls). Some context-only hunks were explored in the disposable source tree; they have not been accepted or written back to shipped patches. Do not build/package this partially patched source. The committed patch files remain unchanged until each conflict has been reviewed and cleanly replayed.

A preliminary full Node fingerprint run against the unpatched/extracting source had342 passes,12 failures,2 skips. Those are not accepted port verification. Re-run only after a clean full patch replay.

Internal disk had17GiB free before source extraction and12GiB afterward. A complete native build cannot safely fit here. The external Chromium build volume is absent. Do not delete Chromium sources, checkpoints, old source trees, profiles or user files for space; use independent build capacity once available.

Remote build40544857164 remains in progress (Chromium source segment on revisionba3f02ce039f37a99d787e3ed5e7ded3d832e436). No jobs were cancelled or dispatched. Chromium's committed native input key remainsbbc651dcf5cbe4321f5fd1728eb40f2a20f7547053009258d96764370804dfcf. No Chromium input files were changed by this branch.
