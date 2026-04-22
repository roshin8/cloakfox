"""
cpp-first POC end-to-end test.

Mounts a CI-produced DMG, extracts Cloakfox.app, strips macOS quarantine,
creates a fresh profile with cpp-first prefs seeded, launches via
selenium, and asserts:

  1. https://example.com renders
  2. Math.PI is perturbed (the CloakfoxMath JSWindowActor fired)
  3. Math.E is perturbed
  4. Math.sin(0.5) has 1e-12-ish noise (trig wrapping works)
  5. about:cloakfox loads without error (settings page registered)
  6. The settings page contains the expected elements

Everything chrome-principal: no extension is loaded. The assertions
validate the three POC pieces of the cpp-first architecture:
  - AboutRedirector kRedirMap entry (about:cloakfox → chrome://)
  - ActorManagerParent JSWINDOWACTORS entry (CloakfoxMath registered)
  - DMG pipeline actually ships our additions (jar.mn + moz.build)

Usage:
  CLOAKFOX_DMG=/tmp/cfx-artifact/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg \\
      python tests/fingerprint/probe_cpp_first.py

If CLOAKFOX_DMG is unset, defaults to that path.

Exit codes:
  0 — all assertions pass.
  1 — at least one assertion failed.
  2 — couldn't launch browser / mount DMG / etc.
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
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service


DEFAULT_DMG = "/tmp/cfx-artifact/cloakfox-macos-arm64/Cloakfox-macos-arm64.dmg"
IEEE_PI = 3.141592653589793
IEEE_E  = 2.718281828459045
IEEE_SIN_HALF = 0.479425538604203


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def mount_dmg(dmg_path: str) -> tuple[str, str]:
    """Mount the DMG; return (mount_point, app_path_inside_mount)."""
    if not os.path.exists(dmg_path):
        sys.exit(f"DMG not found: {dmg_path}")
    print(f"[mount] {dmg_path}")
    result = run(["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", dmg_path],
                 capture=True)
    # Parse plist to get mount point. Cheap: grep for /Volumes/... line.
    mount_point = None
    for line in result.stdout.splitlines():
        if "/Volumes/" in line and "<string>" in line:
            s = line.strip().removeprefix("<string>").removesuffix("</string>")
            if s.startswith("/Volumes/"):
                mount_point = s
                break
    if not mount_point:
        sys.exit(f"Could not locate /Volumes/ mount point in hdiutil output:\n{result.stdout}")
    apps = [p for p in os.listdir(mount_point) if p.endswith(".app")]
    if not apps:
        sys.exit(f"No .app found in {mount_point}")
    app_path = os.path.join(mount_point, apps[0])
    print(f"[mount] ok: {mount_point}, app: {apps[0]}")
    return mount_point, app_path


def unmount_dmg(mount_point: str) -> None:
    print(f"[unmount] {mount_point}")
    run(["hdiutil", "detach", mount_point, "-force"], check=False)


def prepare_app(src_app: str, dest_dir: str) -> str:
    """Copy the .app out of the DMG mount, strip quarantine, return binary path."""
    os.makedirs(dest_dir, exist_ok=True)
    dest_app = os.path.join(dest_dir, os.path.basename(src_app))
    if os.path.exists(dest_app):
        shutil.rmtree(dest_app)
    print(f"[copy] {src_app} -> {dest_app}")
    run(["cp", "-R", src_app, dest_app])
    # Strip macOS quarantine so Gatekeeper doesn't block the unsigned binary.
    run(["xattr", "-cr", dest_app], check=False)
    # Locate the launcher. Firefox builds this as Contents/MacOS/<short-name>.
    macos_dir = os.path.join(dest_app, "Contents", "MacOS")
    candidates = [n for n in os.listdir(macos_dir) if not n.startswith(".")]
    # Prefer ones without dots (the main launcher).
    launcher = next((n for n in candidates if n == "cloakfox"), None) or \
               next((n for n in candidates if "." not in n), None) or \
               candidates[0]
    bin_path = os.path.join(macos_dir, launcher)
    print(f"[copy] binary: {bin_path}")
    return bin_path


def write_profile(profile_dir: str, seed_b64: str) -> None:
    """Seed a fresh Firefox profile with cpp-first prefs."""
    os.makedirs(profile_dir, exist_ok=True)
    user_js = f'''// cpp-first POC test profile
user_pref("cloakfox.enabled", true);
user_pref("cloakfox.container.0.math_seed", "{seed_b64}");
// Make automation reliable.
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("toolkit.startup.max_resumed_crashes", -1);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);
user_pref("app.update.auto", false);
user_pref("app.update.enabled", false);
'''
    with open(os.path.join(profile_dir, "user.js"), "w") as f:
        f.write(user_js)
    print(f"[profile] seeded with cloakfox.enabled=true + 32-byte math_seed")


def start_driver(binary: str, profile_dir: str) -> webdriver.Firefox:
    opts = Options()
    opts.binary_location = binary
    opts.add_argument("-profile")
    opts.add_argument(profile_dir)
    opts.add_argument("-no-remote")
    opts.add_argument("--headless")
    opts.add_argument("-remote-allow-system-access")
    svc = Service(log_path="/tmp/probe-cpp-first.log")
    return webdriver.Firefox(options=opts, service=svc)


def assert_result(name: str, predicate_ok: bool, detail: str = "") -> bool:
    tag = "PASS" if predicate_ok else "FAIL"
    line = f"  [{tag}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return predicate_ok


def diagnose_chrome(driver: webdriver.Firefox) -> None:
    """Switch to chrome context and dump actor/pref state for debugging."""
    print("\n[diagnose] chrome-context probe")
    try:
        driver.set_context("chrome")
        result = driver.execute_script("""
          const out = {};
          try { out.enabled_pref = Services.prefs.getBoolPref("cloakfox.enabled", null); }
            catch (e) { out.enabled_pref = "ERR: " + e.message; }
          try { out.seed_pref = Services.prefs.getStringPref("cloakfox.container.0.math_seed", ""); }
            catch (e) { out.seed_pref = "ERR: " + e.message; }
          try {
            out.actor_registered = (typeof ChromeUtils.registeredJSWindowActors === "function")
              ? Object.keys(ChromeUtils.registeredJSWindowActors()).includes("CloakfoxMath")
              : "ChromeUtils.registeredJSWindowActors not available";
          } catch (e) { out.actor_registered = "ERR: " + e.message; }
          try {
            const messages = Services.console.getMessageArray() || [];
            out.cloakfox_console_errors = messages
              .map(m => m.message || m.toString())
              .filter(s => /[Cc]loakfox|CloakfoxMath/.test(s))
              .slice(-10);
          } catch (e) { out.cloakfox_console_errors = "ERR: " + e.message; }
          try {
            // Try to instantiate the child module directly — surfaces any
            // load-time error.
            const mod = ChromeUtils.importESModule("resource:///actors/CloakfoxMathChild.sys.mjs");
            out.actor_module_load = mod && typeof mod.CloakfoxMathChild === "function"
              ? "ok" : "module loaded but no export";
          } catch (e) { out.actor_module_load = "ERR: " + e.message; }
          return out;
        """)
        print(f"[diagnose] {json.dumps(result, indent=2, default=str)}")
    finally:
        driver.set_context("content")


def probe_math(driver: webdriver.Firefox) -> list[tuple[str, bool, str]]:
    """Navigate example.com, read Math values, assert perturbation.

    CRITICAL: selenium's execute_script runs in a *sandbox* with its
    own Math intrinsic, not the page's actual Math. Reading Math.PI
    via execute_script gives the IEEE default even when the page's
    Math is spoofed. To see what page scripts actually see, we inject
    a <script> tag that writes values into the DOM, then read the DOM
    back via execute_script.
    """
    print("\n[probe] https://example.com — expecting perturbed Math")
    driver.set_page_load_timeout(30)
    driver.get("https://example.com/")
    time.sleep(1.0)

    # Inject page-compartment JS that serializes Math values into an
    # attribute on <body>. This runs in the same compartment the actor
    # modified, so it sees the spoofed Math.
    driver.execute_script("""
      const s = document.createElement('script');
      s.textContent = `
        document.body.setAttribute('data-cfx-probe', JSON.stringify({
          pi: Math.PI,
          e:  Math.E,
          sin_half: Math.sin(0.5),
          cos_zero: Math.cos(0),
          sqrt_two: Math.sqrt(2),
          ln2: Math.LN2,
          sqrt2: Math.SQRT2,
        }));
      `;
      document.head.appendChild(s);
    """)
    time.sleep(0.2)
    raw_str = driver.execute_script(
        "return document.body.getAttribute('data-cfx-probe');"
    )
    if not raw_str:
        return [("Math probe injection", False, "data-cfx-probe attribute missing — inline <script> didn't run?")]
    raw = json.loads(raw_str)
    print(f"[probe] page-compartment Math: {json.dumps(raw, indent=2)}")

    out = []
    pi_diff = abs(raw["pi"] - IEEE_PI)
    # "Any perturbation" is the POC bar — PRNG-magnitude tuning is
    # separate work (see README). As long as delta is non-zero, the
    # full chrome→pageWin.Math assignment pipeline is working.
    out.append(("Math.PI is perturbed",
                raw["pi"] != IEEE_PI,
                f"PI={raw['pi']}, |delta|={pi_diff:.2e}"))
    e_diff = abs(raw["e"] - IEEE_E)
    out.append(("Math.E is perturbed",
                raw["e"] != IEEE_E,
                f"E={raw['e']}, |delta|={e_diff:.2e}"))
    sin_diff = abs(raw["sin_half"] - IEEE_SIN_HALF)
    out.append(("Math.sin(0.5) has trig noise",
                sin_diff > 1e-14,
                f"sin(0.5)={raw['sin_half']}, |delta|={sin_diff:.2e}"))
    out.append(("Math.cos(0) stays integer (no noise on integers)",
                raw["cos_zero"] == 1,
                f"cos(0)={raw['cos_zero']}"))
    ln2_diff = abs(raw["ln2"] - 0.6931471805599453)
    out.append(("Math.LN2 is perturbed",
                ln2_diff > 0,
                f"LN2={raw['ln2']}, |delta|={ln2_diff:.2e}"))
    return out


def probe_about_page(driver: webdriver.Firefox) -> list[tuple[str, bool, str]]:
    """Navigate about:cloakfox and verify the registered page loads."""
    print("\n[probe] about:cloakfox — expecting settings page")
    out = []
    try:
        driver.get("about:cloakfox")
        time.sleep(0.5)
        title = driver.title
        out.append(("about:cloakfox loads without net error",
                    "Unable to connect" not in title and "Address Not Valid" not in title,
                    f"title={title!r}"))
        out.append(("Settings page title set to 'Cloakfox Settings'",
                    title == "Cloakfox Settings",
                    f"title={title!r}"))
        # Check the primary toggle element exists.
        has_toggle = driver.execute_script(
            "return !!document.getElementById('cfx-enabled');")
        out.append(("Primary toggle (#cfx-enabled) present",
                    bool(has_toggle), ""))
        has_regen = driver.execute_script(
            "return !!document.getElementById('cfx-regenerate');")
        out.append(("Regenerate-seed button (#cfx-regenerate) present",
                    bool(has_regen), ""))
    except Exception as e:
        out.append(("about:cloakfox navigation",
                    False,
                    f"exception: {e}"))
    return out


def main() -> int:
    dmg = os.environ.get("CLOAKFOX_DMG", DEFAULT_DMG)
    work_dir = tempfile.mkdtemp(prefix="cfx-cpp-first-")
    app_dir = os.path.join(work_dir, "app")
    profile_dir = os.path.join(work_dir, "profile")

    mount_point = None
    driver = None
    try:
        mount_point, src_app = mount_dmg(dmg)
        binary = prepare_app(src_app, app_dir)
        # Unmount immediately; we have a local copy.
        unmount_dmg(mount_point)
        mount_point = None

        seed = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
        write_profile(profile_dir, seed)

        print(f"[launch] {binary}")
        driver = start_driver(binary, profile_dir)

        results: list[tuple[str, bool, str]] = []
        # Chrome-context diagnostics first — tells us if the actor is even
        # registered and if prefs look right. Run BEFORE page probes so
        # we don't blame page-side Math failures on bad prefs.
        diagnose_chrome(driver)
        results += probe_math(driver)
        results += probe_about_page(driver)

        print("\n=== Summary ===")
        passed = 0
        for name, ok, detail in results:
            assert_result(name, ok, detail)
            if ok:
                passed += 1
        total = len(results)
        print(f"\n{passed}/{total} assertions passed")
        return 0 if passed == total else 1

    except Exception as e:
        print(f"[error] {e}")
        return 2
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        if mount_point:
            unmount_dmg(mount_point)
        # Leave work_dir around for post-mortem. Comment out to auto-clean:
        # shutil.rmtree(work_dir, ignore_errors=True)
        print(f"\n[cleanup] work dir left at {work_dir} (delete manually if desired)")


if __name__ == "__main__":
    sys.exit(main())
