"""Bundled-font packaging regression probe.

Verifies that the built/packaged app actually ships the open-substitute font
pack and that the bundled fonts render — the end-to-end result of:
  - the --enable-bundled-fonts build flag (MOZ_BUNDLED_FONTS),
  - the browser/fonts install rule staging bundle/fonts into dist/bin/fonts,
  - the XP_MACOSX package-manifest entry (font-bundle-packaging.patch) staging
    fonts/* into Contents/Resources/fonts.

Two checks, both host-independent (the target families are Windows/Linux fonts
that a stock macOS host does NOT have, so their presence proves the bundle):

  1. Filesystem: <app>/Contents/Resources/fonts exists and contains the pack
     (checked by a few representative filenames).
  2. Runtime: those families are detectable via text measurement (rendered).

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_bundled_fonts.py

Exit codes: 0 pass · 1 bundle missing/not rendering · 2 couldn't run.
"""

from __future__ import annotations

import json
import os
import sys
import time
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Representative pack files that must be present on disk (renamed substitutes).
EXPECT_FILES = ["SegoeUI.ttf", "Consolas.ttf", "DejaVuSans.ttf", "Arial.ttf"]
# Families a stock macOS host lacks — present only via the bundle.
EXPECT_RENDER = ["Segoe UI", "Consolas", "Calibri", "DejaVu Sans Mono"]

PROBE = """
const P = arguments[0];
function present(f){
  const b = ['monospace','sans-serif','serif'];
  const s = document.createElement('span');
  s.style.cssText = 'position:absolute;left:-9999px;font-size:72px';
  s.textContent = 'mmmwwwiiil'; document.body.appendChild(s);
  let d = false;
  for (const g of b){ s.style.fontFamily = g; const w = s.offsetWidth, h = s.offsetHeight;
    s.style.fontFamily = '"' + f + '",' + g;
    if (s.offsetWidth !== w || s.offsetHeight !== h){ d = true; break; } }
  document.body.removeChild(s); return d;
}
return JSON.stringify(P.filter(present));
"""


def fonts_dir_for(bin_path: str) -> Path | None:
    """Locate the packaged font pack, whatever the platform layout is.

    The pack lands in a different place per platform, and this used to assume
    the macOS one only:

        macOS   <app>/Contents/MacOS/cloakfox -> <app>/Contents/Resources/fonts
        Linux   <dir>/cloakfox                -> <dir>/fonts

    On Linux that produced "no Resources/fonts dir in the app (pack not
    staged)", which reads as a packaging regression. It was not: upstream
    already ships @RESPATH@/fonts/* for XP_WIN and MOZ_WIDGET_GTK
    (package-manifest.in), and Cloakfox's own stanza covers XP_MACOSX, so the
    pack IS packaged on Linux — the probe was just looking in a macOS-shaped
    path that cannot exist there.

    Returns None when no candidate exists, so the caller can say which paths
    it tried instead of naming one.
    """
    binp = Path(bin_path).resolve()
    candidates = [
        binp.parent.parent / "Resources" / "fonts",  # macOS bundle
        binp.parent / "fonts",                       # Linux / Windows
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def main(bin_path: str) -> int:
    fdir = fonts_dir_for(bin_path)
    if fdir is None:
        binp = Path(bin_path).resolve()
        print("FAIL — no bundled fonts dir found (pack not packaged). Tried:")
        print(f"    {binp.parent.parent / 'Resources' / 'fonts'}  (macOS bundle)")
        print(f"    {binp.parent / 'fonts'}  (Linux/Windows)")
        return 1
    print(f"  fonts dir: {fdir}")
    present_files = {p.name for p in fdir.glob("*.ttf")}
    missing = [f for f in EXPECT_FILES if f not in present_files]
    print(f"  pack files on disk: {len(present_files)} "
          f"(missing expected: {missing or 'none'})")
    if missing:
        print("FAIL — expected pack files missing from Resources/fonts")
        return 1

    # enabled=false: no cloakfox filtering; bundled fonts simply ADD to the host,
    # so a Windows/Linux family being detectable proves the bundle renders.
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text('user_pref("cloakfox.enabled", false);\n')
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(service_args=["--allow-system-access"], log_output=str(Path(prof) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.5)
            rendered = set(json.loads(d.execute_script(PROBE, EXPECT_RENDER)))
        finally:
            d.quit()

    print(f"  bundled families rendering: {sorted(rendered)}")
    not_rendered = [f for f in EXPECT_RENDER if f not in rendered]
    if not_rendered:
        print(f"FAIL — bundled families not rendering: {not_rendered} "
              "(staged on disk but not activated — check MOZ_BUNDLED_FONTS)")
        return 1
    print("PASS — pack is staged in the app AND its (host-absent) families render")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
