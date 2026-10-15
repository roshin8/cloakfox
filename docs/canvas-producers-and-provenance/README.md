# Canvas producer candidate — 2026-10-15

This candidate is partial implementation, not a complete privacy renderer.
`cloakfox.experimental.canvas_pipeline` remains default false. Existing RGB
extraction noise, protected native-text fallback, and strict GPU readback policy
remain in force. Source labels do not authorize skipping protection.

Implemented components:

- Protected font fallback initializes allowed family character maps synchronously,
  fixing first-use Arabic/Hebrew missing-glyph differences without warming probes.
- A pinned bundled DejaVu/HarfBuzz outline producer handles supported normal
  generic sans-serif ASCII text, with common geometry and metrics in window and
  worker canvases. Gecko explicitly supplies Mozilla Unicode callbacks.
- Glyph positioning preserves author gradient/pattern coordinates.
- Thread-safe contributor labels follow snapshots, bitmap conversion and
  same-process bitmap clone/transfer. Unknown IPC surfaces remain unknown.
- WebGL snapshot outputs retain a GPU contributor label. No shader renderer was
  added, and generic reported GPU capabilities are not canonical rendering.

Review findings corrected: author paint coordinates, lost ImageBitmap/canvas
import labels, ordinary bitmap clone labels, policy initialization clearing prior
contributors, and missing Gecko Unicode callbacks. Source review was independent.

Validation so far: 258 Node tests and 62 Python tests pass; native build succeeds;
143 ordered patches replay without offset, fuzz or native drift. The dedicated
fixed-outline runtime test fails its new-producer assertions against the old
installed browser and passes all 17 checks against candidate build 20261015123853.
Candidate and installed matrices both passed: each 1,767 canvas checks, 1,368
library consistency checks (144 library executions), 17 fixed-text checks,
11 transfer checks and four cold-start glyph runs. GPU/window/worker guards and
settings checks also passed. Raw detector warnings remain in acceptance.json.

Still required for the complete release gate: complex/custom/color font support,
canonical SVG/image/media conversion, a common GPU software renderer, full
cross-process provenance, cross-host pixel differential tests and extraction
cutover attack-resistance validation. Keeping old guards avoids removing those
guards; it does not establish universal privacy safety. Earlier known-fill
calibration remains a documented limitation of the retained noise design.

## Installed release decision

The tested candidate was installed and signature/hash verified, then the prior
app was restored because the full release gate failed. Personal profiles were
not modified. `install.json` identifies the retained tested candidate and active
restored hash. The packaged DMG is an experimental candidate, not a complete-mode
release. Known-fill calibration still recovers the native path corpus exactly
in all six tested cases; fractional empty-text font bounds also trigger a new
CreepJS metric heuristic when the internal text experiment is enabled. These
results are retained, not filtered out of the report.
