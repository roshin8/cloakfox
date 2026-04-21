# cpp-first architecture exploration

Branch: `cpp-first-exploration`
Date: 2026-04-21
Status: exploration complete, decision pending

## TL;DR

The user proposed: drop the extension-based spoofer architecture, have
C++ do the fingerprinting work, and put the settings UI in a native
`about:cloakfox` page. The stealth circus (ISOLATED/MAIN coordination,
`[Func=...]` gates, documentElement bridge, `cloakfoxIsConfigured()`,
Phase 3 exportFunction migration) disappears.

**Viable? Yes, partially.** Some JS stays, but it moves to chrome-
privileged territory where detection is a different (smaller) problem.

Numbers from `inventory.md`:

| Category | Count | What happens |
|---|---|---|
| Already covered by C++ (redundant JS) | 20 | Delete from extension once C++ verified |
| Feasible to add to C++ | 10 | New C++ patches (small-medium effort) |
| Must stay JS | 22 | Chrome-privileged `JSWindowActor` (no extension) |
| **Total** | **52** | (2 are shared infrastructure, not signals) |

So cpp-first goes from "extension does everything" to "C++ does 30
signals + chrome JS actors do 22 signals, with no extension doing
any spoofer work." The extension shrinks to either zero or a 30-line
toolbar launcher for the settings page.

## Documents in this directory

| File | Purpose |
|---|---|
| `inventory.md` | Per-file mapping of all 52 spoofers to C++ coverage status |
| `about-cloakfox-design.md` | Native settings page: registration, pref schema, per-container config storage |
| `frame-script-pattern.md` | JSWindowActor pattern for the 22 must-stay signals |
| `cpp-first-math-actor.patch.sketch` | Prototype actor showing the pattern concretely |

## What cpp-first eliminates

- Extension background/header-spoofer — prefs drive C++ which drives headers
- `core-bridge.ts` + `callOrAlreadyConfigured()` (self-destructing WebIDL coordination)
- `cloakfoxIsConfigured()` WebIDL (the escape hatch we built last month)
- `IsCloakfoxShieldCaller` principal gates on every setter
- `documentElement` bridge + ISOLATED/MAIN dance
- Phase 3 `exportFunction` migration (the thing we just scaffolded)
- WebExtensions Experiment API for `http2Profile` (no longer needed)
- `preCoreHandled` skip-set and per-signal coordination
- React popup build pipeline (or kept as 30-line launcher)

Net: ~70% reduction in the JavaScript surface that has anything to do
with stealth. The C++ patches themselves don't shrink.

## What cpp-first does NOT eliminate

- The 62 C++ patches. Actually adds ~5 more (about:cloakfox registration,
  pref-reader at window construction, JSWindowActor registration,
  chrome:// manifest, maybe one or two C++ ports from the "feasible to
  move" list to further reduce JS).
- JavaScript spoofing for 22 signals — just moves it from extension MAIN
  world to chrome-privileged `JSWindowActor` child. Still JS, still
  fragile, still needs per-container seed plumbing.
- Build pipeline: Firefox tarball → patches → `mach build` → DMG. Same.
- Container-specific targeting — already in C++ via `mUserContextId`;
  just needs the pref read path to thread userContextId through.

## Tradeoffs vs today

**Pros:**
- No stealth gymnastics; C++ is invisible by construction, chrome JS
  invisible by compartment.
- Settings page can write prefs with parent-process authority (fixes
  the `setHttp2Profile` class of bug permanently).
- Fewer moving parts in the spoofer pipeline (one less hop: extension
  content-script → WebIDL disappears entirely).
- Chrome-privileged JS has fewer detection vectors than page JS — no
  `moz-extension://` in stack traces, `[native code]` stringification
  comes for free.

**Cons:**
- Big refactor. Probably 2-3 weeks for a full cutover including test.
- Loses the ability to ship spoofer changes without a browser rebuild.
  Today we can iterate on `math.ts` and reload the extension; cpp-first
  requires a `./mach build` round-trip for anything but pref tweaks.
- Settings UI is harder to style without React/Tailwind. The popup's
  current 6-tab density works out to ~500 lines of vanilla HTML +
  chrome-privileged JS, which is workable but not delightful.
- Live testing requires the full browser, not a `web-ext run` loop.
- Any UI feature that today lives in the popup (the per-tab fingerprint
  monitor with its "which signals were probed" toast) needs rebuilding
  against `browser.tabs`/WebNavigation equivalents in chrome scope.

## Recommendation

Not an automatic win, but worth doing. The security argument (no
page-visible extension ever) is strong, and the operational argument
(no stealth coordination code to maintain) is stronger.

**Proposed order of operations** for a cpp-first migration:

1. Land the `about:cloakfox` page with a single toggle (`cloakfox.enabled`).
   Prove the chrome-privileged pref-write path works end-to-end.
2. Land the per-container pref-reader at `nsGlobalWindowInner`
   construction. Route one existing C++ signal (canvas seed) through
   the new path. Prove it works alongside the existing WebIDL setter
   path (both paths populate RoverfoxStorageManager).
3. Land the `CloakfoxMath` actor. Prove the pattern for must-stay-JS
   signals.
4. If 1-3 look clean, write a migration RFC: order of the remaining
   18 redundant JS deletions, 10 new C++ patches, 21 remaining actors.
5. If not clean (e.g. `about:cloakfox` CSP fights, actor timing issues),
   abandon and continue the current architecture.

Steps 1-3 are ~1 week of real work; the answer for "go or no-go on
full migration" will be clear by then.

**Stay-the-course argument**: the stealth pass just shipped. Extension
presence is already undetectable from page MAIN. The marginal gain from
cpp-first over the post-Phase-3 state is smaller than the gain from
the stealth pass itself. If we're willing to commit to Phase 3, we get
most of the security benefit without a full rebuild.

This is the "we don't need cpp-first" position. It's defensible.

## Next actions

- [x] Inventory 52 JS spoofers against C++ coverage
- [x] Design `about:cloakfox` registration + pref schema
- [x] Design JSWindowActor pattern for must-stay JS
- [x] Sketch `CloakfoxMath` actor patch (illustrative, not buildable)
- [ ] User decision: pursue cpp-first, or proceed with Phase 3 on
      `unified-maskconfig`?
- [ ] If cpp-first: steps 1-3 above, each ~2 days.
