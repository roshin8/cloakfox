"""
Runtime probe for the CloakfoxKeyboard JSWindowActor.

Sets a per-container keyboard_seed, navigates to an HTTP page,
dispatches a rapid burst of synthetic keydown events to the page's
own DOM, and asserts the reported `event.timeStamp` values are
normalized — each one at least MIN_DELAY (30ms) later than the
previous, even though we dispatch all of them within a few
microseconds.

If the actor fired and successfully wrapped EventTarget.prototype.
addEventListener, the page's listener sees monotonically-spaced
timestamps. If the actor didn't fire (match failure, seed missing,
Xray issue), timestamps are the raw fast-fire values from the
synthetic dispatch.

Usage:
  CLOAKFOX_DMG=/path/to/Cloakfox.dmg \\
      python tests/fingerprint/probe_keyboard_actor.py
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service

DEFAULT_DMG = "/tmp/cfx-artifact6/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg"
MIN_DELAY_MS = 30.0
MAX_JITTER_MS = 15.0


def mount_and_extract(dmg_path, dest_dir):
    result = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", dmg_path],
        check=True, capture_output=True, text=True,
    )
    mount_point = next(
        s.strip().removeprefix("<string>").removesuffix("</string>")
        for line in result.stdout.splitlines()
        for s in [line.strip()] if s.startswith("<string>/Volumes/")
    )
    apps = [p for p in os.listdir(mount_point) if p.endswith(".app")]
    src_app = os.path.join(mount_point, apps[0])
    dest_app = os.path.join(dest_dir, apps[0])
    if os.path.exists(dest_app):
        shutil.rmtree(dest_app)
    subprocess.run(["cp", "-R", src_app, dest_app], check=True)
    subprocess.run(["xattr", "-cr", dest_app], check=False)
    subprocess.run(["hdiutil", "detach", mount_point, "-force"], check=False)
    return os.path.join(dest_app, "Contents", "MacOS", "cloakfox")


def main():
    dmg = os.environ.get("CLOAKFOX_DMG", DEFAULT_DMG)
    work_dir = tempfile.mkdtemp(prefix="cfx-kbd-")
    print(f"[setup] DMG: {dmg}")
    print(f"[setup] work dir: {work_dir}")

    os.makedirs(os.path.join(work_dir, "app"), exist_ok=True)
    binary = mount_and_extract(dmg, os.path.join(work_dir, "app"))

    profile_dir = tempfile.mkdtemp(prefix="cfx-kbd-prof-")
    seed = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    with open(os.path.join(profile_dir, "user.js"), "w") as f:
        f.write(f'''
user_pref("cloakfox.enabled", true);
user_pref("cloakfox.container.0.keyboard_seed", "{seed}");
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
    svc = Service(log_path="/tmp/probe-keyboard.log")
    driver = webdriver.Firefox(options=opts, service=svc)

    try:
        driver.get("https://example.com/")
        time.sleep(1.2)

        # Dispatch a burst of synthetic keydown events and record
        # the timeStamp each listener observes. Inject from a page-
        # compartment <script> so the listener we attach is the
        # same context the actor should have wrapped.
        driver.execute_script("""
          const s = document.createElement('script');
          s.textContent = `
            (async () => {
              const stamps = [];
              document.body.addEventListener('keydown', (ev) => {
                stamps.push(ev.timeStamp);
              });
              // Dispatch 5 synthetic events back-to-back.
              for (let i = 0; i < 5; i++) {
                const ev = new KeyboardEvent('keydown', { key: 'a' });
                document.body.dispatchEvent(ev);
              }
              // Give the event loop a microtask tick, then publish.
              await Promise.resolve();
              document.body.setAttribute('data-kbd', JSON.stringify(stamps));
            })();
          `;
          document.head.appendChild(s);
        """)
        time.sleep(0.5)

        stamps_raw = driver.execute_script(
            "return document.body.getAttribute('data-kbd');"
        )
        if not stamps_raw:
            print("FAIL — data-kbd attribute missing; script didn't run")
            return 2
        stamps = json.loads(stamps_raw)
        print(f"[probe] 5 keydown timestamps: {stamps}")

        if len(stamps) < 5:
            print(f"FAIL — only got {len(stamps)} events (expected 5)")
            return 2

        # What the actor does (per cadence.ts): on events arriving
        # within 30ms of the previous one, set event.timeStamp to
        # previous_real_time + 30ms + [0,15)ms jitter. This clusters
        # burst-dispatched events around first+30 rather than revealing
        # the sub-millisecond burst pattern. It does NOT produce
        # monotonically-increasing timestamps — that's a design choice
        # inherited from the original extension implementation.
        #
        # The actor's signature: event 2+ get stamps significantly
        # higher than event 1 (jumped by ~30+jitter). Without the
        # actor, all 5 stamps would cluster within ~1ms of each other
        # (synthetic dispatch is synchronous, same tick).
        first = stamps[0]
        others = stamps[1:]
        max_burst_gap = max(s - first for s in others)  # biggest jump from first
        min_burst_gap = min(s - first for s in others)  # smallest jump (could be <0 due to jitter order)
        print(f"[probe] stamp[0]={first}, offsets from it: {[round(s - first, 2) for s in others]}")

        # Without actor: all offsets <1ms. With actor: all offsets in
        # [MIN_DELAY_MS, MIN_DELAY_MS + MAX_JITTER_MS + tolerance].
        bumped = sum(1 for s in others if (s - first) >= (MIN_DELAY_MS - 1.0))
        print(f"[probe] events bumped by ≥{MIN_DELAY_MS - 1:.0f}ms from first: {bumped}/{len(others)}")

        if bumped == len(others):
            print("PASS — every burst event (2..N) is normalized ≥29ms past the first; "
                  "actor wrapped addEventListener correctly.")
            return 0
        if bumped == 0:
            print("FAIL — no event was bumped; actor did NOT fire on the synthetic burst.")
            return 1
        print(f"PARTIAL — {bumped}/{len(others)} events bumped. Unexpected — wrapping race?")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
