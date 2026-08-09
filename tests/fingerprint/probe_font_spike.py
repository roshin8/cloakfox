"""Phase-0 spike probe: which font families are enumerable?

Detects, from a fixed panel, (a) a bundled test family that is NOT normally a
macOS system font ("Charis SIL Compact") and (b) a real host family ("Geneva").
Run against the built binary with the spike pref off, then on.

    CLOAKFOX_BIN=.../cloakfox CLOAKFOX_SPIKE=0|1 \
        python tests/fingerprint/probe_font_spike.py
"""
import os
import json
import time
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

BUNDLED = "Charis SIL Compact"   # in-tree test font we will register
HOST = "Geneva"                  # a real macOS system family (should vanish when suppressed)
PANEL = [BUNDLED, HOST, "Arial", "Helvetica", "Menlo", "Times New Roman"]

PROBE = """
const P = arguments[0];
function present(f){
  const b=['monospace','sans-serif','serif'];
  const s=document.createElement('span');
  s.style.cssText='position:absolute;left:-9999px;font-size:72px';
  s.textContent='mmmwwwiiilQ'; document.body.appendChild(s);
  let d=false;
  for(const g of b){ s.style.fontFamily=g; const w=s.offsetWidth,h=s.offsetHeight;
    s.style.fontFamily='"'+f+'",'+g;
    if(s.offsetWidth!==w||s.offsetHeight!==h){d=true;break;} }
  document.body.removeChild(s); return d;
}
return JSON.stringify(P.filter(present));
"""


def main():
    spike = os.environ.get("CLOAKFOX_SPIKE", "0") == "1"
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "p")
        Path(p).mkdir()
        # enabled=false isolates the CoreText register/suppress mechanism from
        # the cloakfox whitelist/narrowing (which otherwise masks enumeration).
        Path(p, "user.js").write_text(
            'user_pref("cloakfox.enabled", false);\n'
            f'user_pref("cloakfox.fonts.bundle_spike", {"true" if spike else "false"});\n')
        o = Options()
        o.binary_location = os.environ["CLOAKFOX_BIN"]
        o.add_argument("--headless")
        o.add_argument("-profile")
        o.add_argument(p)
        d = webdriver.Firefox(options=o, service=Service(service_args=["--allow-system-access"], log_path=str(Path(p) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.5)
            found = set(json.loads(d.execute_script(PROBE, PANEL)))
        finally:
            d.quit()
    print(f"spike={'on' if spike else 'off'} present={sorted(found)}")
    print(f"  bundled '{BUNDLED}' present: {BUNDLED in found}")
    print(f"  host    '{HOST}' present:    {HOST in found}")


if __name__ == "__main__":
    if not os.environ.get("CLOAKFOX_BIN"):
        raise SystemExit("set CLOAKFOX_BIN")
    main()
