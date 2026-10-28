# Coherent executable GPU catalog implementation plan

> Execute inline with executing-plans; request independent code review before acceptance.

**Goal:** Finish coherent, executable Apple/Intel/AMD/NVIDIA persona profiles on
Firefox159 while retaining canonical rendering. The user selected this acceptance
target instead of pixel-for-pixel vendor-driver emulation.

**Architecture:** A single versioned JSON catalog generates C++ and privileged JS
representations. Select whole profiles through existing container/site HMAC ownership,
never independent random limits. Preserve BrowserForge renderer/vendor labels and
all canonical input, owner, integrity and readback guards. Capability numbers may
coincide across containers; secrets/records remain independently owned.

**Tech stack:** C++ Gecko validation, privileged ES modules, Python generator/tests,
Selenium headless runtime corpus, pinned FingerprintJS/CreepJS.

**Constraints:** Existing default-off toggle; canonical backend required; no native
host fallback; no secret rotation; no personal-profile/install changes; Chromium
build inputs/processes untouched. Preserve existing checkpoints and artifacts.

## Catalog

Two canonical executable cohorts for all four supported BrowserForge families:
portable4k (256/224 uniform vectors,32 texture units,256MiB WebGPU buffer) and
desktop8k (1024/1024 vectors,64 units,512MiB buffer). Each defines texture, shader,
attribute/unit, varying, WebGL2 resources and WebGPU storage/buffer bounds as a
whole. Storage-buffer binding stays128MiB. Both preserve core WebGPU minimums.
These are virtual compatible capability cohorts, not claims of physical driver
or detector whitelist parity. Backend support is checked natively before use.

Source the executable ceilings from the recorded canonical software backend
probe and preserve provenance. No external unverified dataset is activated.

## Steps

- [x] Add single catalog + deterministic generator; test invalid catalog and drift.
- [x] Replace native arithmetic decoder with closed catalog IDs. Cover unknown IDs,
  four family bindings, field relationships and immutable profile lookup.
- [x] Privileged profile generation derives eligible whole cohorts from manual
  capacity ceilings. Preserve atomic preflight and exact owner binding. Native
  code independently recomputes eligibility; forged descriptors fail closed.
- [x] Support legacy version1 saved descriptors without rotating identity, while
  emitting version2 descriptors; captured contexts retain their selected cohort.
- [x] Wire all catalog fields into actual WebGL validation and shader resources,
  and captured WebGPU adapter/device/buffer limits. Preserve generic off mode.
- [x] Update UI descriptions and targeted runtime tests to assert whole catalog
  tuples, real below/above-boundary behavior, workers, restart, restoration,
  owner/site isolation, toggle off, invalid ownership and override rejection.
- [x] Replay privacy patches against verified159 source; rebuild with isolated
  pinned Mozilla toolchain,2 low-priority jobs and own-build disk guard.
- [x] Stage a separate self-contained acceptance app; test all four families,
  canonical corpus, ownership/provenance, both library modes/WebGPU enabled,
  broad appropriate regressions. Retain warnings without treating them as bugs.
- [x] Independent code review; repair findings; save evidence/checkpoint.

## Review focus

Manual overrides below some cohorts filter eligibility; below all must reject
before any preference writes. Legacy descriptors must not bypass eligibility.
Page/worker WebGL/WebGPU choose the same profile from the same owner/site.
Context restoration must retain captured identity/caps rather than rereading
changed policy. Malformed catalog/IPC IDs must reject, never expose host values.

Acceptance and independent review: [receipt](../../firefox-159/coherent-gpu-catalog/README.md).
