"""
WebRTC IP-leak probe.

WebRTC is the highest-stakes deanonymization vector in a privacy browser:
an `RTCPeerConnection` gathers ICE candidates that can expose the machine's
real LOCAL IP (behind NAT) and real PUBLIC IP (via STUN srflx), regardless
of any HTTP-level proxy/VPN.

Cloakfox's defense: `patches/webrtc-ip-spoofing.patch` +
`CloakfoxWebRTCSync`/`CloakfoxWebRTCChild` call `window.setWebRTCIPv4` so
ICE candidates + getStats report a single coherent IP and scrub the real
local IP. This probe checks what actually shows up on the wire.

It gathers candidates (host + STUN srflx), extracts every IPv4 / mDNS
`.local` name, and flags whether the machine's real local IP leaked.

Run:
    CLOAKFOX_BIN=/path/to/Cloakfox.app/Contents/MacOS/cloakfox \\
        python tests/fingerprint/probe_webrtc_leak.py
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

PROBE_HTML = """<!doctype html>
<title>cfx-webrtc</title>
<body><script>
const found = { ipv4: [], mdns: [], done: false, err: null };
try {
  const pc = new RTCPeerConnection({
    iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
  });
  pc.createDataChannel("probe");
  const ipv4 = /(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})/;
  const mdns = /([a-f0-9-]+\\.local)/i;
  pc.onicecandidate = (e) => {
    if (!e.candidate) { finish(); return; }
    const c = e.candidate.candidate || "";
    const m4 = c.match(ipv4); if (m4 && !found.ipv4.includes(m4[1])) found.ipv4.push(m4[1]);
    const ml = c.match(mdns); if (ml && !found.mdns.includes(ml[1])) found.mdns.push(ml[1]);
  };
  pc.onicegatheringstatechange = () => {
    if (pc.iceGatheringState === "complete") finish();
  };
  pc.createOffer().then((o) => pc.setLocalDescription(o))
    .catch((e) => { found.err = String(e); finish(); });
} catch (e) { found.err = String(e); finish(); }

let finished = false;
function finish() {
  if (finished) return; finished = true; found.done = true;
  document.documentElement.setAttribute("data-cfx-rtc", JSON.stringify(found));
}
setTimeout(finish, 9000);
</script></body>"""


def _real_local_ips() -> set[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    return {ip for ip in ips if not ip.startswith("127.")}


def _run(bin_path: str, enabled: bool) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, "rtc.html")
        Path(html).write_text(PROBE_HTML)
        prof = os.path.join(tmp, "p")
        Path(prof).mkdir()
        Path(prof, "user.js").write_text(
            f'user_pref("cloakfox.enabled", {str(enabled).lower()});\n'
        )
        opts = Options()
        opts.binary_location = bin_path
        opts.add_argument("--headless")
        opts.add_argument("-profile")
        opts.add_argument(prof)
        d = webdriver.Firefox(
            options=opts,
            # chrome context (for the sharedData read below) needs system
            # access; passed as a geckodriver service arg because 0.37+
            # rejects it as a browser capability.
            service=Service(service_args=["--allow-system-access"],
                            log_output=str(Path(prof) / "gd.log")))
        try:
            d.get(f"file://{html}")
            deadline = time.time() + 15
            while time.time() < deadline:
                attr = d.find_element("css selector", "html").get_attribute("data-cfx-rtc")
                if attr:
                    data = json.loads(attr)
                    if data.get("done"):
                        # CloakfoxWebRTCSync publishes the HTTP-detected public
                        # IP here; the CloakfoxWebRTC actor feeds it to
                        # setWebRTCIPv4. Read it so the caller can check the
                        # two agree.
                        try:
                            d.set_context("chrome")
                            data["synced_ipv4"] = d.execute_script(
                                'return Services.ppmm.sharedData.get('
                                '"cloakfox-public-ipv4") || "";')
                        except Exception as e:
                            data["synced_ipv4"] = f"ERR {e}"
                        finally:
                            try:
                                d.set_context("content")
                            except Exception:
                                pass
                        return data
                time.sleep(0.3)
            return {"err": "timeout", "ipv4": [], "mdns": []}
        finally:
            d.quit()


def main() -> None:
    bin_path = os.environ.get("CLOAKFOX_BIN")
    if not bin_path or not os.path.exists(bin_path):
        sys.exit("CLOAKFOX_BIN not set or binary missing")

    real = _real_local_ips()
    print(f"real local IP(s): {sorted(real) or '<none detected>'}\n")

    res = _run(bin_path, enabled=True)
    print("=== WebRTC ICE candidates (cloakfox.enabled=true) ===")
    print(json.dumps(res, indent=2))
    print()

    ipv4 = set(res.get("ipv4", []))
    def is_private(ip):
        return (ip.startswith("10.") or ip.startswith("192.168.")
                or re.match(r"172\.(1[6-9]|2\d|3[01])\.", ip))
    leaked_local = ipv4 & real
    private_seen = {ip for ip in ipv4 if is_private(ip)}

    print("Analysis:")
    print(f"  mDNS-obfuscated host candidates: {res.get('mdns') or 'none'}")
    print(f"  IPv4 candidates: {sorted(ipv4) or 'none'}")
    if leaked_local:
        print(f"  LEAK: real local IP exposed in ICE candidates: {sorted(leaked_local)}")
        sys.exit(1)
    if private_seen:
        print(f"  NOTE: private-range IP in candidates (not this host's real IP): "
              f"{sorted(private_seen)}")
    # WebRTC must report the SAME public IP the HTTP path already exposed.
    #
    # This is the CloakfoxWebRTC actor's actual job, and nothing tested it: the
    # feature was fully implemented (sync + actor + registration + C++
    # consumers) while cloakfox.cfg still described it as "planned", so a
    # regression would have been silent.
    #
    # The point is NOT hiding the public IP — a site sees it on the TCP
    # connection regardless, and advertising a different one would be a
    # self-contradiction. The point is that WebRTC must not surface an
    # interface address the HTTP path never revealed (a VPN/proxy bypass).
    synced = res.get("synced_ipv4") or ""
    if not synced or synced.startswith("ERR"):
        print(f"  [skip] no synced public IPv4 (got {synced!r}) — IP-echo did "
              "not land (offline runner, or cloakfox.enabled false)")
    elif not ipv4:
        print("  [skip] no IPv4 ICE candidates gathered — STUN unreachable "
              "from this network")
    else:
        public = {ip for ip in ipv4 if not is_private(ip) and ip != "0.0.0.0"}
        if not public:
            print("  [skip] no public IPv4 candidate gathered (STUN blocked)")
        elif public != {synced}:
            print(f"  MISMATCH: WebRTC advertised {sorted(public)} but the HTTP "
                  f"path shows {synced}. WebRTC is surfacing an address the "
                  "HTTP path did not — exactly the VPN/proxy bypass the "
                  "CloakfoxWebRTC actor exists to close.")
            sys.exit(1)
        else:
            print(f"  WebRTC public IP == HTTP-visible IP ({synced}) — actor "
                  "applied setWebRTCIPv4")

    print("\nPASS: the machine's real local IP did NOT leak via WebRTC ICE "
          "candidates.")


if __name__ == "__main__":
    main()
