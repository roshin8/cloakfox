# Canonical layout physical coordinate fixes

Final source tail: `cloakfox-canonical-layout-geometry.patch`, SHA-256
`938a0736d5a7d6c5f1f531101b190c37d0c484e688d4c3267ba0f945cad4e55b`.
A real zero-fuzz patch replay reproduces all 28 changed Gecko files byte for byte.
The rebuilt acceptance app passed the strict geometry runtime probe with zero
failures (32 samples, 10 paint/native-input samples, 29.95 seconds). Its XUL
SHA-256 is `7a54287b1c98ea8525472228ae0514f0708f59c865ff628db837abd330b6a343`.
The earlier failing binaries and receipts remain intact.

- [Runtime result](../../../tests/fingerprint/reports/firefox159-native-reference-layout/probe_canonical_geometry/result.json)
- [Runtime output](../../../tests/fingerprint/reports/firefox159-native-reference-layout/probe_canonical_geometry/probe-output.txt)
- [Verified self-contained acceptance artifact](acceptance-app.json)

This is the separately built, uninstalled `org.mozilla.cloakfox` acceptance app
under `firefox-src/.tools159/acceptance-native-reference-layout/Cloakfox.app`.
The artifact receipt records matching native source-build and copied app hashes.

## Observed failures and repairs

- Fractional composition: physical width 2000 minus a canonical 21.25-pixel
  gutter was truncated to 1978 before division by 1.25. The canonical MVM path
  keeps 1978.75 until conversion, yielding the actual 1583 CSS-pixel scrollport.
  Ordinary/off composition retains the old integer truncation.
- Late display scale: fixed APD60 prevented the existing APD-change reflow.
  The canonical UI-resolution callback rebuilds the viewport from actual viewer
  physical bounds and suspends admission until completed layout.
- A second physical input boundary was overwriting that normalized viewport:
  `PresShellWidgetListener::WindowResized` converted physical PuppetWidget
  dimensions using APD60 after the viewer had normalized them. It now uses the
  canonical conversion at that boundary, preserving the old integer conversion
  outside canonical mode. Admission is suspended before DPI synchronization,
  including when an already queued callback defers synchronization.
- Root admission additionally requires both visible and pending layout viewport
  sizes to match normalized actual viewer bounds. Transient mismatches remain
  protected without permanently revoking the captured owner.
- Root scrollbar movement crosses the output transform. Canonical bars use
  Gecko's synchronous drag path and carry no asynchronous scrollbar metadata;
  content APZ remains active. Event-coordinate walks recognize the same one
  output boundary. Root event-list visibility includes the physical output
  extent before descending into the scrollbar's layout-space subtree.
- A second event prefilter compared physical points against the async zoom
  item's unscaled child union before its `HitTest` converted the point. The
  canonical visual event-list bounds now include the actual resolution;
  ancestor wrapper unions consume those visual bounds too. Painting, ordinary
  themes and layout-relative event queries retain their prior bounds. An owned
  2x diagnostic clicked boxes at CSS x103/703 but missed every box beyond800;
  at CSS y653 all clicks missed, including x103, although logical hit testing
  saw every box. This independently established the layout-sized prefilter.
- Root scrollbars have `position:relative` in UA CSS. The earlier classic-part
  append skipped them, and the positioned-part append happened after output
  wrapping. Canonical positioned scrollparts now join the wrapper before it is
  serialized. Actual widget pixels established that the old 1.25x bar occupied
  physical x1583..1600 and height900 instead of x1979..2000 and height1125.
- RTL fixed-position culling replaced viewport-parent coordinates with a
  scrollport-relative visual viewport/displayport. It now includes the canonical
  left/top gutter origin. An owned old-binary diagnostic proved fixed frames
  starting at x1585 were omitted while absolute frames at x1595 painted fully;
  a fixed frame beginning at1580 painted through1585. This was frame culling,
  not a pixel clip ending at1583.
- Private browser UI scrollbar insets shortened the canonical slider by12 CSS
  pixels at1x and15 at1.25x. Root canonical scrollbar insets are now fixed zero;
  native/off embedder insets and authored element insets remain intact.
- The canonical drawing uses fixed buttonless scrollbars. Otherwise the inherited
  Windows drawing advertised button support and actual anonymous button creation
  consulted host `ScrollArrowStyle` (Cocoa None, Windows Single), changing track
  and thumb metrics across hosts.

## Verification

The actual-source compiled regressions exercise fractional composition, output
callback dispatch, generation readiness, widget resize conversion, root event
visibility, fixed-frame culling, positioned-part wrapper placement, synchronous
scrollbar dispatch, insets and button policy. The focused policy, decoration,
WebRender font fallback, DOM geometry and scrollbar suite passed **16 tests**.

The strict runtime fixture now checks actual authored-color track and thumb
pixels against the complete physical gutter, compares normalized thumb sizes,
and retains exact native drag-distance, parent/iframe click, edge-pixel and
full layout/SVG/Range/control assertions. Live1.25x/2x transitions run before
refresh and use a bounded wait for the actual native resolution and admitted
page geometry. The native observation uses the existing privileged Marionette
actor and `windowUtils.getResolution`, independently of page DPR presentation.
The fixture also paints and natively clicks a distinct box near CSS
(1400,650), and clears all parent/iframe/far-box click flags before every sample.
Before each screenshot it moves the native pointer to a neutral page point and
waits for two animation frames. This preserves the exact authored-color oracle:
prior RTL drags had left the pointer hovering the next thumb, whose intentional
hover color (59,95,135) differed from its base (38,76,114); the actual painted
thumb was present in the failing PNG. No RTL production paint exception was
added. Both new runtime probes pass Python syntax validation.

## Final geometry runtime acceptance

The final artifact passed actual parent/iframe/far-corner painting and native
clicks, root track/thumb pixels and exact drag distances, authored RTL and
opposite host-side preferences, fractional/2x viewport and composition agreement,
font preference changes, real ruby glyph shaping, SVG/Range/control geometry,
owner/site persistence, restart and protected unsupported/live-revocation cases.
The live transition receipts record actual native resolutions 1.25 and 2 while
the admitted fixed box remains exactly `[20,20,100,80]`. No geometry-oracle
failure remains in this artifact. Broader final-artifact regression and library
results are maintained by the coordinator separately.
