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
