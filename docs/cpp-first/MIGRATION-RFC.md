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
13. ~~`CloakfoxErrors`~~ — replaced by `cpp-first-error-stack-depth.patch` (clamps `MAX_REPORTED_STACK_DEPTH` in SpiderMonkey to 20; V8-style `Error.stackTraceLimit` JS property isn't honoured by SM).
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

### Phase 4 — Trim extension to popup-only (~2 days)

**Revised plan (2026-04-24):** the original Phase 4 ("delete the
extension entirely") + Phase 5 ("native customize-mode toolbar
button") collapse into a single Phase 4: keep the extension as a
**thin tab-aware popup**, delete everything else.

The motivation for the revision: `about:cloakfox` (Phase 3) doesn't
know which container the user's *current tab* is in — extensions
do, natively, via the tab's `cookieStoreId`. Building a dedicated
parent actor just to thread that signal through to a chrome page
is more code than keeping a 100-line popup in a thin extension.
The popup ALSO solves Phase 5's "discoverable toolbar button"
problem for free, since extensions get one by default.

**What stays in the extension:**

- `manifest.json` (drastically slimmed: only `tabs` + `contextual
  Identities` permissions, no `host_permissions`, no `content_scripts`)
- `popup/popup.html` + `popup.js` + `popup.css` — vanilla HTML,
  no React, no Vite, no bundler
- icons

**What gets deleted from the extension:**

- All of `src/background/` — header spoofer, settings store,
  profile manager, config injector
- All of `src/content/` — ISOLATED-world content script, core-bridge
- All of `src/inject/` — MAIN-world spoofers (already replaced by
  cpp-first JSWindowActors)
- `src/lib/` — crypto/PRNG/domain-matcher (cpp-first owns these)
- All build infrastructure (vite, rolldown, tailwind, postcss, etc.)
- `package.json` shrinks from ~200 deps to zero

**What's NOT deleted from the C++ patches:**

The Func-gated WebIDL setters (`setCanvasSeed`, `setCloakConfig`,
`setHttp2/3Profile`, `setNavigatorUserAgent`, `setWebGLVendor`,
`setWebGLRenderer`, `setScreen*`, `setFontList`,
`setFontSpacingSeed`, `setAudioFingerprintSeed`, `setSpeechVoices`,
`setNavigator{Platform,Oscpu,HardwareConcurrency}`) plus the
`IsCloakfoxShieldCaller` principal helper plus `cloakfoxIsConfigured`
WebIDL query stay in the tree.

Rationale: every setter is `[Func="IsCloakfoxShieldCaller"]`. With
the extension's content scripts gone, **no caller satisfies the
gate** (no principal carries the cloakfox-shield@cloakfox addon
policy in its expanded principal). Result: from any compartment,
`typeof window.setCanvasSeed === "undefined"` — invisible to
fingerprinting. Same for `cloakfoxIsConfigured`.

Surgical removal would touch ~10 patches, each with hunk-count
arithmetic, with high regression risk (cf. `cpp-first-pref-
migration.patch`'s blank-line-context bug that took two CI runs to
catch). Zero functional benefit since the setters are already
unreachable. Marked as a future cleanup pass in PENDING.md.

**What gets added to `about:cloakfox`:**

- Accept a `?ucid=N` query param to auto-select container N in the
  dropdown. The popup's "Configure for this container" button uses
  this to deep-link.

### Popup spec

When the user clicks the toolbar icon:

```
┌─────────────────────────────────┐
│  Cloakfox       [enabled ●]     │
├─────────────────────────────────┤
│  Container:    Personal         │
│  This site:    https://nyt.com  │
│  Seed status:  set (active)     │
│                                 │
│  [ Regenerate seeds ]           │
│  [ Open full settings ]         │
└─────────────────────────────────┘
```

`Regenerate seeds` writes to `cloakfox.container.<ucid>.math_seed`
+ `cloakfox.s.cloak_cfg_<ucid>` via an Experiment API (small,
purpose-built; ~30 lines). `Open full settings` does
`browser.tabs.create({ url: 'about:cloakfox?ucid=<N>' })`.

The Experiment API is the only piece that needs privileged-extension
plumbing. Without it, the popup can only display the URL/container
and link out — `Regenerate` would have to happen on the settings
page. Acceptable degraded behavior if the Experiment API turns out
hard to ship.

### Phase 5 — DELETED

The native toolbar-button work is no longer needed; the popup
provides the same affordance through extension UX.

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
| 2 (done) | — | 9 actors landed; Worker + Iframe analyzed as redundant |
| 3 (done) | — | Container-aware about:cloakfox + pref migration shipped |
| 4 (revised) | 2 days | Trim extension to popup-only + drop Func-gated setters |
| 5 (DELETED) | — | Popup provides the toolbar affordance for free |
| **Total remaining** | **~2 days** | Mostly delete-and-rewrite |

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
