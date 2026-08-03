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
| Arial, Helvetica, Helvetica Neue, Trebuchet MS, Verdana, Tahoma | Arimo | Apache-2.0 |
| Times New Roman, Times                    | Tinos            | Apache-2.0 |
| Courier New, Courier, Consolas, Menlo, Monaco | Cousine      | Apache-2.0 |
| Georgia                                   | Gelasio          | SIL OFL 1.1|
| Calibri                                   | Carlito          | SIL OFL 1.1|
| Cambria                                   | Caladea          | SIL OFL 1.1|
| Segoe UI                                  | Selawik          | MIT        |
| Comic Sans MS                             | Comic Neue       | SIL OFL 1.1|
| Impact                                    | Anton            | SIL OFL 1.1|

Arimo, Tinos, and Cousine are from Google's croscore project; Carlito, Caladea,
Gelasio, Comic Neue, and Anton are from Google Fonts; Selawik is from Microsoft.
Full license texts ship with each upstream project; the target family names
(Arial, Segoe UI, etc.) are trademarks of their respective owners and are used
here only as substitution aliases, not as claims of authenticity.

## Coverage notes

- Verdana, Tahoma, Consolas, Menlo, Monaco have no exact open metric match; the
  closest open face is used and residual metric drift is absorbed per-container
  by the anti-font-fingerprinting spacing seed.
- Non-Latin script coverage (Noto family) is not yet included; add as needed.
- Currently only `bundle/fonts/macos/` is populated; `windows/` and `linux/`
  packs (same substitutes) are a mechanical follow-up.
