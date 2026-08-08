# Cloakfox bundled fonts

These are **openly-licensed, metric-compatible substitute fonts**, renamed to
the target family names that personas claim. They are activated at runtime by
Firefox's native bundled-font support (`MOZ_BUNDLED_FONTS`, enabled via
`--enable-bundled-fonts`) from `App.app/Contents/Resources/fonts/`, letting a
persona present its OS's fonts on any host — e.g. a Windows persona rendering
`Segoe UI` on macOS.

**Cloakfox does not bundle proprietary OS fonts.** Only redistributable open
fonts are used; the presented family name is set in the name table because
macOS has no fontconfig aliasing. Rebuild with `python scripts/build-font-pack.py`.

## Substitutes and licenses

| Target family(s) presented                | Open source font | License    |
|-------------------------------------------|------------------|------------|
| Arial, Helvetica, Helvetica Neue, Trebuchet MS | Arimo       | Apache-2.0 |
| Times New Roman, Times                    | Tinos            | Apache-2.0 |
| Courier New, Courier, Consolas, Menlo, Monaco | Cousine      | Apache-2.0 |
| Georgia                                   | Gelasio          | SIL OFL 1.1|
| Calibri                                   | Carlito          | SIL OFL 1.1|
| Cambria                                   | Caladea          | SIL OFL 1.1|
| Segoe UI                                  | Selawik          | MIT        |
| Comic Sans MS                             | Comic Neue       | SIL OFL 1.1|
| Impact                                    | Anton            | SIL OFL 1.1|
| Verdana, Tahoma                           | DejaVu Sans      | Bitstream* |
| DejaVu Sans / Serif / Sans Mono (Linux)   | DejaVu (as-is)   | Bitstream* |

Arimo, Tinos, and Cousine are from Google's croscore project; Carlito, Caladea,
Gelasio, Comic Neue, and Anton are from Google Fonts; Selawik is from Microsoft;
DejaVu is from the DejaVu Fonts project. \* DejaVu uses the free Bitstream Vera /
Arev permissive license. The DejaVu faces keep their own names (Linux personas
legitimately claim them); other faces are renamed to the target family. Full
license texts ship with each upstream project; the target family names (Arial,
Segoe UI, etc.) are trademarks of their respective owners and are used here only
as substitution aliases, not as claims of authenticity.

## Coverage notes

- Verdana, Tahoma, Consolas, Menlo, Monaco have no exact open metric match; the
  closest open face is used and residual metric drift is absorbed per-container
  by the anti-font-fingerprinting spacing seed.
- Non-Latin script coverage: a curated **Noto** subset (SIL OFL, kept under
  real names) — Arabic, Hebrew, Thai, Devanagari, Bengali, Georgian, Armenian,
  and CJK via Noto Sans SC (Simplified Chinese). Extend in
  `scripts/build-font-pack.py` (`NOTO`) for more scripts / JP+KR+TC if needed.
- Currently only `bundle/fonts/macos/` is populated; `windows/` and `linux/`
  packs (same substitutes) are a mechanical follow-up.

## Cross-OS metric identity — investigated, not a gap (2026-08-07)

An open question was whether the pack needs PER-OS variants so a Windows
persona's "Arial" measures differently from a macOS persona's, the way real
machines do. Investigated and measured; the answer is no, for two reasons.

**1. The substitutes are already metrically exact.** Advance widths (/1000em)
read straight out of the shipped files match the proprietary originals:

| family          | shipped | canonical original |
|-----------------|---------|--------------------|
| Arial           | A 667 · M 833 · i 222 · w 722 · 0 556 | identical |
| Times New Roman | A 722 · M 889 · i 278 · w 722 · 0 500 | identical |
| Courier New     | 600 (monospace)                        | identical |

**2. Advance widths do not vary by OS.** Arial on Windows and Arial on macOS
are the same Monotype design with the same metrics — that is precisely why
metric-compatible substitution works at all. There is no per-OS advance-width
signature to reproduce, so shipping different substitutes per OS would make us
*less* accurate, not more.

What genuinely differs between OSes for the same font is RASTERISATION —
hinting, subpixel AA, DirectWrite vs CoreText. That shows up in canvas-rendered
text rather than in `getBoundingClientRect()` advances, and it is already
covered by the per-container canvas noise plus the font-spacing seed.

Measured for completeness: across 10 generated personas, Arial widths spanned
186.15–187.80px with full overlap between Windows, macOS and Linux personas —
i.e. the observable spread is per-container seed noise, which is the intended
design (identical for a given persona on every machine, different between
containers). A change to fold the persona OS into the spacing seed was
prototyped and REVERTED: it only re-randomised within the same range and
created no OS-correlated signal, so it added complexity for no benefit.
