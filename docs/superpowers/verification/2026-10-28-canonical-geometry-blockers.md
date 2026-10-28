# Canonical geometry admission: blocked

Canonical geometry is **not implemented or admitted**. No production source,
native getter, patch ordering, installed application or Chromium input was
changed by this investigation. The existing protected geometry stays in force.
`geometry:canonical=true` must not be exposed as an operational setting yet.

## Reproducible Firefox159 evidence

The disposable-profile headless probe is
`tests/fingerprint/probe_canonical_geometry_readiness.py`. It serves its own
local fixture, preserves one owner/site/seed, enables the existing canonical
canvas/font pipeline and records Element, offset/client, Range, caret, native
controls, SVG text, path, non-scaling stroke, marker, clipping, foreignObject,
CTM and screen-CTM outputs. It also hashes actual screenshots and the XUL library.
It does not special-case a detector or exempt authored geometry in production.

Baseline application:
`firefox-src/.tools159/acceptance-coherent-gpu/Cloakfox.app/Contents/MacOS/cloakfox`

- Firefox `159.0-beta.1`, BuildID `20261028140958`.
- XUL SHA-256 `28ffd228ed58d9206f8da4c15dac6e1e7032576b2a58b8a7d815dc1a98f67b58`.
- Full report: `/tmp/cloakfox-geometry-readiness-20261028-native-baseline-3/result.json`.
- This is the existing baseline binary, **not** verification of newly compiled
  native changes.

Run with an explicitly selected test binary and new report directory:

```sh
MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1 \
CLOAKFOX_BIN=/absolute/path/to/test/Cloakfox.app/Contents/MacOS/cloakfox \
REPORT_DIR=/tmp/new-owned-geometry-report \
python3 tests/fingerprint/probe_canonical_geometry_readiness.py --diagnose
```

`--diagnose` deliberately records `BLOCKED / NOT IMPLEMENTED` without exiting
with an error. Omit it for nonzero unmet acceptance. Even if these inputs stop
changing layout, the probe requires broader cross-host and paint verification
and does not silently report full acceptance.

The final invocation without `--diagnose` exited **1**, with the same blockers
and stable reload/transition results. Its independent report is
`/tmp/cloakfox-geometry-readiness-20261028-acceptance-negative/result.json`.

Observed under `geometry:canonical=true`:

| Input | Measured result | Implication |
| --- | --- | --- |
| `font.minimum-size.x-western`: 0 → 50 | Text bounding height 33.07645 → 413.07644; button 48.90970 × 20.07645 → 179.50969 × 65.07645. Computed `font-size` remains `11px`. | Canonical glyph selection does not canonicalize actual font layout preferences. |
| `layout.css.devPixelsPerPx`: 1 → 1.25 | Fractional-border rectangle 103.35970 × 81.37646 → 102.95969 × 80.97645; transformed non-scaling SVG path bounding height 72.62644 → 69.87644. | Device rounding affects actual layout and SVG extents. Getter-only noise suppression would expose it. |
| Live full zoom 1 → 1.25 | Fourteen sample families change, including Range/caret, controls, rounded borders, SVG path/text and foreignObject. | Safe admission needs actual canonical rounding/transforms or revocation before unsupported zoom changes become observable. |
| Request false/absent → true | All sampled results unchanged; fixed rectangle remains protected at approximately `[19.81869,20.07295,100.05969,80.07645]`. Master-off control is `[20,20,100,80]`. | The request is currently unimplemented; existing protection is retained. |
| Same-owner reload | No sampled geometry changes. | Existing deterministic behavior is preserved. |
| Live request and disabled/malformed requests | No sampled presentation changes. | The current unimplemented request does not bypass the existing mask, including before reload. |
| Scrollbar style Cocoa → Windows | No sampled geometry changes on this macOS headless run. | Runtime result is inconclusive for platform scrollbar differences; source dependencies remain. |

The initial attempted launch without `MOZ_REMOTE_ALLOW_SYSTEM_ACCESS=1` failed
before content measurements. Its report is marked incomplete; the completed
report above uses the required environment. Gecko also logs sandbox-extension
and SWGL framebuffer warnings in this headless environment. These do not turn
the measured dependency differences into passing canonical-layout results.

The existing compiled helper regression passed:
`python3 -m pytest --noconftest tests/fingerprint/test_dom_geometry.py -q`
(`1 passed`). This verifies existing presentation semantics only.

## Native dependency map

1. `gfx/thebes/gfxTextRun.cpp:1872` captures canonical owned fonts when the
   authoritative pipeline is requested. This is useful groundwork, not a
   whole-layout contract.
2. `dom/base/Document.cpp:21121` returns process-shared `StaticPresData` font
   preferences. `layout/base/StaticPresData.cpp:98` reads language-specific
   minimum size; `layout/style/nsStyleStruct.cpp:240` and
   `layout/style/GeckoBindings.cpp:1253` apply it to actual style/font sizes.
   Default size, size-adjust, generic choices, text zoom and inflation also need
   explicit ownership or admission, not a font fallback whitelist alone.
3. Ordinary content already uses the basic theme through
   `Document::ShouldAvoidNativeTheme()` and `nsPresContext::EnsureTheme()`.
   However, `widget/Theme.cpp:124` creates a platform-dependent singleton
   (`ThemeCocoa` on macOS); `Theme::ScrollbarStyle()` at 1482 selects platform or
   global-pref scrollbar implementations. `nsPresContext::UseOverlayScrollbars`
   at 1862 reads `LookAndFeel`. Selecting the basic theme alone is insufficient.
4. `layout/generic/nsIFrame.cpp:1640,1663,7325` consumes real theme border,
   padding and minimum control metrics. `widget/Theme.cpp:1390,1514` rounds
   metrics in device units. `widget/ScrollbarDrawing.cpp:22,93` combines device
   scale, platform scrollbar kind and rounded sizes. These affect painting,
   layout and available line width together.
5. `layout/base/nsPresContext.h:629` exposes the actual cached device unit
   conversion; helpers through 716 use it for rounding and layout/device
   transforms. Changing only the getter to a constant would disagree with the
   shared `nsDeviceContext`, compositing and hit testing. Admission based on
   "current device scale happens to be one" would also need invalidation before
   any pending scale/zoom transition is visible.
6. `dom/svg/SVGGeometryElement.cpp:108,130,146,170` obtains paths and bounds from
   `ScreenReferenceDrawTarget`, with caches tied to the default content backend.
   `layout/svg/SVGGeometryFrame.cpp:362` and its stroke/marker branches combine
   fill, transformed/non-scaling stroke, device-dependent text/frame extents,
   markers and clips. `SVGTextFrame` uses effective zoom in several bounds and
   advance paths. Canonical canvas rasterization alone does not prove this
   layout path canonical.
7. `nsPresContext::PreferenceChanged()` reconstructs text runs/styles for font
   identity and pipeline preference changes. It does not own a canonical
   geometry identity/readiness generation. The current
   `CloakfoxSiteSeed::GeometryForDocument` dynamically reads configuration, so
   replacing its seed with zero on a request could expose a layout built under
   the preceding identity before reconstruction.
8. SVG path length currently uses `ForDocument` rather than
   `GeometryForDocument` (`SVGGeometryElement.cpp:345`). A future coherent mode
   must inventory every geometry output; one shared gate is not sufficient.

## Minimum full implementation before admission

1. Define an exact-owner immutable native geometry profile and strict descriptor
   validation. Bind its generation to the document's container/site and actual
   canonical font/rendering owner. Invalid/missing/foreign descriptors retain
   the existing protected mode.
2. Create per-document canonical font preferences, fixed default and minimum
   size behavior, system/generic font metrics and text scale policy. Keep user
   authored font/style semantics and canonical author-font loading; avoid
   mutating shared preferences or unrelated containers.
3. Supply a per-profile theme and scrollbar implementation with fixed metrics,
   overlay policy and canonical control/system-font behavior. Use it for both
   painting and reflow; do not only replace API rectangles.
4. Separate canonical layout rounding from physical painting units with a
   consistent conversion through style, reflow, transforms, compositing and
   hit testing. Preserve explicit CSS transforms/zoom. Normalize or reject
   unsupported full/text zoom, print, RDM, embedded documents and device-scale
   transitions before they can publish an unprotected layout.
5. Own SVG measurement/path backend and cache generation. Prove fill, strokes,
   non-scaling strokes, markers, clips, text, foreignObject and screen transforms
   agree with canonical paint and hit testing. Unsupported operations retain
   protection for the dependent query/document.
6. On request/identity/dependency change, revoke admission synchronously,
   reconstruct styles/frames/text/path caches, finish layout under one immutable
   generation, then publish admission. Every getter must require that completed
   generation; callbacks/re-entrant reads and subdocuments must not bypass it.
7. Only then suppress additive presentation for admitted output. Test native
   compiled ownership/admission transitions, actual Firefox159 Element/Range/
   caret/empty/fragments/SVG/control semantics, paint and boundary hit tests,
   reload/restart and multiple sites/containers across differing layout inputs.
   Run unmodified detection libraries and retain unsupported cases explicitly.

Until these prerequisites exist, a functioning canonical-geometry toggle would
overstate the implementation. The safe current behavior is to keep protection
and report canonical geometry unavailable.
