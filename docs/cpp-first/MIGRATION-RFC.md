# Cpp-first Migration RFC

**Branch:** `cpp-first-exploration`
**Date:** 2026-04-23
**Status:** draft — awaiting go/no-go

## Summary

Retire the `cloakfox-shield` WebExtension. Move its three jobs to native
browser components:

1. **Spoofer logic** → existing C++ patches (already present), fed from
   a new `cloakfox.s.*` pref namespace rather than WebIDL setters.
2. **Must-stay-JS spoofers** (Math, WebRTC SDP, keyboard cadence, etc.
   — 22 per `inventory.md`) → chrome-privileged `JSWindowActor` children
   under `browser/components/cloakfox/actors/`.
3. **Settings UI** → `about:cloakfox` native page (already scaffolded,
   renders, 4/4 probe assertions pass).

The extension becomes either (a) gone entirely, or (b) a ≤30-line
shim that only provides a toolbar launcher for `about:cloakfox`.

## Why now

The 2026-04 stealth pass closed the extension's *presence* detection
surface (Func gates, documentElement bridge). What remained was the
JS spoofer shape-detection surface (descriptor inspection, stack
traces, `.toString` arms race). Phase 3 of the stealth work was going
to move those spoofers to ISOLATED via `exportFunction` — exactly the
same pattern the cpp-first JSWindowActors use, but without the
extension wrapping.

Running the POC (`cpp-first-exploration` branch) confirmed both
halves of cpp-first work: Step 1 (about:cloakfox) and Step 3
(CloakfoxMath actor) pass end-to-end probes. Step 2 (C++ reads
`cloakfox.s.*`) is mechanically complete — the cross-process IPC
fallback and priority check compile and link — runtime verification
is blocked on a pre-existing MV3 builtin-addon permission issue
(tracked separately) that disappears once the extension does.

## Layered scope

Five phases, each independently landable and independently revertable.

### Phase 1 — Scaffolding landed (done, this branch)

- `about:cloakfox` page + `chrome://browser/content/cloakfox/` assets.
- `AboutRedirector` kRedirMap entry + `components.conf` + DIRS in
  `browser/components/moz.build` via `cpp-first-about-cloakfox.patch`.
- `CloakfoxMath` JSWindowActor + registration in
  `ActorManagerParent.sys.mjs` via
  `cpp-first-math-actor-registration.patch`.
- `RoverfoxStorageManager` reads `cloakfox.s.<key>` with priority over
  `roverfox.s.<key>` via `cpp-first-pref-reader.patch`.
- `ContentParent::RecvRoverfoxStorageGet/Put` IPC accepts
  `cloakfox.s.*` in addition to `roverfox.s.*` via an edit to
  `cross-process-storage.patch`.

No changes to the extension. Phase 1 is shipped.

### Phase 2 — Must-stay JS actors (next; ~2-3 weeks)

Port the 22 inventory.md "must-stay JS" spoofers into
`browser/components/cloakfox/actors/`. Priority order (no C++
coverage today, so each port is a net stealth improvement):

1. `CloakfoxMath` — done.
2. `CloakfoxKeyboard` — `KeyboardEvent.timeStamp` jitter.
3. `CloakfoxWebRTC` — `RTCPeerConnection.createOffer` SDP munging
   (m-line ordering, ice-ufrag/pwd randomization).
4. `CloakfoxDOMRect` — `Element.getBoundingClientRect` / `Range`
   jitter.
5. `CloakfoxTextMetrics` — `CanvasRenderingContext2D.measureText`
   width jitter.
6. `CloakfoxSVG` — `SVGTextContentElement.getComputedTextLength` etc.
7. `CloakfoxPerformance` — `performance.now` coarse-grain jitter.
8. `CloakfoxStorageEstimate` — `navigator.storage.estimate` quota.
9. `CloakfoxPermissions` — `navigator.permissions.query` results.
10. `CloakfoxEventLoop` — setTimeout/setInterval coarsening.
11. `CloakfoxTouchInput` — `navigator.maxTouchPoints`, `TouchEvent`.
12. `CloakfoxRendering` — emoji/MathML render-variation.
13. `CloakfoxErrors` — `Error.stack` chrome:// filtering.
14. `CloakfoxHistory` — `window.history.length` floor.
15. `CloakfoxWebCrypto` — `SubtleCrypto` algorithm disclosure.
16. `CloakfoxWorkerInit` — `Worker`/`SharedWorker` startup config.
17. `CloakfoxIframeInject` — iframe content-script propagation.
18. (…remaining nice-to-haves)

Each actor is one commit. Feature-gated on a pref
(`cloakfox.<signal>.enabled`) so bisecting is trivial.

Each must include the fix from the `CloakfoxMath` descriptor-leak
note: install spoofed properties using page-compartment
`defineProperty` with correct `{writable:false,configurable:false}`
flags — known research-pending but must not regress.

### Phase 3 — Flip authority (~1 week)

Flip every C++ manager that today reads
`RoverfoxStorageManager::GetUint("canvasSeed_N")` etc. to
authoritatively consume `cloakfox.s.canvasSeed_N` via the already-
landed priority check. No manager code changes needed — they already
call `GetUint` which checks cpp-first first.

What DOES change in this phase:

- `about:cloakfox` settings page gains real UI for every
  container-keyed pref (canvas seed, audio seed, WebGL vendor/
  renderer choice, font allowlist, screen size override, etc.).
  Vanilla HTML; the current React popup's density maps to ~500 lines.
- Container-aware UI: settings page reads the tab-origin's
  userContextId (via a new `AboutCloakfoxParent` actor) instead of
  the hardcoded 0 the POC uses.
- Pref migration script runs on first boot of a cpp-first build:
  reads any existing `roverfox.s.*` prefs (extension-written) and
  copies them to `cloakfox.s.*`. One-time, idempotent.

### Phase 4 — Delete the extension (~2 days)

- Remove `additions/browser/extensions/cloakfox-shield/` from the
  tree.
- Remove the entry from `browser/extensions/moz.build` (via an
  update to `builtin-extension.patch`).
- Remove the `ExtensionSettings` block from `settings/policies.json`.
- Remove Func-gated WebIDL setters that exist solely to receive
  extension calls: `setCanvasSeed`, `setCloakConfig`, `setHttp2/3
  Profile`, `setNavigatorUserAgent`, etc. C++ managers still read
  from `RoverfoxStorageManager`, which now only takes writes from
  the new `about:cloakfox` page (chrome-privileged direct pref
  writes, no need for WebIDL intermediary).
- Drop the `IsCloakfoxShieldCaller` principal helper — nothing
  needs to be gated to extension principal anymore.
- Drop `cloakfoxIsConfigured` WebIDL — the cpp-first architecture
  removes the self-destruct race it was designed around.

### Phase 5 — Optional toolbar shim (~30 lines; ~1h)

Decide: do we ship a minimal shim extension whose only job is a
toolbar button that opens `about:cloakfox`? Tradeoffs:

- **Pro:** discoverable UI entry. Users familiar with extensions
  find the button intuitively. Matches Firefox's native-addon UX
  (uBlock Origin, etc.).
- **Con:** reintroduces an extension — however thin — into a
  codebase designed to be extension-free. Signing, manifest
  maintenance, review-process overhead for a single click handler.
- **Alternative:** add a customize-mode button in
  `browser/components/customizableui/` that opens `about:cloakfox`
  directly. Native, no extension. More Firefox-style UI patch
  work but matches how Firefox exposes its own features.

**Recommendation:** Phase 5 is the customize-mode button, not an
extension. Cpp-first goes fully zero-extension.

## Config migration

Users with existing extension-written state have `roverfox.s.*` prefs
populated. The migration script runs once per profile at first boot
of a cpp-first build:

```python
# pseudocode
for key in Services.prefs.getBranch("roverfox.s.").getChildList(""):
    v = Services.prefs.getCharPref(f"roverfox.s.{key}")
    Services.prefs.setCharPref(f"cloakfox.s.{key}", v)
```

Plus a one-time flag `cloakfox.migration.v1.done = true` so it
doesn't re-run. Existing containers' canvas seeds, font seeds, etc.
are preserved — same values, new namespace.

## Risks and rollback

| Risk | Mitigation | Rollback cost |
|------|------------|---------------|
| Phase 2 actor-port introduces a regression per signal | Per-signal feature flag pref, gated off by default | Flip the pref off; bug-triage |
| Phase 3 pref migration misses entries | Idempotent; re-run is safe | Run migration again |
| Phase 4 deletes setters that some test infrastructure still calls | Update tests alongside in same commit | Revert Phase 4 patch-set |
| Phase 5 toolbar button doesn't render in custom themes | Pin to native native CustomizableUI behavior | User disables the button |
| Descriptor-leak in JSWindowActor spoofers (known, documented) | Research task — pageWin.eval with temp-global trick | Accept the detection surface; doesn't regress current state |

**Revert points:**

- After Phase 2 ships: easy revert — delete the new actor files, the
  old extension still works as the primary spoofer.
- After Phase 3 ships: revert per pref-migration table; extension
  can coexist while we debug.
- After Phase 4 (extension deleted): revert by restoring the
  extension directory + the moz.build DIRS entry + policies.json
  entry. 3-5 file changes.

## Timeline estimate

| Phase | Calendar | Person-effort |
|-------|----------|---------------|
| 1 (done) | — | — |
| 2 | 2-3 weeks | ~14 actor ports × 1-2 days each = 2-4 weeks engineering, plus coupled test work |
| 3 | 1 week | Settings-page UI + pref migration |
| 4 | 2 days | Delete the extension, rip out setters |
| 5 | 1 day | Customize-mode button |
| **Total** | **~5 weeks** | Mostly actor ports |

## Open questions

1. **MV3 builtin permission issue** (separate task): when do we
   lose the ability to ship the extension at all? If Firefox ever
   fully enforces MV3 user-consent for builtin addons, the current
   architecture breaks with or without cpp-first. That would convert
   this RFC from "strategic refactor" to "forced migration."

2. **Per-container seed persistence across profile restarts.** Today
   the extension derives seeds deterministically from the container
   ID. Cpp-first stores them as prefs — user-observable via
   about:config. Is that exposure acceptable?

3. **Worker global spoofing.** Every actor port must verify that
   workers (which spawn in separate processes without
   `JSWindowActorChild` on `DOMDocElementInserted`) get the same
   spoofed values. Current extension handles this via
   `workerPreamble` injected at `self` construction. Cpp-first
   equivalent TBD — likely a `WorkerProcessChildActor` pattern.

## Recommendation

**Proceed with Phase 2**, starting with `CloakfoxKeyboard` (no C++
coverage, small scope, easy to verify). Defer Phase 4 until at
least 10 actor ports are green and the settings page has real
container-aware UI.

If the MV3 permission research confirms the extension is
unfixable for our builtin use case, Phase 4 accelerates — the
extension is already dead; Phase 4 just removes the tombstone.

## Decision needed

Sign off on the five-phase plan or redline it. Phase 2 kicks off
the moment go/no-go lands.
