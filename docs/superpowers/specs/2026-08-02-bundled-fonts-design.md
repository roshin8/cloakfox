# Bundled per-OS font subsystem — design

**Status:** approved design, pre-implementation
**Date:** 2026-08-02
**Branch:** cpp-first-exploration

## Problem

Cloakfox spoofs the *claimed* OS (navigator, UA, canvas, …) per container, but
font enumeration still comes from the **real host**. Two consequences, both
verified this session against the built binary:

1. **Cross-OS incoherence / generic collapse.** A cross-OS persona (e.g. a
   Windows persona on a macOS host) lists fonts the host lacks (`Consolas`,
   `Segoe UI`) and excludes host fonts it does have (`Menlo`, `Monaco`). The
   `serif`/`monospace` CSS generics then have no valid font and collapse to
   sans-serif — `serif == monospace == sans-serif`, which a real system never
   does. Measured: disabled `sans/serif/mono = 686.6 / 666.95 / 867.0` (all
   distinct); a cross-OS persona `= 699 / 699 / 699` (collapsed).
2. **No cross-machine consistency.** Today the exposed set is `persona_list ∩
   host_fonts`, so two different machines running the *same* persona expose
   *different* fonts, and shared families (Arial, …) render with the *host's*
   glyph metrics. Font metrics are a strong fingerprint; per-host metrics leak
   the real machine.

Root cause of both: **there are no bundled fonts.** A host can only expose fonts
it actually has, so a cross-OS persona can never be coherent, and metrics can
never be host-independent.

Not a bug in reload determinism: reloads *are* deterministic (launch 2 == launch
3, byte-identical). The instability seen earlier was launch-1 (fallback
whitelist) vs launch-2 (persona whitelist) — the known first-launch gap.

## Goal

Every machine running a given persona exposes the **identical** font set **and
identical glyph metrics**, coherent with the persona's claimed OS — regardless
of the real host OS or installed fonts.

### Non-goals

- Shipping proprietary fonts. We use metric-compatible **open substitutes**
  renamed to the target families (the Camoufox font pack). "Segoe UI" is a
  renamed open font that *matches Segoe UI metrics*, not Microsoft's file.
- Per-glyph pixel-perfect parity with the real proprietary fonts. Metric
  compatibility (advance widths, line metrics) is the target; the anti-font
  spacing seed (already present) covers residual per-container variation.

## Model: full host-font replacement

At startup Gecko loads **only** the bundled font pack for the persona's claimed
OS and **suppresses enumeration of the real host fonts entirely**. Chosen over
the additive model (keep host fonts + add bundled) because only full replacement
gives cross-machine consistency and closes the host-metric leak. This is
Camoufox's production model.

Behavioral consequence, explicitly accepted: the browser renders *all* content
using bundled fonts only. Web fonts (`@font-face` downloads) are unaffected —
they are user fonts, not system enumeration.

## Architecture

```
persona cloak_cfg (per container)
        │  os = "windows" | "macos" | "linux"
        ▼
[gfx font-list init]  ──selects──▶  bundle/fonts/<os>/  (renamed open fonts)
        │                                   │
        │  register bundled fonts           │
        │  + suppress host fonts            ▼
        ▼                          platform font list = ONLY bundled <os> pack
[FontListManager narrowing]  ──per userContextId──▶  persona's font SUBSET
        │                                              (existing #4 mechanism)
        ▼
   page sees: persona's fonts, bundled metrics, coherent generics
```

### Components

1. **Font pack** — `bundle/fonts/{windows,macos,linux}/`. Camoufox's curated,
   license-cleared, renamed metric-compatible fonts. Each OS dir covers that
   OS's `CANONICAL_FONTS` families (see `CloakfoxPersonas.sys.mjs`). Packaged
   into the app under `Contents/Resources/fonts/` via the existing
   `package.py --fonts` path, extended to bundle all three OS dirs.

2. **Per-platform loader + host-suppressor (C++) — the real work.**
   - **macOS** (`gfxMacPlatformFontList` / CoreText): register the bundled dir
     with `CTFontManagerRegisterFontsForURL` (or process-scoped registration) at
     font-list init; suppress host CoreText family enumeration so only the
     registered bundled families are visible.
   - **Linux** (fontconfig): generate/ship a fontconfig config that points only
     at the bundled dir and rejects system font dirs; set `FONTCONFIG_FILE`/
     `FONTCONFIG_PATH` so the content process uses it.
   - **Windows** (DirectWrite): build a custom `IDWriteFontCollection` from the
     bundled dir and use it as the system collection; suppress the default
     collection.

3. **Persona-OS selector.** Which pack to load = the persona's OS, read from the
   per-container `cloak_cfg` overlay at gfx init. Inherits the existing
   first-launch timing gap (the persona pref may not be written when gfx inits
   on a fresh profile). Handled by persisting the last-known persona OS in a
   simple string pref read early at init; on the very first launch, default to
   the **host** OS pack (coherent, no collapse) until the persona lands next
   launch.

4. **Existing narrowing composes unchanged.** `FontListManager` still narrows
   per `userContextId` to the persona's font *subset*, now operating within the
   bundled OS pack instead of `host ∩ persona`. No change to #4 code.

5. **Fallback.** If registration or suppression fails on a platform (API error,
   missing pack), fall back to today's whitelist behavior — never a blank font
   list or broken rendering. Logged once.

## Data flow (per content process)

1. Content process starts for a container (userContextId `u`).
2. gfx font-list init reads persona OS for `u` from `cloak_cfg` (or the early
   persisted pref / host default on first launch).
3. Loader registers `bundle/fonts/<os>/` and suppresses host fonts → platform
   font list = bundled `<os>` pack.
4. Page requests fonts / generics → resolved within the bundled pack.
5. `FontListManager` narrows enumeration to `u`'s persona subset (existing).

## Error handling & edge cases

- **Registration failure** → fallback to current whitelist behavior (§Fallback).
- **First launch** (no persona yet) → host-OS pack default; coherent, avoids
  collapse; converges to the persona OS from launch 2.
- **`cloakfox.enabled = false`** → skip bundling entirely; real host fonts, real
  identity (consistent with the existing master switch).
- **Missing family in pack** → pack must cover the full `CANONICAL_FONTS` union
  per OS; a coverage test (Phase 4) asserts this so personas never reference an
  unbundled family.

## Phasing (spike-first)

- **Phase 0 — macOS feasibility spike (go/no-go).** Register *one* renamed font
  and prove (a) it enumerates as its target family and (b) host families can be
  suppressed, on the real Mac build. If this fails, the whole full-replacement
  approach is reconsidered before further investment.
- **Phase 1 — macOS full.** Whole macOS pack + persona-OS selection + host
  suppression + `FontListManager` composition + first-launch handling + tests.
- **Phase 2 — Linux.** fontconfig config + env wiring; lower risk.
- **Phase 3 — Windows.** DirectWrite custom collection.
- **Phase 4 — cross-machine consistency + coverage verification.** Reference
  metric/hash fixtures per persona OS; pack-covers-CANONICAL_FONTS assertion;
  generic-resolution (no collapse) assertion.

## Testing strategy

Selenium + geckodriver against the built binary (per `tests/fingerprint/`):

- **Coherence:** for each persona OS, `serif`/`monospace`/`sans-serif` resolve to
  distinct, OS-appropriate fonts (no collapse). Fails today for cross-OS.
- **Cross-OS independence:** a Windows persona on the Mac build exposes
  `Segoe UI`/`Consolas` (bundled) and hides `Menlo`/`Geneva` (host).
- **Cross-machine consistency:** bundled-font metrics match a committed
  reference fixture (proves host-independence). This is the fixture a second
  machine would reproduce.
- **Determinism & per-container:** existing `probe_font_metric_noise.py` and
  `probe_container_fonts.py` continue to pass (bundling composes with #3/#4).
- **Coverage:** every `CANONICAL_FONTS` family for an OS is present in that OS's
  bundled pack.

## Risks

- **macOS suppression feasibility (highest).** Suppressing host CoreText
  enumeration may be harder than registration. Mitigated by the Phase 0 spike as
  a hard go/no-go before full investment.
- **App size.** The pack is tens of MB. Accepted (reuse decision).
- **Metric-DB accuracy.** Substitutes are metric-compatible, not identical;
  residual differences are within the spacing-seed noise and are consistent
  across machines (still fingerprint-stable).
- **Licensing.** Reusing Camoufox's already-cleared pack; re-verify licenses
  carry over on import.

## Out of scope for this spec

- Curating an original font pack (reuse Camoufox's).
- Bundling additional scripts/CJK beyond what the Camoufox pack covers.

## Phase 0 result (2026-08-02) — macOS spike: CONDITIONAL, integration blocked

Ran the macOS feasibility spike on the real build (probe:
`tests/fingerprint/probe_font_spike.py`, isolating the CoreText layer with
`cloakfox.enabled=false`). Findings:

**Proven working:**
- `CTFontManagerRegisterFontsForURL(url, kCTFontManagerScopeProcess, …)`
  succeeds in the **parent** process (`ok=1`, no error).
- CoreText reads the correct family name from the bundled file
  (`CTFontManagerCreateFontDescriptorsFromURL` → `kCTFontFamilyNameAttribute`
  == `"Charis SIL Compact"`).
- **Injection point corrected:** on macOS the modern default is the *shared*
  font list, so `gfxPlatformFontList::InitFontList()` calls
  `CoreTextFontList::InitSharedFontListForPlatform()` — **not**
  `InitFontListForPlatform()`. The original plan/spec assumed the latter; the
  parent build path is `InitSharedFontListForPlatform` (`CoreTextFontList.cpp`
  ~line 1280).

**Blocker (why this is CONDITIONAL, not a clean GO):**
- Process-registered fonts do **not** appear in
  `CTFontManagerCopyAvailableFontFamilyNames()`, so the shared-list enumeration
  loop never picks them up.
- Adding the registered family's name explicitly to `SharedFontList()->
  SetFamilyNames(...)` makes the name present but does **not** cause the shared
  list's lazy face-loader `GetFacesInitDataForFamily()` to be invoked for it
  (verified by instrumentation: the loader was never called for the injected
  family). The font therefore never renders — a page requesting it falls back
  to sans-serif, and the probe reports it absent.

**Verdict:** macOS full-replacement is feasible at the *registration* layer but
blocked at the *shared-font-list rendering-integration* layer. Surfacing a
process-registered font through Gecko's shared font list to actual rendering is
dedicated gfx engineering — not resolvable within a spike. This confirms the
spec's stated top risk ("macOS suppression/integration feasibility").

**Recommended next options (pick before Phase 1):**
1. **Dedicated macOS shared-font-list integration investigation** — determine
   why the injected family never triggers face loading; likely provide
   `fontlist::Face::InitData` with the bundled file's path + face index directly
   (so the shared list mmaps the face itself instead of relying on a CoreText
   match query), and/or evaluate running with the *non-shared* font list on Mac
   (`gfx.e10s.font-list.shared=false`) where `AddFamily` + native face loading
   may integrate registered fonts more directly. Budget real time.
2. **Reconsider scope** — if macOS integration proves too costly, the pragmatic
   coherence fix (no bundling) is **host-OS-coherent personas**: on a Mac only
   generate Mac personas, so generics never collapse and fonts stay coherent.
   This abandons cross-OS independence but is a small, safe change.

Spike code was reverted (gated + non-functional + debug logging); only the
probe and this result are kept. Phases 1–4 do not proceed until option 1 or 2
is chosen.

### Phase 0 deeper dive (2026-08-02, funded "option 1") — architectural blocker

Pushed further into the shared-font-list face-loading path. New findings:

- The lazy face-loader `GetFacesInitDataForFamily` (parent) is triggered by
  `InitializeFamily`, which content requests over IPC (`SendInitializeFamily`)
  when it resolves a family. For the injected family this trigger **never
  fires** — the macOS shared list has no path to initialize faces for a
  non-system family.
- Firefox **does** model app-bundled fonts in the shared list —
  `fontlist::Family::InitData` takes an `aBundled` flag — but it is annotated
  **`[win]`**: bundled-font support exists for **Windows (DirectWrite)** only.
  **macOS has no bundled-font path in the shared font list.**

**Architectural conclusion:** making macOS render app-bundled fonts is not a
small patch on top of `CTFontManagerRegisterFontsForURL`. It requires one of:

- **(1a) Extend shared-list bundled-font support to macOS** — teach
  `CoreTextFontList` to build `Face::InitData` for registered/bundled families
  (PostScript-name descriptor + cmap) and trigger their initialization. This is
  real Gecko gfx work touching the shared-font-list lifecycle — a multi-day
  effort with its own risks (IPC face propagation, cmap loading, hidden-family
  visibility), and it is the macOS analog of what Firefox already does for
  Windows.
- **(1b) Run macOS with the non-shared font list** (`gfx.e10s.font-list.shared
  = false`) and register + add bundled families per content process. Sidesteps
  the shared-list model but carries a perf/telemetry cost and still needs
  per-process registration inside the content sandbox.
- **(2) Host-OS-coherent personas** (no bundling) — the pragmatic fix for the
  actual visible bug (serif/mono collapse), small and safe, abandons cross-OS
  font independence.

Per systematic-debugging discipline (3+ attempts, each surfacing a new layer =
architectural), this is a decision point, not a grind-it-out bug. Recommend
choosing 1a (if cross-OS independence is a hard requirement and multi-day gfx
work is acceptable) or 2 (if shipping coherence now matters more).

### Phase 0 RESOLVED (2026-08-02) — GO, via native `--enable-bundled-fonts`

The hand-rolled registration was reinventing an existing Firefox feature. Gecko
has **native app-bundled-font support** behind the `MOZ_BUNDLED_FONTS` build
define — `CoreTextFontList::ActivateBundledFonts()` activates every font in
`<GRE>/fonts` (= `App.app/Contents/Resources/fonts/`) via
`CTFontManagerRegisterFontURLs` and wires them into the shared font list
**correctly** (the exact face-integration the manual approach couldn't do). It
is cross-platform: macOS (`CoreTextFontList`) and Windows (`gfxDWriteFontList`).

It is simply not compiled in: `--enable-bundled-fonts` (`toolkit/moz.configure`)
defaults **on for Windows/Linux, off for macOS**, but the code is gated on
`MOZ_BUNDLED_FONTS`, not `XP_WIN` — so forcing the flag enables it on Mac.

**Verified on the real build:** added `ac_add_options --enable-bundled-fonts`
to `assets/base.mozconfig`, reconfigured + rebuilt (`MOZ_BUNDLED_FONTS=1` in
`mozilla-config.h`), staged a renamed test font in `Resources/fonts/`, and the
probe (`probe_font_spike.py`) reports the bundled family **present: True** — it
enumerates *and renders* (font-detection uses real rendering metrics). With no
fonts dir the flag is a **no-op** (host fonts enumerate normally, no breakage),
so it is safe to ship the flag ahead of the pack.

**This eliminates the macOS risk that blocked the design.** The revised plan:

- **Font integration = the build flag + `Resources/fonts/`.** No gfx-internals
  code. (Options 1a/1b/2 above are moot — the native path is neither.)
- **Host suppression / per-container narrowing = the existing whitelist +
  `FontListManager`** (already built, #4). The bundled pack *adds* the persona's
  OS fonts; the whitelist/narrowing hides host fonts and restricts each
  container to its persona subset. Full replacement falls out of composing the
  two.

**Revised phasing:**
- **Phase 1:** import the Camoufox font pack into `bundle/fonts/{os}/`; wire
  `package.py --fonts` to stage them under `Resources/fonts/`; verify a
  cross-OS persona (e.g. Windows-on-Mac) exposes its fonts and generics resolve
  (no collapse).
- **Phase 2:** persona-OS pack selection (load only the persona's OS pack, or
  mark non-persona-OS bundled families hidden) + first-launch handling.
- **Phase 3:** cross-machine consistency fixtures; Windows/Linux verification
  (bundled fonts already default-on there).

Committed: the `--enable-bundled-fonts` flag in `assets/base.mozconfig` (safe
no-op until the pack lands) + `probe_font_spike.py`. All hand-rolled spike code
was reverted; `firefox-src` C++ is pristine.

### Phase 1 progress (2026-08-02) — legal pack decision + pipeline proven

**Font-pack source decision (important correction).** Camoufox's macOS/Windows
packs (`bundle/fonts/{macos,windows}`) are the **real proprietary OS fonts**
extracted from macOS Sonoma / Windows 11 (README: "solely for academic and
research purposes … no … distribution … intended"), ~574 MB + ~321 MB. An
earlier note here mis-described them as open substitutes — only Camoufox's
**Linux** pack is open (Arimo/Cousine/Noto from the Tor bundle). Bundling the
real fonts into a distributed browser is a copyright/redistribution risk, so the
chosen approach is **openly-licensed metric-compatible substitutes renamed to
the target family names** (the standard font-substitution technique; the font
files are open, only the presented name matches the proprietary family).

**Pipeline proven end-to-end.** On macOS there is no fontconfig aliasing, so the
substitution is baked into the font's name table (`scripts/rename-font.py`).
Verified: an OFL font renamed to "Segoe UI", staged into `Resources/fonts/`,
**renders as `Segoe UI` on the Mac** (a Windows-only family, normally absent) —
i.e. a cross-OS persona can present its fonts via a legal open substitute.

**Substitution mapping (starting point; verify each license + metric fidelity
before shipping):**

| Target family        | Open substitute | License   |
|----------------------|-----------------|-----------|
| Arial / Helvetica    | Arimo           | Apache-2.0|
| Times New Roman      | Tinos           | Apache-2.0|
| Courier New          | Cousine         | Apache-2.0|
| Calibri              | Carlito         | SIL OFL   |
| Cambria              | Caladea         | SIL OFL   |
| Georgia              | Gelasio         | SIL OFL   |
| Segoe UI             | Selawik         | MIT       |
| Verdana              | DejaVu Sans*    | Bitstream |
| non-Latin scripts    | Noto family     | SIL OFL   |

\* no exact open metric match for Verdana/Consolas; use the closest open face
and accept minor metric drift (covered per-container by the spacing seed).

**Remaining Phase-1 work (bounded, mostly mechanical):**
1. Source the open substitutes above (Google Fonts / Selawik / Noto), verify
   licenses, and rename each to its target family via `scripts/rename-font.py`
   into `bundle/fonts/{macos,windows,linux}/` covering the `CANONICAL_FONTS`
   families per OS.
2. Pass `--fonts <os>` to the macOS package target (packaging already flattens
   `bundle/fonts/<os>/*` into `Resources/fonts/` — no new code).
3. Verify a cross-OS persona exposes its family set and `serif`/`monospace`
   resolve (the collapse fix), then compose with the whitelist/`FontListManager`
   for host suppression + per-container narrowing.

Committed: `scripts/rename-font.py` + this note. The proof font was a placeholder
(Charis SIL is not metric-compatible with Segoe UI) and was NOT committed.
