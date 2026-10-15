# SVG Bidi comparison diagnosis (Mac only)

The geometry change did not introduce the reported SVG-versus-Canvas mismatch.
The installed build 20261015160908 and pre-geometry backup 20261015154131
produce byte-identical corresponding PNGs for each of five fixed identities:
fonts seeds 0, 1, 42, 123456789 and 4000000000, canvas seed 1234567, and the
same disposable secret and site. This includes the same two differing pixels
between SVG and Canvas at seed 123456789, at (237,50) and (237,51). Their alpha
values differ by one; unpremultiplied RGB differs by at most two. Other fixed
seeds agree across APIs. A fresh random identity also reproduced a one-column
17-pixel difference in the new build. This was not accepted as a retry pass.

Explicit embedded DejaVuSans author-font bytes reproduce the same old/new
result (`../svg-bidi-author-control/result.json`). A cold protection-off control
with those same font bytes also shows SVG/Canvas differences at fractional font
sizes in both builds (`../svg-bidi-native-control/result.json`). That native
control demonstrates that unconditional cross-API pixel equality is not an
invariant; its larger differences are not used as a tolerance for canonical text.
The warm mode-switch data-URI samples in the author-control report are not used
as the native baseline.

The source paths use different positioning operations. `SVGTextFrame.cpp`
`DetermineCharPositions` accumulates nscoord positions per layout frame;
`TextRenderedRun::GetTransformFromUserSpaceForPainting` converts app units and
sets a per-run transform before `SVGTextFrame::PaintSVG` calls
`nsTextFrame::PaintText`. `CanvasRenderingContext2D.cpp` `CanvasBidiProcessor`
uses a float point, rounded run widths for the bidi processor, and a fractional
RTL advance before `gfxTextRun::Draw`. These are independent layout APIs even
though both use the same canonical font outlines. The source trace supports a
precision/positioning explanation; the exact floating-point operation responsible
for the two antialiasing pixels was not instrumented. Neither path calls the
changed Element/AbstractRange DOM rectangle methods during this render.

No product renderer was changed. The corrected font corpus retains cross-API
pixel equality as a diagnostic (including failure PNGs and raw pixel deltas),
and strictly compares the same SVG through data/blob URLs, ImageBitmap,
OffscreenCanvas, and worker transfers. The companion
`tests/fingerprint/probe_canvas_canonical_svg_golden.py` requires exact raw RGBA
SHA256 values captured from the pre-geometry build with explicit pinned
DejaVuSans.ttf bytes and identities at seeds 0, 42 and 123456789. The fixture
records the font digest, old build ID, site, default container, and all seed
inputs. It does not derive expected values from the current renderer, encoded
PNG metadata, an antialiasing tolerance, or a host font name.

Current installed evidence is under
`../installed/probe_canvas_canonical_svg_golden/result.json` (29 checks) and
`../installed/probe_canvas_canonical_fonts-revised/result.json` (96 checks).
These are replacement assertions, not a claim that the original 100
cross-API assertions all passed.
