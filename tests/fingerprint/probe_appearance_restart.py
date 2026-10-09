#!/usr/bin/env python3
"""Exercise the actual appearance restart button with a disposable profile."""
import json
import os
import shutil
import subprocess
import signal
import tempfile
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from probe_appearance import chrome, extension_branding, PREF, MODULE


def main():
    binary = os.environ["CLOAKFOX_BIN"]
    gecko = os.environ.get("GECKODRIVER") or shutil.which("geckodriver")
    assert gecko and os.uname().sysname == "Darwin"
    with tempfile.TemporaryDirectory(prefix="cloakfox-appearance-restart-") as temp:
        profile = Path(temp) / "profile with spaces"
        profile.mkdir()
        opts = Options()
        opts.binary_location = binary
        if not os.environ.get("CLOAKFOX_HEADFUL"):
            opts.add_argument("-headless")
        opts.add_argument("-profile")
        opts.add_argument(str(profile))
        driver = webdriver.Firefox(options=opts, service=Service(
            executable_path=gecko, service_args=["--allow-system-access"],
            log_output=str(Path(temp) / "geckodriver.log")))
        try:
            chrome(driver, """
              Services.prefs.setBoolPref('browser.tabs.warnOnClose',false);
              Services.prefs.setBoolPref('browser.warnOnQuit',false);
              Services.prefs.setStringPref('cloakfox.appearance.probe','restart preserved');
            """)
            chrome(driver, """
              gBrowser.addTab('data:text/html,<title>Appearance tab kept</title>kept',
                {triggeringPrincipal:Services.scriptSecurityManager.getSystemPrincipal()});
            """)
            WebDriverWait(driver, 10).until(lambda _: "Appearance tab kept" in chrome(
                driver, "return gBrowser.tabs.map(t => t.label)"))
            for enabled in (True, False):
                chrome(driver, "Services.prefs.setBoolPref('browser.tabs.warnOnClose',false);")
                print(f"Applying appearance: {enabled}", flush=True)
                driver.get("about:cloakfox")
                WebDriverWait(driver, 10).until(lambda d: d.find_element(
                    By.ID, "cfx-appearance-status").text.startswith("Active:"))
                toggle = driver.find_element(By.CSS_SELECTOR, f'input[data-pref="{PREF}"]')
                assert toggle.is_selected() != enabled
                old_pid = chrome(driver, "return Services.appinfo.processID")
                driver.execute_script("arguments[0].click()", toggle)
                button = WebDriverWait(driver, 10).until(lambda d: d.find_element(
                    By.ID, "cfx-appearance-restart"))
                assert button.is_displayed(), "Restart action should be available"
                driver.execute_script("setTimeout(() => arguments[0].click(), 0)", button)
                print("Restart requested", flush=True)
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    state = subprocess.run(["ps", "-p", str(old_pid), "-o", "stat="],
                                           capture_output=True, text=True).stdout.strip()
                    if not state or state.startswith("Z"):
                        break
                    time.sleep(0.1)
                else:
                    error = driver.find_element(By.ID, "cfx-appearance-status").text
                    raise AssertionError(f"Original process did not restart: {error}")
                driver.service.stop()
                active_port = profile / "MarionetteActivePort"
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if active_port.exists() and active_port.read_text().strip().isdigit():
                        port = int(active_port.read_text().strip())
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError("Restarted browser did not publish its automation port")
                connect = Options()
                connect.binary_location = binary
                driver = webdriver.Firefox(options=connect, service=Service(
                    executable_path=gecko,
                    service_args=["--connect-existing", "--marionette-port", str(port),
                                  "--allow-system-access"],
                    log_output=str(Path(temp) / "geckodriver.log")))
                assert chrome(driver, "return Services.appinfo.processID") != old_pid
                assert Path(chrome(driver, "return Services.dirsvc.get('ProfD',Ci.nsIFile).path")).resolve() == profile.resolve()
                assert chrome(driver, "return Services.prefs.getStringPref('cloakfox.appearance.probe')") == "restart preserved"
                assert "Appearance tab kept" in chrome(driver, "return gBrowser.tabs.map(t => t.label)"), "Tabs should survive appearance restart"
                driver.set_context("chrome")
                status = driver.execute_async_script("""
                  ChromeUtils.importESModule(arguments[0]).getAppearance().then(arguments[arguments.length - 1]);
                """, MODULE)
                driver.set_context("content")
                assert status["active"] == enabled, status
                assert chrome(driver, "return Services.env.get('CLOAKFOX_RESTART_BUNDLE')") == "", "Restart request should be consumed"
                driver.get("about:cloakfox")
                expected = "Firefox" if enabled else "Cloakfox"
                if os.environ.get("CLOAKFOX_HEADFUL"):
                    pid = chrome(driver, "return Services.appinfo.processID")
                    native = json.loads(subprocess.check_output([
                        "/usr/bin/osascript", "-l", "JavaScript", "-e",
                        'ObjC.import("AppKit"); '
                        f'const app = $.NSRunningApplication.runningApplicationWithProcessIdentifier({pid}); '
                        'JSON.stringify({name:ObjC.unwrap(app.localizedName),'
                        'bundle:ObjC.unwrap(app.bundleURL.path)})',
                    ], text=True))
                    assert native["name"] == expected, native
                    assert Path(native["bundle"]).resolve() == Path(status["app"]).resolve(), native
                WebDriverWait(driver, 10).until(lambda d: d.title == expected)
                extension_branding(driver, expected)
                print(f"Restarted into {expected}; profile and tabs preserved", flush=True)
            # Relaunching the original installation also honors the saved choice.
            # Use one tab so the normal close-tabs prompt needs no UI interaction.
            chrome(driver, """
              for (const tab of gBrowser.tabs.slice(1)) gBrowser.removeTab(tab);
              Services.prefs.setBoolPref(arguments[0],true);
              Services.prefs.savePrefFile(null);
            """, PREF)
            closed_pid = chrome(driver, "return Services.appinfo.processID")
            # --connect-existing leaves the attached browser running on quit.
            # Shut down this owned test app explicitly before a fresh launch.
            chrome(driver, "setTimeout(() => Services.startup.quit(Ci.nsIAppStartup.eForceQuit),100);")
            driver.service.stop()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                state = subprocess.run(["ps", "-p", str(closed_pid), "-o", "stat="],
                                       capture_output=True, text=True).stdout.strip()
                if not state or state.startswith("Z"):
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Browser did not finish closing before fresh launch")
            original = subprocess.Popen([binary, *opts.arguments, "-no-remote", "--marionette",
                                         "--remote-allow-system-access"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            original.wait(timeout=45)
            assert original.returncode == 0, "Original app failed during appearance handoff"
            active_port = profile / "MarionetteActivePort"
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if active_port.exists() and active_port.read_text().strip().isdigit():
                    port = int(active_port.read_text().strip())
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Saved appearance did not start")
            driver = webdriver.Firefox(options=connect, service=Service(
                executable_path=gecko,
                service_args=["--connect-existing", "--marionette-port", str(port),
                              "--allow-system-access"],
                log_output=str(Path(temp) / "geckodriver.log")))
            assert Path(chrome(driver, "return Services.dirsvc.get('ProfD',Ci.nsIFile).path")).resolve() == profile.resolve()
            driver.set_context("chrome")
            active = driver.execute_async_script("""
              ChromeUtils.importESModule(arguments[0]).getAppearance()
                .then(status => arguments[arguments.length - 1](status.active));
            """, MODULE)
            driver.set_context("content")
            assert active, "Launching the original app must honor saved Firefox appearance"
            extension_branding(driver, "Firefox")
            print("Original-app launch honors saved Firefox appearance", flush=True)
        finally:
            try:
                driver.quit()
            except Exception:
                driver.service.stop()
            processes = subprocess.run(["ps", "-axo", "pid=,command="],
                                       capture_output=True, text=True).stdout
            # NSWorkspace can restart with no command-line profile argument.
            # Inspect candidate test executables' environment privately and match
            # only this disposable profile, including canonical /private paths.
            owned_pids = []
            for line in processes.splitlines():
                if "/Contents/MacOS/" not in line:
                    continue
                pid = int(line.split(None, 1)[0])
                candidate = str(profile) in line or str(profile.resolve()) in line
                if not candidate and binary in line:
                    environment = subprocess.run(
                        ["ps", "eww", "-p", str(pid), "-o", "command="],
                        capture_output=True, text=True).stdout
                    candidate = str(profile) in environment or str(profile.resolve()) in environment
                if candidate:
                    owned_pids.append(pid)
                    try: os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError: pass
            deadline = time.monotonic() + 10
            while owned_pids and time.monotonic() < deadline:
                owned_pids = [pid for pid in owned_pids if subprocess.run(
                    ["ps", "-p", str(pid), "-o", "stat="], capture_output=True,
                    text=True).stdout.strip()[:1] not in ("", "Z")]
                if owned_pids: time.sleep(0.1)
            assert not owned_pids, f"Disposable browser processes did not exit: {owned_pids}"
    print("PASS — native appearance restart handoff in both directions")


if __name__ == "__main__":
    main()
