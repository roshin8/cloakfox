"""
Per-container font-metric-noise regression probe.

The anti-font-fingerprinting patch (FontSpacingSeedManager) perturbs text
metrics deterministically from a per-userContextId seed the persona pipeline
publishes as `font:spacing_seed` (CloakfoxSeedSync -> nsGlobalWindowInner ->
FontSpacingSeedManager::SetSeed -> gfxTextRun/gfxHarfBuzzShaper). This breaks
text-measurement fingerprinting (offsetWidth / getBoundingClientRect on shared
fonts) that would otherwise expose the real host's exact glyph metrics.

Host-independent relative check — no hardcoded metrics, holds on any machine:

  enabled twice  (fresh profiles -> random personas -> different seeds)
    => measured metrics must DIFFER (the noise is live and seed-driven)
  disabled twice (fresh profiles)
    => measured metrics must be IDENTICAL (stock Firefox, no perturbation)

A live spoofer emits a random per-profile seed, so identical metrics across two
enabled profiles would mean the noise never ran; differing metrics across two
disabled profiles would mean something other than our seed is perturbing them.

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

# A long, glyph-varied line in a generic family so metrics come from the host's
# real fonts (which the spacing seed then perturbs). Repeated to accumulate
# per-character noise into a measurable width delta.
MEASURE = r"""
const s = document.createElement('span');
s.style.cssText =
  'position:absolute;left:-9999px;font:16px sans-serif;white-space:nowrap';
s.textContent = 'The quick brown fox jumps 0123456789 WWWWiiiigjpqy '.repeat(6);
document.body.appendChild(s);
const r = s.getBoundingClientRect();
return r.width.toFixed(6) + '|' + r.height.toFixed(6);
"""


def measure(bin_path: str, enabled: bool) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        prof = os.path.join(tmp, "p")
        Path(prof).mkdir()
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
            return d.execute_script(MEASURE)
        finally:
            d.quit()


def main(bin_path: str) -> int:
    en1, en2 = measure(bin_path, True), measure(bin_path, True)
    di1, di2 = measure(bin_path, False), measure(bin_path, False)
    print(f"  enabled  #1: {en1}")
    print(f"  enabled  #2: {en2}")
    print(f"  disabled #1: {di1}")
    print(f"  disabled #2: {di2}")
    print()

    if not en1 or not en2 or not di1 or not di2:
        print("could not measure metrics (probe didn't run)")
        return 2

    fails = []
    if en1 == en2:
        fails.append("enabled metrics identical across two fresh profiles — "
                     "the per-container spacing seed is not being applied")
    if di1 != di2:
        fails.append("disabled metrics differ across two fresh profiles — "
                     "something other than our seed is perturbing text (unexpected)")

    if fails:
        print("FAIL — font-metric noise regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — enabled builds perturb text metrics per seed; disabled builds "
          "measure clean stock metrics")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
