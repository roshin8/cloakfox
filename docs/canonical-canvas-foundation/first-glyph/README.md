# Cold first-canvas glyph fallback

The former unexplained mismatch is reproduced and localized. With a fixed Linux
persona (seed in the reports), the first HTML canvas paints missing-glyph boxes
for Arabic/Hebrew; subsequent HTML/Offscreen/worker canvases draw the actual font.
Per-operator readbacks show identical background and Latin text, then 5,182
changed channels inside x99..221/y43..71 at the RTL strokeText call. Those changes
remain exactly constant through later emoji/bounded text calls. PNGs preserve the
pixels. It is not extraction-noise seed drift or a transform mismatch.

`GlobalFontFallback` intentionally starts asynchronous cmap loading and skips
uninitialized families. Cloakfox forces cmap fallback for its masked family list.
A later font-list reflow repairs DOM text but cannot repaint an existing canvas
bitmap. `SearchAllFontsForChar` already has synchronous family/cmap initialization.
The fix allows that path for protected content; native/chrome retain async policy.
The existing allowlist and family ordering are preserved.

Recorded investigation (all disposable profiles, personal profile untouched):

* Original unmodified glyph sample: 12 clean prototype profiles; 4 initial HTML
  mismatches, all immediate later HTML/offscreen samples matching. Full config
  and output retained in `cfx-glyph-repro.json`.
* Pixel instrumentation: 3 clean prototype profiles, 2 mismatches; all divergence
  starts at the RTL stroke operation. `operator-investigation.json` records each.
* Fixed failing seed, async=true: 4/4 initial HTML mismatches; async=false causal
  control: 4/4 passes with identical stable output63f8cb0b. These are the
  `cfx-glyph-fixed-1.json` and `cfx-glyph-fixed-0.json` runs. No retries accepted.
* Final reusable no-wait operator probe against unchanged retained prototype:
  2/2 fail at exactly the same RTL call, each with5,182 changed channels. See
  `prototype-before/report.json` and accompanying PNGs.
* Final reusable operator probe with async=false:1/1 passes, all operators exact,
  recorded in `prototype-control/`. The restored stable installed app with normal
  async=true also fails1/1 in `stable-before/`, proving this predates canonical
  backing.
* Actual production branch C++ fixture: RED before source change at
  `assert(draw(&masked,cold))`; GREEN after adding the masked-content gate.
  It also proves native/non-content lookup still chooses the asynchronous path.

Source and ordered patch are updated. Native rebuild and runtime acceptance must
use the normal async=true setting; a pref=false control alone is not acceptance.
The original render-privacy probe now also asserts cross-realm equality of its
first legacy sample, so the formerly missed condition is directly checked.
