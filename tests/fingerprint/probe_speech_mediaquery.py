"""speechSynthesis + matchMedia spoofing regression probe.

Two OS-coherence vectors, both spoofed by JSWindowActors that derive the persona
OS from navigator.platform:

  * CloakfoxSpeech    — speechSynthesis.getVoices() returns an OS-coherent voice
                        list. The real host TTS voices are a blatant OS tell
                        (macOS ships Samantha/Alex, Windows David/Zira, Linux
                        eSpeak), so a Windows persona listing macOS voices would
                        contradict its own navigator.
  * CloakfoxMediaQuery — pins fingerprinting-relevant CSS media features
                        (prefers-color-scheme, pointer/hover, forced-colors,
                        color-gamut, dynamic-range) so they are persona-coherent
                        and host-independent, instead of leaking the real
                        device/OS (e.g. the host's dark-mode setting).

Checks (host-independent):
  1. Voices match the persona's OS (Windows persona -> Microsoft voices, etc.)
     and are consistent across two loads.
  2. matchMedia pins: light (not dark), pointer/hover fine+hover, and the
     color-gamut "min" semantics (a p3 persona matches srgb AND p3; nobody
     matches rec2020). macOS personas get p3, others srgb.
  3. An uncontrolled query ((min-width: 1px)) still delegates to native.
  4. Stealth: the wrappers must be native-identical — MediaQueryList.prototype
     .matches getter named "get matches" + [native code], no own properties on
     a MediaQueryList instance or on speechSynthesis, getVoices name/arity
     correct, and the fake voices are real SpeechSynthesisVoice instances with
     zero own properties (served via the inherited prototype getters).

Exit codes: 0 pass · 1 a spoof/stealth check regressed · 2 couldn't run.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_speech_mediaquery.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

# Distinctive substrings identifying each OS's voice set.
OS_VOICE_MARKERS = {
    "windows": "Microsoft",
    "macos": ("Samantha", "Daniel", "Alex"),
    "linux": "English (",
}

PROBE = r"""
const out = {plat: navigator.platform};
const v = speechSynthesis.getVoices();
out.voices = v.map(x => x.name);
out.voice_is_instance = v.length ? (v[0] instanceof SpeechSynthesisVoice) : null;
out.voice_own_props = v.length ? Object.getOwnPropertyNames(v[0]).length : null;

const mq = s => matchMedia(s).matches;
out.light = mq('(prefers-color-scheme: light)');
out.dark = mq('(prefers-color-scheme: dark)');
out.pointer_fine = mq('(pointer: fine)');
out.pointer_coarse = mq('(pointer: coarse)');
out.hover = mq('(hover: hover)');
out.forced_colors_none = mq('(forced-colors: none)');
out.reduced_motion_none = mq('(prefers-reduced-motion: no-preference)');
out.srgb = mq('(color-gamut: srgb)');
out.p3 = mq('(color-gamut: p3)');
out.rec2020 = mq('(color-gamut: rec2020)');
out.uncontrolled = mq('(min-width: 1px)');   // must delegate to native

// stealth
const d = Object.getOwnPropertyDescriptor(MediaQueryList.prototype, 'matches');
out.mq_getter_name = d && d.get ? d.get.name : null;
out.mq_getter_native = d && d.get ? (''+d.get).includes('[native code]') : null;
out.mq_own_props = Object.getOwnPropertyNames(matchMedia('(pointer: fine)')).length;
const gv = SpeechSynthesis.prototype.getVoices;
out.gv_name = gv.name; out.gv_len = gv.length;
out.gv_native = (''+gv).includes('[native code]');
out.synth_own_keys = Object.keys(speechSynthesis).length;
return JSON.stringify(out);
"""


def os_of(platform: str) -> str:
    p = platform.lower()
    if "win" in p:
        return "windows"
    if "mac" in p:
        return "macos"
    return "linux"


def run(bin_path: str) -> dict:
    with tempfile.TemporaryDirectory() as t:
        prof = os.path.join(t, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text('user_pref("cloakfox.enabled", true);\n')
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-remote-allow-system-access")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(options=opts,
                              service=Service(log_output=str(Path(prof) / "g.log")))
        try:
            d.set_page_load_timeout(30)
            d.get("https://example.com/")
            time.sleep(1.5)
            d.get("https://example.com/?w=1")   # 2nd load: persona settled
            time.sleep(1.5)
            return json.loads(d.execute_script(PROBE))
        finally:
            d.quit()


def main(bin_path: str) -> int:
    r = run(bin_path)
    persona_os = os_of(r["plat"])
    print(f"  persona: {r['plat']} ({persona_os})")
    print(f"  voices: {r['voices']}")
    print(f"  media: light={r['light']} dark={r['dark']} pointer_fine={r['pointer_fine']} "
          f"hover={r['hover']} srgb={r['srgb']} p3={r['p3']} rec2020={r['rec2020']}")
    print()

    fails = []

    # 1. voices present + OS-coherent
    if not r["voices"]:
        fails.append("speechSynthesis.getVoices() returned no voices "
                     "(actor did not fire)")
    else:
        marker = OS_VOICE_MARKERS[persona_os]
        markers = marker if isinstance(marker, tuple) else (marker,)
        joined = " ".join(r["voices"])
        if not any(m in joined for m in markers):
            fails.append(f"voices {r['voices']} do not match the persona OS "
                         f"({persona_os}, expected one of {markers})")

    # 2. media-feature pins
    if not r["light"] or r["dark"]:
        fails.append(f"prefers-color-scheme not pinned to light "
                     f"(light={r['light']} dark={r['dark']})")
    if not r["pointer_fine"] or r["pointer_coarse"]:
        fails.append("pointer not pinned to fine")
    if not r["hover"]:
        fails.append("hover not pinned to hover")
    if not r["forced_colors_none"] or not r["reduced_motion_none"]:
        fails.append("forced-colors / prefers-reduced-motion not pinned")
    # color-gamut "min" semantics: srgb always true; p3 iff macOS persona
    if not r["srgb"]:
        fails.append("color-gamut srgb should always match")
    expect_p3 = persona_os == "macos"
    if r["p3"] != expect_p3:
        fails.append(f"color-gamut p3={r['p3']} but persona is {persona_os} "
                     f"(expected {expect_p3})")
    if r["rec2020"]:
        fails.append("color-gamut rec2020 should not match")
    if not r["uncontrolled"]:
        fails.append("(min-width: 1px) did not match — uncontrolled queries "
                     "must delegate to the native getter")

    # 3. stealth
    if r["mq_getter_name"] != "get matches":
        fails.append(f"MediaQueryList.matches getter name={r['mq_getter_name']!r} "
                     "(native 'get matches')")
    if not r["mq_getter_native"]:
        fails.append("MediaQueryList.matches getter does not stringify as native")
    if r["mq_own_props"]:
        fails.append(f"MediaQueryList instance has {r['mq_own_props']} own props "
                     "(native 0)")
    if r["gv_name"] != "getVoices" or r["gv_len"] != 0 or not r["gv_native"]:
        fails.append(f"getVoices identity wrong: name={r['gv_name']!r} "
                     f"len={r['gv_len']} native={r['gv_native']}")
    if r["synth_own_keys"]:
        fails.append(f"speechSynthesis has {r['synth_own_keys']} own enumerable "
                     "keys (native 0)")
    if r["voices"] and not r["voice_is_instance"]:
        fails.append("fake voices are not SpeechSynthesisVoice instances")
    if r["voices"] and r["voice_own_props"]:
        fails.append(f"fake voice has {r['voice_own_props']} own props "
                     "(native 0 — must be served via prototype getters)")

    if fails:
        print("FAIL — speech/media-query spoofing regressed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS — voices are OS-coherent, media features pinned, uncontrolled "
          "queries delegate, and all wrappers are native-identical")
    return 0


if __name__ == "__main__":
    b = os.environ.get("CLOAKFOX_BIN")
    if not b or not os.path.exists(b):
        sys.exit("CLOAKFOX_BIN not set or binary missing")
    sys.exit(main(b))
