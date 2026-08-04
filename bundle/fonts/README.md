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
