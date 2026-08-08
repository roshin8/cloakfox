"""Rename a font's family name-table entries to a target family name.

Cloakfox bundles openly-licensed, metric-compatible substitute fonts (OFL /
Apache / MIT) and presents them under the target family names that personas
claim (e.g. an open Arial-metric font presented as "Arial", an open Segoe UI
substitute presented as "Segoe UI"). On macOS there is no fontconfig aliasing,
so the substitution must be baked into the font's own name table.

This edits nameIDs 1/16 (family / typographic family), 4 (full name), 6
(PostScript name), 3 (unique id) and 25 (variations PostScript name prefix) on
all platform/encoding records. For variable fonts it ALSO rewrites the
PostScript name of every fvar named instance — macOS registers those instance
PostScript names, so a leftover "Arimo-Bold" would let a page prove the machine
claiming "Arial" is actually running Arimo (`document.fonts.check('1em
Arimo-Bold')` / `local('Arimo-Bold')`), defeating the rename.

Usage:
    python scripts/rename-font.py <src.ttf> <dst.ttf> "<Target Family>"
"""
import sys

from fontTools.ttLib import TTFont


def rename_names(font: TTFont, target: str) -> None:
    """Rewrite the identity records of an already-loaded font in place."""
    ps = target.replace(" ", "")
    name = font["name"]

    for rec in name.names:
        if rec.nameID in (1, 16):      # Family / Typographic Family
            rec.string = target
        elif rec.nameID == 4:          # Full name
            rec.string = target
        elif rec.nameID == 6:          # PostScript name
            rec.string = ps
        elif rec.nameID == 3:          # Unique ID
            rec.string = f"{ps};cloakfox"
        elif rec.nameID == 25:         # Variations PostScript Name Prefix
            rec.string = ps

    # Variable fonts: rewrite each named instance's PostScript name so it no
    # longer carries the source family (e.g. "Arimo-Bold" -> "Arial-Bold").
    # These records live at nameID >= 256 and are referenced by fvar instances.
    if "fvar" in font:
        for inst in font["fvar"].instances:
            psid = getattr(inst, "postscriptNameID", 0xFFFF)
            if psid in (0, 0xFFFF, None):
                continue
            style = name.getDebugName(inst.subfamilyNameID) or "Regular"
            new_ps = f"{ps}-{style.replace(' ', '')}"
            for rec in name.names:
                if rec.nameID == psid:
                    rec.string = new_ps


def rename(src: str, dst: str, target: str) -> None:
    ps = target.replace(" ", "")
    f = TTFont(src)
    rename_names(f, target)
    f.save(dst)
    print(f"renamed {src} -> family '{target}' (ps '{ps}') -> {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: rename-font.py <src.ttf> <dst.ttf> <Target Family>")
    rename(sys.argv[1], sys.argv[2], sys.argv[3])
