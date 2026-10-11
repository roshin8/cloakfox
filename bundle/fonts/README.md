# Cloakfox bundled fonts

The pack contains 31 redistributable open font files. Some are renamed
substitutes for CSS family names; they are **not authentic proprietary OS
fonts**. Firefox loads them through native bundled-font support. The files live
in `macos/` for historical reasons and the build currently stages this pack on
all platforms.

`font-manifest.json` records SHA-256 hashes, embedded copyright notices, actual
family names and license files for the shipped bytes. `FONT-NOTICES.txt` and
`licenses/*.txt` ship alongside the fonts. Verify with
`python3 scripts/audit-font-pack.py --check`; regenerate the manifest after an
intentional font update with `uv run --with fonttools python scripts/audit-font-pack.py`.

## Substitutes

| CSS family aliases | Underlying open font |
| --- | --- |
| Arial, Helvetica, Helvetica Neue, Trebuchet MS | Arimo |
| Times New Roman, Times | Tinos |
| Courier New, Courier, Consolas, Menlo, Monaco | Cousine |
| Georgia / Calibri / Cambria | Gelasio / Carlito / Caladea |
| Segoe UI / Comic Sans MS / Impact | Selawik / Comic Neue / Anton |
| Verdana, Tahoma | DejaVu Sans |
| DejaVu Sans, Serif, Sans Mono | Original DejaVu families |
| Noto families | Original Noto families, including eight script-specific faces |

The shipped Arimo, Tinos, Cousine and Selawik files identify **SIL OFL 1.1** in
their embedded license metadata, as do the other non-DejaVu faces. Earlier
Apache/MIT labels in this directory were incorrect for these particular bytes.
DejaVu uses Bitstream Vera/Arev permissions; the full embedded notices are
included. Renaming preserves the source copyright and license metadata.

## Rendering and privacy limits

Bundling reduces dependence on installed fonts for these covered families.
It does not make all allowlisted OS fonts available. Several aliases are
approximate: DejaVu Sans is not Verdana or Tahoma, Cousine is not Menlo or
Consolas, and Arimo is not Trebuchet MS. Matching a few advance widths does not
establish matching glyph outlines, kerning, hinting, shaping or font versions.
Native rasterization remains CoreText, DirectWrite or FreeType according to
the actual host. Canvas noise and spacing noise do **not** establish that
foreign-OS rendering is indistinguishable from the claimed OS.

New identities can use host-constrained personas: the complete Bayesian tuple
is sampled conditional on the host OS, keeping native rendering and the
claimed OS aligned. Existing legacy identities remain unchanged until the
user explicitly changes appearance/mode. This reduces cross-OS contradictions;
it is not full cross-OS font independence or a guarantee of indistinguishability.

Rebuilding the pack with `scripts/build-font-pack.py` fetches upstream sources.
Those URLs are not immutable; review resulting bytes, embedded metadata and
license changes before accepting a new manifest. No fonts were downloaded or
replaced when this manifest was introduced.
