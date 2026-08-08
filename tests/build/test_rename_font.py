"""Regression test for scripts/rename-font.py (finding #9).

Builds a tiny VARIABLE font whose internal identity is the open substitute
"Arimo" — including nameID 25 (variations PS name prefix) and an fvar named
instance whose PostScript name is "Arimo-Bold" — renames it to "Arial", then
asserts that NO trace of "Arimo" survives in any identity record. Before the
fix, nameID 25 and the fvar instance PS name leaked "Arimo", letting a page
prove the machine claiming Arial is really running Arimo.

    python tests/build/test_rename_font.py   # exit 0 = pass
"""
import os
import sys
import tempfile

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
from importlib import import_module

rename_mod = import_module("rename-font")


def build_arimo_vf(path: str) -> None:
    glyph_order = [".notdef", "A"]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap({0x41: "A"})
    glyphs = {}
    for gn in glyph_order:
        pen = TTGlyphPen(None)
        pen.moveTo((0, 0))
        pen.lineTo((0, 500))
        pen.lineTo((500, 500))
        pen.lineTo((500, 0))
        pen.closePath()
        glyphs[gn] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({gn: (600, 0) for gn in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable(dict(
        familyName="Arimo", styleName="Regular", psName="Arimo",
        typographicFamily="Arimo",
    ))
    fb.setupOS2()
    fb.setupPost()
    fb.setupFvar(
        axes=[("wght", 400, 400, 700, "Weight")],
        instances=[
            dict(location={"wght": 400}, stylename="Regular",
                 postscriptname="Arimo-Regular"),
            dict(location={"wght": 700}, stylename="Bold",
                 postscriptname="Arimo-Bold"),
        ],
    )
    # nameID 25 — variations PostScript name prefix (the leak the fix targets).
    fb.font["name"].setName("Arimo", 25, 3, 1, 0x409)
    fb.save(path)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "Arimo.ttf")
        dst = os.path.join(tmp, "Arial.ttf")
        build_arimo_vf(src)
        rename_mod.rename(src, dst, "Arial")

        f = TTFont(dst)
        name = f["name"]

        fails = []

        # No identity record may still contain the source token "Arimo".
        for rec in name.names:
            s = rec.toUnicode()
            if "Arimo" in s:
                fails.append(f"nameID {rec.nameID} still contains 'Arimo': {s!r}")

        # nameID 25 must be the target PS prefix.
        n25 = name.getDebugName(25)
        if n25 != "Arial":
            fails.append(f"nameID 25 is {n25!r}, expected 'Arial'")

        # Every fvar instance PS name must be rebased onto Arial.
        for inst in f["fvar"].instances:
            psid = getattr(inst, "postscriptNameID", 0xFFFF)
            if psid in (0, 0xFFFF, None):
                continue
            ps = name.getDebugName(psid)
            if not ps or not ps.startswith("Arial"):
                fails.append(f"fvar instance PS name is {ps!r}, expected Arial-*")

        # Family must actually be Arial (the rename did happen).
        if name.getDebugName(1) != "Arial":
            fails.append(f"family is {name.getDebugName(1)!r}, expected 'Arial'")

    if fails:
        print("FAIL — rename-font.py left source-family traces:")
        for msg in fails:
            print(f"  - {msg}")
        return 1
    print("PASS — no 'Arimo' trace; nameID 25 + fvar instance PS names rebased to Arial")
    return 0


if __name__ == "__main__":
    sys.exit(main())
