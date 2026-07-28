"""
Actor-stealth regression probe.

The JSWindowActor spoofers (Math, Gamepad, Midi, FeatureDetect, Timing…)
patch page objects via Cu.exportFunction. Two classes of tamper tell were
fixed and must not regress:

  1. Own-enumerable descriptor leaks. Installing a spoof by plain assignment
     (`navigator.getGamepads = …`, `spoofedMath[fn] = …`) creates an OWN
     ENUMERABLE property where native keeps it inherited/non-enumerable, so
     Object.keys(navigator) leaked ["getGamepads","gpu","javaEnabled",
     "requestMIDIAccess"] and Object.keys(Math) leaked all 23 method names.
     Stock Firefox returns [] for both. Fix: define on the prototype with
     native flags.

  2. Wrong function identity. exportFunction yields name:"" length:0, but
     native methods report their own name + arity (Math.sin.name==="sin",
     Math.pow.length===2). Fix: copy native name/length onto the wrapper.

This probe runs in page MAIN context (a persona is active by default) and
asserts both are native-identical. All checks are host-independent.

Exit codes: 0 all pass · 1 a tell regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_actor_stealth.py
"""

from __future__ import annotations

import json
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Native name + arity for each wrapped function the actors replace.
EXPECT_FNS = {
    "Math.sin": ("sin", 1),
    "Math.pow": ("pow", 2),
    "Math.atan2": ("atan2", 2),
    "navigator.getGamepads": ("getGamepads", 0),
    "navigator.requestMIDIAccess": ("requestMIDIAccess", 0),
    "navigator.javaEnabled": ("javaEnabled", 0),
    "performance.now": ("now", 0),
    "setTimeout": ("setTimeout", 1),
    "addEventListener": ("addEventListener", 2),
}

PROBE = r"""
const s = document.createElement('script');
s.textContent = `
  const id = (fn) => ({name: fn.name, len: fn.length,
                       nat: (''+fn).includes('[native code]')});
  const r = {
    nav_keys: Object.keys(navigator),          // native: []
    math_keys: Object.keys(Math).length,       // native: 0
    perf_now_own: !!Object.getOwnPropertyDescriptor(performance, 'now'), // native: false
    fns: {
      'Math.sin': id(Math.sin), 'Math.pow': id(Math.pow),
      'Math.atan2': id(Math.atan2),
      'navigator.getGamepads': id(navigator.getGamepads),
      'navigator.requestMIDIAccess': id(navigator.requestMIDIAccess),
      'navigator.javaEnabled': id(navigator.javaEnabled),
      'performance.now': id(performance.now),
      'setTimeout': id(setTimeout),
      'addEventListener': id(EventTarget.prototype.addEventListener),
    },
    // sanity: the Math actor actually fired (trig noised), so these checks
    // are meaningful rather than passing because nothing ran.
    sin_noised: Math.sin(0.5) !== 0.479425538604203,
  };
  const out = document.createElement('pre');
  out.id = '_actor'; out.textContent = JSON.stringify(r);
  document.body.appendChild(out);
`;
document.body.appendChild(s);
"""


def run(bin_path: str) -> int:
    opts = Options()
    opts.binary_location = bin_path
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    d = webdriver.Firefox(options=opts,
                          service=Service(log_path="/tmp/probe-actor.log"))
    try:
        d.set_page_load_timeout(30)
        d.get("https://example.com/")
        time.sleep(1.5)
        d.get("https://example.com/?warm=1")  # 2nd nav — persona settled
        time.sleep(1.5)
        d.execute_script(PROBE)
        raw = None
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                raw = d.find_element("id", "_actor").text
                if raw:
                    break
            except Exception:
                pass
            time.sleep(0.3)
        if not raw:
            print("probe element missing — inline script didn't run")
            return 2
        r = json.loads(raw)
    finally:
        d.quit()

    fails = []
    if not r.get("sin_noised"):
        return _bail("Math actor did not fire (Math.sin unmodified) — "
                     "cannot assess stealth", r)
    if r["nav_keys"]:
        fails.append(f"Object.keys(navigator) leaked {r['nav_keys']} (native [])")
    if r["math_keys"] != 0:
        fails.append(f"Object.keys(Math) leaked {r['math_keys']} names (native 0)")
    if r["perf_now_own"]:
        fails.append("performance.now is an OWN property (native: inherited)")
    for key, (name, length) in EXPECT_FNS.items():
        v = r["fns"][key]
        if v["name"] != name:
            fails.append(f"{key}.name = {v['name']!r} (native {name!r})")
        if v["len"] != length:
            fails.append(f"{key}.length = {v['len']} (native {length})")
        if not v["nat"]:
            fails.append(f"{key} does not stringify as [native code]")

    print("=== actor-stealth checks ===")
    print(f"  Object.keys(navigator): {r['nav_keys'] or '[]'}")
    print(f"  Object.keys(Math).length: {r['math_keys']}")
    print(f"  sample fns: sin={r['fns']['Math.sin']} pow={r['fns']['Math.pow']}")
    print()
    if fails:
        print("FAIL — stealth tell(s) regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — no descriptor/name/arity tells; wrappers are native-identical")
    return 0


def _bail(msg, r):
    print(f"INCONCLUSIVE — {msg}")
    print(json.dumps(r, indent=2))
    return 2


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(run(b))
