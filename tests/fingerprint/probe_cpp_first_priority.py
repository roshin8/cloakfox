"""
Step 2 verification — cpp-first pref priority end-to-end.

Launches the browser twice with different `cloakfox.s.canvasSeed_0`
values. On each run, draws a canvas and hashes its pixels. If the
hashes differ, the cpp-first pref IS driving canvas spoofing output
(the C++ RoverfoxStorageManager::GetUint TryGetCppFirstPref priority
check is actually wired in).

If hashes are identical across runs with different cpp-first prefs,
something is wrong:
  - The extension might be overwriting via setCanvasSeed (race)
  - The priority check might not be hit
  - The pref might not be reaching content process

Usage:
  CLOAKFOX_DMG=/path/to/Cloakfox.dmg \\
      python tests/fingerprint/probe_cpp_first_priority.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

DEFAULT_DMG = "/tmp/cfx-artifact3/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg"


def mount_and_extract(dmg_path, dest_dir):
    result = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", dmg_path],
        check=True, capture_output=True, text=True,
    )
    mount_point = None
    for line in result.stdout.splitlines():
        s = line.strip()
        if s.startswith("<string>/Volumes/"):
            mount_point = s.removeprefix("<string>").removesuffix("</string>")
            break
    if not mount_point:
        sys.exit("no mount point found")
    apps = [p for p in os.listdir(mount_point) if p.endswith(".app")]
    src_app = os.path.join(mount_point, apps[0])
    os.makedirs(dest_dir, exist_ok=True)
    dest_app = os.path.join(dest_dir, apps[0])
    if os.path.exists(dest_app):
        shutil.rmtree(dest_app)
    subprocess.run(["cp", "-R", src_app, dest_app], check=True)
    subprocess.run(["xattr", "-cr", dest_app], check=False)
    subprocess.run(["hdiutil", "detach", mount_point, "-force"], check=False)
    return os.path.join(dest_app, "Contents", "MacOS", "cloakfox")


def launch_and_hash_canvas(binary, canvas_seed_value):
    """Launch browser with cloakfox.s.canvasSeed_0 = canvas_seed_value,
    draw a canvas, return a hex hash of the pixel bytes."""
    profile_dir = tempfile.mkdtemp(prefix="cfx-prio-")
    # user.js must use user_pref for every pref — including our cpp-first.
    # cloakfox.enabled gates the Math actor, irrelevant here but harmless.
    with open(os.path.join(profile_dir, "user.js"), "w") as f:
        f.write(f'''
user_pref("cloakfox.enabled", true);
user_pref("cloakfox.s.canvasSeed_0", "{canvas_seed_value}");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("toolkit.startup.max_resumed_crashes", -1);
''')
    opts = Options()
    opts.binary_location = binary
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    opts.add_argument("-no-remote")
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    svc = Service(log_path="/tmp/probe-priority.log")
    driver = webdriver.Firefox(options=opts, service=svc)
    try:
        driver.get("https://example.com/")
        time.sleep(1.5)
        # Draw a deterministic canvas, return its raw pixel data as
        # a hex-encoded SHA-256 via a document attribute.
        driver.execute_script("""
          const s = document.createElement('script');
          s.textContent = `
            (async () => {
              const c = document.createElement('canvas');
              c.width = 200; c.height = 60;
              const ctx = c.getContext('2d');
              ctx.fillStyle = '#f60'; ctx.fillRect(0, 0, 200, 60);
              ctx.fillStyle = '#069'; ctx.font = '20px Arial';
              ctx.fillText('cloakfox-probe', 10, 40);
              const data = ctx.getImageData(0, 0, 200, 60).data;
              // Manual SHA-256 via SubtleCrypto
              const h = await crypto.subtle.digest('SHA-256', data);
              const hex = Array.from(new Uint8Array(h)).map(b => b.toString(16).padStart(2,'0')).join('');
              document.body.setAttribute('data-canvas-hash', hex);
            })();
          `;
          document.head.appendChild(s);
        """)
        time.sleep(0.8)
        hash_hex = driver.execute_script(
            "return document.body.getAttribute('data-canvas-hash');"
        )
        return hash_hex
    finally:
        driver.quit()
        shutil.rmtree(profile_dir, ignore_errors=True)


def main():
    dmg = os.environ.get("CLOAKFOX_DMG", DEFAULT_DMG)
    work_dir = tempfile.mkdtemp(prefix="cfx-prio-work-")
    print(f"[setup] DMG: {dmg}")
    print(f"[setup] work dir: {work_dir}")

    binary = mount_and_extract(dmg, os.path.join(work_dir, "app"))

    print("\n[test] Run 1: cloakfox.s.canvasSeed_0 = 11111")
    hash_a = launch_and_hash_canvas(binary, 11111)
    print(f"[test] canvas hash A: {hash_a}")

    print("\n[test] Run 2: cloakfox.s.canvasSeed_0 = 99999")
    hash_b = launch_and_hash_canvas(binary, 99999)
    print(f"[test] canvas hash B: {hash_b}")

    print("\n=== Result ===")
    if not hash_a or not hash_b:
        print("FAIL — a probe didn't return a hash (canvas draw or SHA crypto broke)")
        return 2
    if hash_a == hash_b:
        print(f"""FAIL — canvas hashes identical across different cpp-first seeds.

cpp-first priority is NOT driving canvas output. Either:
  1. TryGetCppFirstPref isn't being called (patch didn't land)
  2. Extension's setCanvasSeed is still winning somehow
  3. pref name mismatch (check key is canvasSeed_<ucid>)
  4. Extension uses a domain-derived seed that ignores canvasSeed
     prefs, and C++ is returning 0 so both runs fall through to
     the same fallback path

Hash: {hash_a}""")
        return 1
    print(f"PASS — different cpp-first seeds produce different canvas outputs.")
    print(f"  seed=11111 → {hash_a[:16]}...")
    print(f"  seed=99999 → {hash_b[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
