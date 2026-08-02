"""
Per-container font-metric-noise regression probe.

The anti-font-fingerprinting patch (FontSpacingSeedManager + gfxHarfBuzzShaper)
adds up to 0.1px of letter-spacing PER GLYPH, driven by a per-container seed the
persona publishes in the cloak_cfg blob under "fonts:spacing_seed". This breaks
text-measurement fingerprinting (offsetWidth / getBoundingClientRect) that would
otherwise read the host's exact glyph advances.

CRITICAL: measure a CONCRETE whitelisted font (Arial), not a CSS generic. With
the font whitelist active, generic families (sans-serif/serif/monospace) resolve
NONDETERMINISTICALLY across launches, so a generic-family probe reports "enabled
profiles differ" even when the spacing seed is completely dead — a false pass.
Arial resolves deterministically, so any width change is genuine spacing.

Over a ~360-glyph string a live seed shifts Arial's width by up to ~36px; a dead
seed leaves it within measurement jitter (<0.5px) of the disabled baseline. The
decisive assertion is therefore "enabled differs from disabled", not merely
"enabled profiles differ from each other":

  disabled: clean stock width W0 (deterministic across profiles)
  enabled : W0 + per-glyph spacing; must differ from W0 by >1px, differ between
            two fresh personas, and be stable across launches of one profile

Exit codes: 0 pass · 1 noise inactive/regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_font_metric_noise.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Arial is on the whitelist and resolves to a single concrete face, so it is
# not subject to generic-family resolution nondeterminism. The long repeated
# string accumulates per-glyph spacing into a large, unambiguous width delta.
MEASURE = r"""
const s = document.createElement('span');
s.style.cssText =
  'position:absolute;left:-9999px;white-space:nowrap;font:16px Arial';
s.textContent = 'WWWWWWWWWW iiiiiiiiii gjpqygjpqy 0123456789'.repeat(3);
document.body.appendChild(s);
return parseFloat(s.getBoundingClientRect().width.toFixed(5));
"""

# A dead seed leaves enabled within jitter of disabled (~0.2px observed); a live
# seed shifts by whole pixels. 1px cleanly separates the two.
MIN_SHIFT_PX = 1.0


def measure(bin_path: str, enabled: bool, prof: str) -> float:
    Path(prof).mkdir(parents=True, exist_ok=True)
    Path(prof, "user.js").write_text(
        f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
    )
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    opts.add_argument("-profile")
    opts.add_argument(prof)
    d = webdriver.Firefox(options=opts,
                          service=Service(log_path=str(Path(prof) / "gd.log")))
    try:
        d.set_page_load_timeout(30)
        d.get("https://example.com/")
        time.sleep(1.2)
        return float(d.execute_script(MEASURE))
    finally:
        d.quit()


def main(bin_path: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        w0 = measure(bin_path, False, os.path.join(tmp, "d1"))
        w0b = measure(bin_path, False, os.path.join(tmp, "d2"))
        ea = measure(bin_path, True, os.path.join(tmp, "ea"))
        eb = measure(bin_path, True, os.path.join(tmp, "eb"))
        ea2 = measure(bin_path, True, os.path.join(tmp, "ea"))  # same profile again

    print(f"  disabled  #1/#2: {w0} / {w0b}")
    print(f"  enabled   A/A':  {ea} / {ea2}")
    print(f"  enabled   B:     {eb}")
    print(f"  |A-disabled|={abs(ea - w0):.3f}px  |B-disabled|={abs(eb - w0):.3f}px")
    print()

    fails = []
    if w0 != w0b:
        fails.append(f"disabled Arial width differs across profiles ({w0} vs "
                     f"{w0b}) — stock metrics should be deterministic")
    if abs(ea - w0) < MIN_SHIFT_PX and abs(eb - w0) < MIN_SHIFT_PX:
        fails.append(f"enabled Arial width within {MIN_SHIFT_PX}px of disabled "
                     f"for both personas — the fonts:spacing_seed noise is dead "
                     f"(check the cloak_cfg key matches C++)")
    if ea == eb:
        fails.append("two fresh personas produced identical enabled width — "
                     "the seed is not per-container")
    if ea != ea2:
        fails.append(f"same profile gave different widths across launches "
                     f"({ea} vs {ea2}) — spacing is not deterministic")

    if fails:
        print("FAIL — font-metric noise regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — enabled shifts Arial width per-persona (deterministically); "
          "disabled measures clean stock metrics")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
